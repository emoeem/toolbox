"""图像文档存储与编辑状态：document_id → 内存 ndarray（协议 §3.1/§3.3/§4）。"""
from __future__ import annotations

import io
import math
import re
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

# import processors 触发滤镜注册；core 提供调整/变换原语（复用资产，不重写算法）。
from processors import core as image_core
from processors.cancellation import CancelledError
from processors.utils import load_image, np_to_pil, save_image

from .. import protocol


class WorkerError(Exception):
    """带稳定错误码的业务异常，dispatcher 据此构造协议错误响应。"""

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass
class HistoryEntry:
    """历史栈条目（docs/ipc-protocol.md §3.3，Phase 6+ 参数化 undo）。

    不变量：pixels 与 replay 至少一个非 None；pixels=None 时 replay 必非
    None（参数化条目）；两者并存仅限携带重放参数的快照条目（image.adjust 与
    Phase 9 组合参数形式的 image.transform）——
    - 快照条目（pixels 非 None）：保存该动作**之前**的像素，undo 直达；replay
      为该条目自身动作的重放参数（可确定性重放的动作才有，见下），供"重放越过
      本条目"重建其后的参数化条目状态。image.adjust 属于此类（adjustments 可
      确定性重放）；组合参数 image.transform 亦属此类（crop/rotate_free/
      perspective/scale 为确定性函数，同输入同参数 → bitwise 同输出）；既有
      op/params 形式的 image.transform 仍是快照条目且 replay=None（scale/crop
      有损，参数重放不可靠——重放屏障）。
    - 参数化条目（replay 非 None）：只存动作参数（filter 链 steps / 标注 ops），
      不存像素，内存 O(参数)。undo 时从基线/最近快照锚点重放
      （`_replay_state_before`）。
    replay 载荷形状（Worker 内部策略，非协议字段）：
      {'kind': 'chain', 'steps': <协议 filters 数组>}
      {'kind': 'adjust', 'applies': [<adjustments 对象>, ...]}  # 合并条目为多段
      {'kind': 'transform', 'ops': <组合变换 spec>}            # 快照+replay
      {'kind': 'annotate', 'ops': [<标注 ops 数组>]}           # 参数化条目
    """
    name: str  # §3.3 条目名 = 产生该条目的动作名（undo 该条目即撤销此动作）
    pixels: np.ndarray | None = None
    replay: dict[str, Any] | None = None


@dataclass
class Document:
    document_id: str
    source: str
    image: np.ndarray
    format: str = ''
    modified: bool = False
    extras: dict[str, Any] = field(default_factory=dict)
    # 编辑状态（docs/ipc-protocol.md §3.1）：version 从 0 起，全分辨率变更成功后 +1。
    version: int = 0
    # 源图引用（reset 的恢复目标与参数化 undo 的重放基线）。与 image 暂指同一
    # 对象：processors 均为函数式（返回新数组，不原地修改），首次变更前
    # push_history 已做 .copy()，别名安全。
    source_image: np.ndarray | None = None
    # 历史栈（docs/ipc-protocol.md §3.3）：HistoryEntry（快照/参数化二态）。
    # undo_stack[-1] 是最近一次全分辨率变更的回退点；redo_stack[0] 是最近被撤销的状态。
    undo_stack: list[HistoryEntry] = field(default_factory=list)
    redo_stack: list[HistoryEntry] = field(default_factory=list)
    # 深度淘汰（HistoryMixin._trim_history）丢弃的前导动作名：这些动作的产物
    # 状态已不可达，history() 据此跳过，保证条目名与可达状态一一对齐（§3.3）。
    # undo 底条目时命名职责随改名转移到复合 redo 条目，本表就此清空（undo）。
    dropped_names: list[str] = field(default_factory=list)


class HistoryMixin:
    """文档历史（docs/ipc-protocol.md §3.3）：像素快照留在 Worker 进程内，不跨进程复制。

    内存策略（Phase 6+ 参数化 undo，docs/competitive-analysis.md §4 行动项 1）：
    滤镜链应用只存链参数（参数化条目），undo 从基线/最近快照锚点重放链，
    内存从 O(像素×历史) 降到 O(参数)；像素快照仅保留给不可参数化的操作
    （transform/crop 类）。预算策略对齐旧 app（app/main_window.py:346-357）：
    最多 30 条 + 512MB 字节预算（字节只计快照条目，参数化条目近似零耗）；
    超限从最旧开始淘汰，但至少保留一条 undo 条目。淘汰不得破坏 §3.3 契约
    （entries[0] 恒为初始状态、undo 到底恒回到 open 像素），见 `_trim_history`。
    容量为 Worker 内部策略，非协议字段。
    """

    HISTORY_MAX_ENTRIES = 30
    HISTORY_BUDGET_BYTES = 512 * 1024 * 1024

    def _push_history(self, doc: Document, name: str,
                      replay: dict[str, Any] | None = None) -> None:
        """全分辨率应用前调用：快照当前像素（undo 的回退点），截断 redo 分支。

        与旧 app `_push_history` 相同的时机约束：必须在换入新结果之前调用。
        replay 为该动作自身的重放参数（可确定性重放时携带，如 image.adjust 的
        adjustments 与 Phase 9 组合参数 image.transform 的 ops；既有 op 形式
        的 transform 不携带——重放屏障，见 HistoryEntry 注）。
        """
        doc.undo_stack.append(HistoryEntry(name, pixels=doc.image.copy(), replay=replay))
        doc.redo_stack.clear()  # 协议 §3.3：非栈顶的新变更截断 redo 分支
        self._trim_history(doc)

    def _push_replay_history(self, doc: Document, name: str,
                             replay: dict[str, Any]) -> None:
        """参数化推送（滤镜链应用）：只存参数不存像素，undo 靠重放复原。

        推送规则（重放完整性）：仅当栈顶是参数化条目（延续同一参数段）或
        可重放快照（adjustments）或栈空（基线即锚点）时才允许——栈顶是不可
        重放快照（transform 类）时参数化条目的 undo 无法重放越过它，本条目
        退化为像素快照（该快照成为新锚点）。
        """
        top = doc.undo_stack[-1] if doc.undo_stack else None
        if top is not None and top.pixels is not None and top.replay is None:
            self._push_history(doc, name)
            return
        doc.undo_stack.append(HistoryEntry(name, pixels=None, replay=replay))
        doc.redo_stack.clear()  # 协议 §3.3：非栈顶的新变更截断 redo 分支
        self._trim_history(doc)

    def _push_adjust_history(self, doc: Document, name: str,
                             adjustments: dict[str, float]) -> None:
        """全分辨率 adjust 推送，带滑杆命令合并（coalescing，§4 行动项 2）。

        与上一条同 key（同为全分辨率 image.adjust）且中间无其它动作/撤销时，
        合并为单条历史：快照（undo 目标）不变，本次 adjustments 追加进该条目
        的重放序列（applies），重放按序执行两段调整即可精确复原现状态。
        redo 栈非空说明栈顶条目之后发生过 undo——此时"现状态"不再等于
        "applies 依次作用于条目快照"，绝不合并（否则重放与实况不一致）。
        """
        top = doc.undo_stack[-1] if doc.undo_stack else None
        if (top is not None and top.name == name and top.pixels is not None
                and top.replay is not None and top.replay.get('kind') == 'adjust'
                and not doc.redo_stack):
            top.replay['applies'].append(dict(adjustments))
            doc.redo_stack.clear()  # 新的全分辨率变更同样截断 redo 分支（§3.3）
            return
        self._push_history(doc, name,
                           replay={'kind': 'adjust', 'applies': [dict(adjustments)]})

    def _trim_history(self, doc: Document) -> None:
        """超限从最旧淘汰（对齐旧 app 预算策略），且 §3.3 两个不变量在任意
        淘汰深度下保持：entries[0] 恒为初始状态、undo 到底恒回到 open 像素。

        - 字节预算只计快照条目（参数化条目仅存参数，近似零耗）。
        - 底条目的快照像素恒等于 source_image（首次快照的就是 open 态），淘汰
          它时原地改写为对 source_image 的共享引用：释放的是独立副本的内存，
          状态与条目名一样不丢，底条目从此"钉"在源图上（processors 均为函数
          式，source_image 从不原地修改，共享引用安全）。
        - 预算仍超限时弹出次旧条目（undo_stack[1]）：其动作名记入
          dropped_names，该动作的产物状态从此不可达；history() 跳过不可达
          状态并对齐条目名，绝不伪称 open 或错位命名。
        - 参数化段完整性：弹出的次旧条目是参数化条目、或其上紧邻参数化条目
          时，参数段内上方条目的 undo 重放依赖段底成员的参数——连同整段一并
          弹出（见 `_evict_oldest`），保持"淘汰只发生在栈前缀"的对齐不变量。
        """
        while len(doc.undo_stack) > self.HISTORY_MAX_ENTRIES:
            self._evict_oldest(doc)
        total = self._snapshot_bytes(doc)
        while len(doc.undo_stack) > 1 and total > self.HISTORY_BUDGET_BYTES:
            self._evict_oldest(doc)
            total = self._snapshot_bytes(doc)

    @staticmethod
    def _snapshot_bytes(doc: Document) -> int:
        return sum(entry.pixels.nbytes for entry in doc.undo_stack
                   if entry.pixels is not None)

    def _evict_oldest(self, doc: Document) -> None:
        """淘汰一步：底条目改写为源图共享引用（钉住 open 态），已钉住时弹出
        次旧条目（undo_stack[1]）并把其动作名记入 dropped_names；弹出的位置
        之上紧邻参数化条目时连同整段弹出（重放完整性，见 `_trim_history`）。

        调用前提 len(undo_stack) >= 2（两条淘汰循环的守卫保证）。
        """
        bottom = doc.undo_stack[0]
        if bottom.pixels is not None and bottom.pixels is not doc.source_image:
            # 底条目快照即 open 态像素的独立副本：改写为共享引用即完成本次淘汰。
            # replay 原样保留：其上是参数化条目时，undo 重放要越过底条目自身
            # 的动作（参数就在这里）。
            doc.undo_stack[0] = HistoryEntry(bottom.name, pixels=doc.source_image,
                                             replay=bottom.replay)
            return
        if len(doc.undo_stack) > 1:
            doc.dropped_names.append(doc.undo_stack.pop(1).name)
            # 参数段整体弹出：段底成员的参数已随本次淘汰丢失，段内上方条目
            # 的重放会缺参；停在快照条目上（快照 undo 不依赖重放）。
            while len(doc.undo_stack) > 1 and doc.undo_stack[1].pixels is None:
                doc.dropped_names.append(doc.undo_stack.pop(1).name)

    def undo(self, doc: Document, progress_cb: Any = None,
             cancel_token: Any = None) -> None:
        """撤销栈顶条目（docs/ipc-protocol.md §3.3）。

        快照条目：直接恢复像素（与 1.0 相同的语义）。参数化条目：从基线/
        最近快照锚点重放（`_replay_state_before`）复原该动作之前的状态。
        先纯计算目标像素、后提交栈改写（compute-before-commit）：重放中途
        取消或失败时文档状态不动，绝不产生半途栈。
        """
        if not doc.undo_stack:
            raise WorkerError(protocol.ERR_UNREDOABLE, f'文档无可撤销条目: {doc.document_id}')
        entry = doc.undo_stack[-1]
        is_bottom = len(doc.undo_stack) == 1
        composite_eviction = is_bottom and bool(doc.dropped_names)
        # 快照条目：重做保存"被离开状态"的像素（1.0 语义）。例外（深度淘汰）：
        # undo 底条目时被离开的状态是最后一个被淘汰动作的产物（含整段淘汰动作
        # 的复合效应），无法由参数唯一复原——重做按快照语义保存当前像素，并
        # 沿用 dropped_names[-1] 的动作名（§3.3 条目命名规则）。
        redo_as_snapshot = entry.pixels is not None or composite_eviction
        if entry.pixels is not None:
            new_image = entry.pixels
        elif composite_eviction:
            # 底部参数化条目：其动作之前的状态即 open 态 = 源图基线。
            new_image = doc.source_image
        else:
            # 参数化条目：从基线/最近快照锚点重放复原该动作之前的状态。
            new_image = self._replay_state_before(doc, progress_cb, cancel_token)
        # ---- 提交（重放成功后才改栈：取消/失败不产生半途状态）----
        doc.undo_stack.pop()
        redo_name = entry.name
        if composite_eviction:
            redo_name = doc.dropped_names[-1]
        if redo_as_snapshot:
            if composite_eviction:
                # 复合 redo 条目（深度淘汰）：pixels 已是整段被淘汰动作的复合
                # 产物，自身不可由单一动作的参数重放——replay 置 None（按快照/
                # 重放屏障语义随行）。随行底条目自身的 replay 会与 pixels 失配
                # （锚点重放会拿陈旧参数从本快照出发复原出错误像素），且会让
                # _push_replay_history 误把本条目当可重放锚点；置 None 后其上
                # 的参数化推送自动退化为快照条目，重放完整性恢复。
                doc.redo_stack.append(HistoryEntry(redo_name, pixels=doc.image.copy()))
            else:
                # replay 原样随行：重做压回 undo 栈后，其上参数化条目的重放仍可
                # 越过本条目（快照条目自带自身动作的参数）。
                doc.redo_stack.append(HistoryEntry(redo_name, pixels=doc.image.copy(),
                                                   replay=entry.replay))
        else:
            # 当前状态正是该动作的产物，重做时沿用同一动作名与参数（§3.3）。
            doc.redo_stack.append(HistoryEntry(redo_name, replay=entry.replay))
        if composite_eviction:
            # 命名职责已随改名转移到复合 redo 条目：dropped_names 就此清空，
            # 此后新条目不会被 history() 的 dropped_names 分支吞名（§3.3
            # 条目名与可达状态一一对齐）。
            doc.dropped_names.clear()
        doc.image = new_image

    def redo(self, doc: Document, progress_cb: Any = None,
             cancel_token: Any = None) -> None:
        """重做 redo 分支栈顶条目：快照条目恢复像素（1.0 语义）；参数化条目
        把参数压回 undo 栈并把动作重放施加到当前像素（确定性重放）。"""
        if not doc.redo_stack:
            raise WorkerError(protocol.ERR_UNREDOABLE, f'文档无可重做条目: {doc.document_id}')
        entry = doc.redo_stack.pop()
        if entry.pixels is not None:
            doc.undo_stack.append(HistoryEntry(entry.name, pixels=doc.image.copy(),
                                               replay=entry.replay))
            doc.image = entry.pixels
            return
        new_image = self._replay_apply(doc.image, entry.replay, progress_cb, cancel_token,
                                       baseline=doc.source_image)
        doc.undo_stack.append(HistoryEntry(entry.name, replay=entry.replay))
        doc.image = new_image

    def reset(self, doc: Document, progress_cb: Any = None,
              cancel_token: Any = None) -> None:
        doc.image = doc.source_image.copy()
        doc.undo_stack.clear()
        doc.redo_stack.clear()
        doc.dropped_names.clear()
        doc.modified = False  # 像素回到源图，无未保存修改

    def _replay_state_before(self, doc: Document, progress_cb: Any,
                             cancel_token: Any) -> np.ndarray:
        """重放复原"即将弹出的栈顶条目之前的状态"（参数化 undo 的核心）。

        锚点 = 栈内（除栈顶外）最近的快照条目：从锚点像素出发，依次重放锚点
        自身动作及其上所有参数化条目的动作，直到即将弹出的栈顶条目**之前**
        （重放范围不含栈顶条目自身——它的动作正是要被撤销的）。推送规则
        （`_push_replay_history`）保证锚点的重放参数必在（锚点必为可重放快照
        或基线），且锚点与栈顶之间全为参数化条目——重放路径所需参数完整。
        无快照时锚点为源图基线。
        """
        top_idx = len(doc.undo_stack) - 1  # 即将弹出的条目（重放范围不含它）
        anchor_idx = -1
        for idx in range(top_idx - 1, -1, -1):
            if doc.undo_stack[idx].pixels is not None:
                anchor_idx = idx
                break
        if anchor_idx >= 0:
            state = doc.undo_stack[anchor_idx].pixels
            replay_entries = doc.undo_stack[anchor_idx:top_idx]
        else:
            state = doc.source_image
            replay_entries = doc.undo_stack[:top_idx]
        for entry in replay_entries:
            if cancel_token is not None:
                cancel_token.raise_if_cancelled()
            state = self._replay_apply(state, entry.replay, progress_cb, cancel_token,
                                       baseline=doc.source_image)
        return state

    def _replay_apply(self, state: np.ndarray, replay: dict[str, Any],
                      progress_cb: Any, cancel_token: Any,
                      baseline: np.ndarray | None = None) -> np.ndarray:
        """按载荷类别重放单个动作。adjust：逐段 adjust_chain（确定性浮点管线，
        与原应用 bitwise 一致）；chain：重建 FilterChain 走既有运行器（复用
        filter_adapter，函数级延迟导入避免模块循环）；transform：组合参数变换
        重放（apply_composite_transform，确定性几何函数）；annotate：标注 ops
        重放（apply_annotate——eraser 需要源图基线，故 baseline 必须随行）。
        baseline 为源图 open 态像素（undo/redo 的重放基线，由调用方传入）。"""
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()
        if replay is None:
            # 重放路径遇到无参数条目：推送规则保证不可达（不可重放快照之上
            # 不会有参数化条目）；防御性显式失败，绝不静默跳过产生错误像素。
            raise WorkerError(protocol.ERR_INTERNAL, '重放路径缺少动作参数')
        kind = replay.get('kind')
        if kind == 'adjust':
            for adjustments in replay['applies']:
                if cancel_token is not None:
                    cancel_token.raise_if_cancelled()
                state = adjust_chain(state, adjustments)
            return state
        if kind == 'chain':
            from . import filter_adapter  # 延迟导入：filter_adapter 顶层 import 本模块

            def _step_progress(done: int) -> None:
                if progress_cb is not None:
                    progress_cb(45 + int(done * 40 / 100), '重放滤镜链')

            chain = filter_adapter.build_chain(replay['steps'])
            return filter_adapter.run_chain(state, chain, _step_progress, cancel_token)
        if kind == 'transform':
            if cancel_token is not None:
                cancel_token.raise_if_cancelled()
            return apply_composite_transform(state, replay['ops'])
        if kind == 'annotate':
            if baseline is None:
                # eraser 需要源图基线像素；调用方（undo/redo）恒传入
                # doc.source_image，此处缺失属内部不变量被破坏，显式失败。
                raise WorkerError(protocol.ERR_INTERNAL, '重放路径缺少标注基线')

            def _annotate_progress(value: int, message: str = '') -> None:
                if progress_cb is not None:
                    progress_cb(min(99, 45 + int(value * 40 / 100)), f'重放标注（{message}）')

            return apply_annotate(state, replay['ops'], baseline,
                                  _annotate_progress, cancel_token)
        raise WorkerError(protocol.ERR_INTERNAL, f'未知重放载荷类别: {kind}')

    def history(self, doc: Document) -> dict[str, Any]:
        """image.history（sync）的结果：entries + current + canUndo/canRedo。

        条目与可达状态一一对应（§3.3）：
        - 无深度淘汰：entries[i+1] 沿用 undo_stack[i] 的动作名（原规则）。
        - 有深度淘汰：底条目钉在源图上（undo 它 = open），其上的第一个幸存
          快照由最后一个被淘汰的动作产生，故 entries[1] 取 dropped_names[-1]，
          其后沿用幸存条目自身的动作名；底条目被 undo 后（栈空）其重做条目
          已按同一名规则改名，redo 分支自然对齐，dropped_names 亦随改名清空
          （命名职责移至复合 redo 条目）——因此本分支的 undo_stack[0] 恒为
          钉桩/幸存底条目，不会吞掉其后新动作的条目名。
        - redo 分支按重做顺序排列（redo_stack[-1] 最先被重做），保证
          "点击条目 = 连续 undo/redo"落到的像素与条目名一致。
        - 合并（coalescing）与参数化不改变本表形状：合并后的连续 adjust 只占
          一条（名字仍为 image.adjust），参数化链条目的名字仍为 filter.apply。
        """
        entries: list[dict[str, Any]] = [{'index': 0, 'name': 'open'}]
        if doc.dropped_names and doc.undo_stack:
            entries.append({'index': 1, 'name': doc.dropped_names[-1]})
            entries.extend({'index': i + 2, 'name': entry.name}
                           for i, entry in enumerate(doc.undo_stack[1:]))
        else:
            entries.extend({'index': i + 1, 'name': entry.name}
                           for i, entry in enumerate(doc.undo_stack))
        for j, entry in enumerate(reversed(doc.redo_stack)):
            entries.append({'index': len(doc.undo_stack) + j + 1, 'name': entry.name})
        return {
            'entries': entries,
            'current': len(doc.undo_stack),
            'canUndo': len(doc.undo_stack) > 0,
            'canRedo': len(doc.redo_stack) > 0,
        }


class DocumentStore(HistoryMixin):
    """线程安全的文档表。Worker 进程内单实例。"""

    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}
        self._lock = threading.Lock()

    def open(self, path: str) -> Document:
        src = Path(path)
        if not src.is_file():
            raise WorkerError('FILE_NOT_FOUND', f'文件不存在: {path}')
        try:
            image = load_image(src)
        except FileNotFoundError as exc:
            raise WorkerError('FILE_NOT_FOUND', f'文件不存在: {path}') from exc
        except Exception as exc:  # PIL/cv2 解码失败的形态过多，统一归一
            raise WorkerError('UNSUPPORTED_FORMAT', f'无法解码图像: {exc}') from exc
        if image is None or getattr(image, 'size', 0) == 0:
            raise WorkerError('UNSUPPORTED_FORMAT', f'解码结果为空: {path}')

        doc = Document(
            document_id=f'doc-{uuid.uuid4().hex[:8]}',
            source=str(src.resolve()),
            image=image,
            format=src.suffix.lower().lstrip('.'),
            source_image=image,
        )
        with self._lock:
            self._docs[doc.document_id] = doc
        return doc

    def get(self, document_id: str) -> Document:
        with self._lock:
            doc = self._docs.get(document_id)
        if doc is None:
            raise WorkerError('UNKNOWN_DOCUMENT', f'文档不存在或已关闭: {document_id}')
        return doc

    def close(self, document_id: str) -> bool:
        with self._lock:
            return self._docs.pop(document_id, None) is not None

    def close_all(self) -> None:
        with self._lock:
            self._docs.clear()

    def save(self, document_id: str, path: str, quality: int | None = None,
             target_kb: int | None = None,
             cancel_token: Any = None) -> dict[str, Any]:
        """image.save 任务体（协议 §3）：quality 直通 save_image；target_kb
        给定时二分 JPEG/WebP quality（保 alpha 用 WebP，§3.9），响应附加
        {quality, bytes}。扩展名/alpha 校验已在 dispatcher 提交前完成
        （validate_save_target），此处只负责搜索与落盘。"""
        doc = self.get(document_id)
        target = Path(path)
        try:
            if target_kb is not None:
                found_quality, _probe = search_quality_for_target(
                    doc.image, target.suffix.lower(), int(target_kb) * 1024, cancel_token)
                save_image(doc.image, target, quality=found_quality)
                file_size = target.stat().st_size
                # bytes 与 file_size 同源（落盘后的真实大小；探测值不返回，
                # 以磁盘为准，不谎报估计值）。
                return {'saved': True, 'path': str(target), 'file_size': file_size,
                        'quality': found_quality, 'bytes': file_size}
            kwargs = {'quality': quality} if quality is not None else {}
            saved = save_image(doc.image, target, **kwargs)
        except (WorkerError, CancelledError):
            raise  # 协议错误与协作取消原样上抛（取消归一为 CANCELLED，§7）
        except Exception as exc:
            raise WorkerError('ENGINE_ERROR', f'保存失败: {exc}') from exc
        return {'saved': True, 'path': str(saved), 'file_size': saved.stat().st_size}


# ---- image.adjust / image.transform 的处理器串联（docs/ipc-protocol.md §3.2）----

# 协议九键 → 旧 app 调整面板的顺序与默认值（app/main_window.py:730-740）。
# 高光/阴影在旧 app 是两个独立步骤（各自把另一参数置 0），此处保持逐步串联。
_ADJUST_STEPS: tuple[tuple[str, float, Any], ...] = (
    ('brightness', 0.0, image_core.brightness),
    ('contrast', 0.0, image_core.contrast),
    ('saturation', 0.0, image_core.saturation),
    ('gamma', 1.0, image_core.gamma),
    ('exposure', 0.0, image_core.exposure),
    ('hue', 0.0, image_core.hue_shift),
    ('vibrance', 0.0, image_core.vibrance),
    ('highlights', 0.0, lambda img, value: image_core.highlights_shadows(img, value, 0.0)),
    ('shadows', 0.0, lambda img, value: image_core.highlights_shadows(img, 0.0, value)),
)

# 协议 op → 必需参数键（§3.2 op/params 对应表）。
TRANSFORM_REQUIRED_PARAMS: dict[str, tuple[str, ...]] = {
    'rotate': ('angle',),
    'flip_h': (),
    'flip_v': (),
    'scale': ('sx',),
    'crop': ('x', 'y', 'w', 'h'),
}

# image.adjust 的九个合法调整键（供 dispatcher 做提交前校验）。
ADJUST_KEYS: frozenset[str] = frozenset(step[0] for step in _ADJUST_STEPS)


def adjust_chain(img: np.ndarray, adjustments: dict[str, float]) -> np.ndarray:
    """按旧 app `_apply_adjust_chain`（app/main_window.py:836-846）的顺序串联调整。

    - 只应用用户提供的键；与默认值差 ≤ 1e-6 的键跳过（避免无谓的全图浮点遍历，
      对齐旧 app `_adjust_changed` 的 no-op 剪枝）。
    - 第一个实际执行的步骤接收 img.copy()，后续步骤接收前一步结果；
      无任何实际执行的步骤时返回 img.copy()（永不原地修改输入）。
    """
    current: np.ndarray | None = None
    for key, default, func in _ADJUST_STEPS:
        if key not in adjustments:
            continue
        value = float(adjustments[key])
        if abs(value - default) <= 1e-6:
            continue
        current = func(img.copy() if current is None else current, value)
    return img.copy() if current is None else current


def apply_transform(img: np.ndarray, op: str, params: dict[str, Any]) -> np.ndarray:
    """按 op 调用 processors.core 的几何变换原语（全部为函数式，返回新数组）。"""
    if op == 'rotate':
        return image_core.rotate(img, float(params['angle']))
    if op == 'flip_h':
        return image_core.flip_h(img)
    if op == 'flip_v':
        return image_core.flip_v(img)
    if op == 'scale':
        return image_core.scale(img, float(params['sx']))
    if op == 'crop':
        return image_core.crop(img, int(params['x']), int(params['y']),
                               int(params['w']), int(params['h']))
    raise WorkerError('INVALID_PARAMS', f'未知变换 op: {op}')


# ---- image.transform 组合参数（Phase 9，docs/ipc-protocol.md §3.2 增补）------
#
# 与既有 op/params 形式互斥的顶层可选参数：crop / rotate_free / perspective /
# scale。组合链固定为 crop → rotate_free → scale（perspective 为独立几何变换，
# 不参与组合）。全部为确定性函数（同输入同参数 → bitwise 同输出），因此全分辨
# 率应用以"快照 + replay"入历史（可重放锚点），undo/redo 参数化复用。
# 既有 op/params 形式语义不变，仍为无 replay 的快照条目（重放屏障）。

COMPOSITE_TRANSFORM_KEYS: tuple[str, ...] = ('crop', 'rotate_free', 'perspective', 'scale')
RESAMPLE_CHOICES: tuple[str, ...] = ('lanczos', 'bilinear', 'nearest', 'bicubic')

# 协议 resample 词表 → image_core.resize 的 interpolation 词表（bicubic 在
# core 里叫 cubic；lanczos/bilinear/nearest 同名直通）。
_RESAMPLE_TO_CORE = {'lanczos': 'lanczos', 'bilinear': 'bilinear',
                     'nearest': 'nearest', 'bicubic': 'cubic'}


def _spec_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise WorkerError('INVALID_PARAMS', f'{label} 必须是有限数值')
    return float(value)


def _spec_int(value: Any, label: str) -> int:
    number = _spec_number(value, label)
    if not number.is_integer():
        raise WorkerError('INVALID_PARAMS', f'{label} 必须是整数')
    return int(number)


def _spec_member(raw: dict, key: str, label: str) -> Any:
    if key not in raw:
        raise WorkerError('INVALID_PARAMS', f'{label} 缺少参数: {key}')
    return raw[key]


def _spec_point(pair: Any, label: str) -> list[float]:
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        raise WorkerError('INVALID_PARAMS', f'{label} 必须是 [x, y] 两元素数组')
    return [_spec_number(pair[0], f'{label}.x'), _spec_number(pair[1], f'{label}.y')]


def validate_transform_spec(params: dict[str, Any], image_w: int, image_h: int) -> dict[str, Any] | None:
    """新式 image.transform 顶层组合参数校验（§3.2 Phase 9 增补）。

    无任何组合键时返回 None（调用方回退既有 op/params 路径）；有组合键时
    返回归一化 spec（仅含出现的键，值均为 JSON 形状，可直接进历史 replay）。
    crop 负值/越界、rotate_free 角度越界（|angle| > 180）、perspective 四点
    形状非法、scale 取值非法 → INVALID_PARAMS。perspective 为独立变换，
    与其它组合键并存 → INVALID_PARAMS。
    """
    if not isinstance(params, dict):
        raise WorkerError('INVALID_PARAMS', 'params 必须是对象')
    present = [key for key in COMPOSITE_TRANSFORM_KEYS if key in params]
    if not present:
        return None
    if 'perspective' in params and len(present) > 1:
        raise WorkerError('INVALID_PARAMS',
                          'perspective 为独立变换，不能与 crop/rotate_free/scale 组合')
    spec: dict[str, Any] = {}

    if 'crop' in params:
        raw = params['crop']
        if not isinstance(raw, dict):
            raise WorkerError('INVALID_PARAMS', 'crop 必须是对象')
        x = _spec_int(_spec_member(raw, 'x', 'crop'), 'crop.x')
        y = _spec_int(_spec_member(raw, 'y', 'crop'), 'crop.y')
        width = _spec_int(_spec_member(raw, 'width', 'crop'), 'crop.width')
        height = _spec_int(_spec_member(raw, 'height', 'crop'), 'crop.height')
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise WorkerError('INVALID_PARAMS', 'crop 的 x/y 须非负且 width/height > 0')
        if x + width > int(image_w) or y + height > int(image_h):
            raise WorkerError('INVALID_PARAMS', 'crop 矩形超出图像范围')
        spec['crop'] = {'x': x, 'y': y, 'width': width, 'height': height}

    if 'rotate_free' in params:
        raw = params['rotate_free']
        if not isinstance(raw, dict):
            raise WorkerError('INVALID_PARAMS', 'rotate_free 必须是对象')
        angle = _spec_number(_spec_member(raw, 'angle', 'rotate_free'), 'rotate_free.angle')
        if not -180.0 <= angle <= 180.0:
            raise WorkerError('INVALID_PARAMS', 'rotate_free.angle 须在 -180..180（度）')
        expand = raw.get('expand', True)
        if not isinstance(expand, bool):
            raise WorkerError('INVALID_PARAMS', 'rotate_free.expand 必须是布尔值')
        spec['rotate_free'] = {'angle': angle, 'expand': expand}

    if 'perspective' in params:
        raw = params['perspective']
        if not isinstance(raw, dict):
            raise WorkerError('INVALID_PARAMS', 'perspective 必须是对象')
        corners_raw = _spec_member(raw, 'corners', 'perspective')
        if not isinstance(corners_raw, (list, tuple)) or len(corners_raw) != 4:
            raise WorkerError('INVALID_PARAMS', 'perspective.corners 必须是 [x,y]×4 数组')
        corners = [_spec_point(pair, f'perspective.corners[{i}]')
                   for i, pair in enumerate(corners_raw)]
        spec['perspective'] = {'corners': corners}

    if 'scale' in params:
        raw = params['scale']
        if not isinstance(raw, dict):
            raise WorkerError('INVALID_PARAMS', 'scale 必须是对象')
        width = _spec_int(_spec_member(raw, 'width', 'scale'), 'scale.width')
        height = _spec_int(_spec_member(raw, 'height', 'scale'), 'scale.height')
        if width <= 0 or height <= 0:
            raise WorkerError('INVALID_PARAMS', 'scale 的 width/height 必须 > 0')
        resample = raw.get('resample', 'lanczos')
        if resample not in RESAMPLE_CHOICES:
            raise WorkerError('INVALID_PARAMS',
                              f'scale.resample 须为 {"|".join(RESAMPLE_CHOICES)} 之一')
        spec['scale'] = {'width': width, 'height': height, 'resample': resample}

    return spec


def apply_composite_transform(img: np.ndarray, spec: dict[str, Any]) -> np.ndarray:
    """按 crop → rotate_free → (perspective) → scale 顺序应用组合变换。

    校验保证 perspective 不与其它键并存（独立几何变换）。引擎选择：crop 复用
    image_core.crop（已校验参数，钳制分支不触发）、scale 复用 image_core.resize
    （resample 词表映射）；自由旋转与透视在适配层实现——core.rotate 只覆盖
    扩张画布的仿射旋转（BORDER_REFLECT/CONSTANT 填充），无 expand=False 与
    投影变换资产，此处用 PIL Image.rotate / cv2 warpPerspective 补齐。全部为
    函数式，返回新数组，不修改 img。
    """
    current = img
    if 'crop' in spec:
        c = spec['crop']
        current = image_core.crop(current, c['x'], c['y'], c['width'], c['height'])
    if 'rotate_free' in spec:
        current = _rotate_free(current, spec['rotate_free'])
    if 'perspective' in spec:
        current = _perspective_warp(current, spec['perspective']['corners'])
    if 'scale' in spec:
        s = spec['scale']
        current = image_core.resize(current, s['width'], s['height'], keep_aspect=False,
                                    interpolation=_RESAMPLE_TO_CORE[s['resample']])
    return current


def _rotate_free(img: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """PIL 自由旋转（正角逆时针，与既有 op=rotate 的 cv2 约定一致）。

    expand=true 画布扩到包容整图，expand=false 保持原尺寸（越出部分裁掉）；
    露出的底面：RGBA 透明、RGB 黑（PIL 缺省 0 填充）。BICUBIC 重采样确定性
    可重放。
    """
    from PIL import Image  # 延迟导入（filter_adapter.write_preview 同款）

    rotated = np_to_pil(img).rotate(params['angle'], expand=bool(params['expand']),
                                    resample=Image.Resampling.BICUBIC)
    return np.array(rotated)


def _perspective_warp(img: np.ndarray, corners: list[list[float]]) -> np.ndarray:
    """透视变换：文档四角 (0,0)/(w,0)/(w,h)/(0,h)（左上起顺时针）映射到
    corners[0..3]；输出画布 = 目标四点外接矩形（上取整），负坐标平移回原点。
    填充与 op=rotate 同约定：RGBA 透明、RGB 邻域反射。"""
    h, w = img.shape[:2]
    src = np.array([[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]], dtype=np.float32)
    dst = np.array(corners, dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    x_min, y_min = float(dst[:, 0].min()), float(dst[:, 1].min())
    x_max, y_max = float(dst[:, 0].max()), float(dst[:, 1].max())
    out_w = max(1, int(math.ceil(x_max - x_min)))
    out_h = max(1, int(math.ceil(y_max - y_min)))
    shift = np.array([[1.0, 0.0, -x_min], [0.0, 1.0, -y_min], [0.0, 0.0, 1.0]])
    border = (cv2.BORDER_CONSTANT if img.ndim == 3 and img.shape[2] == 4
              else cv2.BORDER_REFLECT)
    return cv2.warpPerspective(img, (shift @ matrix).astype(np.float32), (out_w, out_h),
                               flags=cv2.INTER_LINEAR, borderMode=border)


# ---- image.annotate（Phase 9，docs/ipc-protocol.md §3.9）--------------------
#
# 标注 ops 在文档像素上依序应用（PIL ImageDraw / ImageFilter）。ops 全量校验在
# dispatcher 提交任务前完成（validate_annotate_ops），归一化结果序列化进历史
# 条目（参数化 replay：undo 从锚点重绘 ops 前缀，复用既有参数化 undo 机制）。

ANNOTATE_OP_TYPES: tuple[str, ...] = ('pen', 'text', 'rect', 'ellipse', 'arrow',
                                      'blur_rect', 'pixelate_rect', 'eraser')
_ANNOTATE_OP_SET = frozenset(ANNOTATE_OP_TYPES)

# 颜色词汇与 generate_adapter 的协议色一致（§3.7 Phase 6C 复查注）：[r,g,b]
# 整数数组或 #RGB/#RRGGBB hex 文本；标注另接受第 4 分量 alpha（[r,g,b,a] /
# #RRGGBBAA），缺省不透明。
_ANNOTATE_HEX_COLOR = re.compile(r'#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})')

_TEXT_FONT_SIZE_MAX = 512    # 上限防呆：超大字号在 PIL 里按像素光栅化，防内存
_BLUR_STRENGTH_MAX = 100.0   # GaussianBlur radius 上限（秒级耗时防线）


def _annotate_color(value: Any, label: str) -> tuple[int, int, int, int]:
    """标注颜色归一为 (r, g, b, a)；非法形状/越界分量 → INVALID_PARAMS。"""
    if isinstance(value, str):
        text = value.strip()
        if not _ANNOTATE_HEX_COLOR.fullmatch(text):
            raise WorkerError('INVALID_PARAMS',
                              f'{label} 颜色非法: {value!r}（须为 [r,g,b(,a)] 或 #RGB/#RRGGBB/#RRGGBBAA）')
        digits = text[1:]
        if len(digits) == 3:
            digits = ''.join(c * 2 for c in digits)
        components = [int(digits[i:i + 2], 16) for i in range(0, len(digits), 2)]
    elif isinstance(value, (list, tuple)) and len(value) in (3, 4):
        components = []
        for component in value:
            if isinstance(component, bool) or not isinstance(component, int) \
                    or not 0 <= component <= 255:
                raise WorkerError('INVALID_PARAMS', f'{label} 颜色分量须为 0-255 整数')
            components.append(int(component))
    else:
        raise WorkerError('INVALID_PARAMS',
                          f'{label} 颜色非法: {value!r}（须为 [r,g,b(,a)] 或 #RGB/#RRGGBB/#RRGGBBAA）')
    if len(components) == 3:
        components.append(255)
    return tuple(components)


def _annotate_points(value: Any, label: str) -> list[list[float]]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise WorkerError('INVALID_PARAMS', f'{label} 至少需要 2 个点')
    return [_spec_point(pair, f'{label}[{i}]') for i, pair in enumerate(value)]


def _annotate_stroke_width(value: Any, label: str) -> int:
    width = _spec_int(value, label)
    if width < 1:
        raise WorkerError('INVALID_PARAMS', f'{label} 必须 ≥ 1')
    return width


def _annotate_rect(value: Any, label: str, image_w: int, image_h: int,
                   require_intersect: bool) -> dict[str, float]:
    """rect/ellipse/blur_rect/pixelate_rect 的 {x,y,width,height} 公共校验。

    绘制类（rect/ellipse）允许部分越界（PIL 自动裁剪）；区域类（blur/pixelate）
    区域按图像边界裁剪，完全在图像外 → INVALID_PARAMS（不谎报处理了不可见
    区域）。"""
    if not isinstance(value, dict):
        raise WorkerError('INVALID_PARAMS', f'{label} 必须是对象')
    x = _spec_number(_spec_member(value, 'x', label), f'{label}.x')
    y = _spec_number(_spec_member(value, 'y', label), f'{label}.y')
    width = _spec_number(_spec_member(value, 'width', label), f'{label}.width')
    height = _spec_number(_spec_member(value, 'height', label), f'{label}.height')
    if width <= 0 or height <= 0:
        raise WorkerError('INVALID_PARAMS', f'{label} 的 width/height 必须 > 0')
    if require_intersect:
        x0 = max(0, int(math.floor(x)))
        y0 = max(0, int(math.floor(y)))
        x1 = min(int(image_w), int(math.ceil(x + width)))
        y1 = min(int(image_h), int(math.ceil(y + height)))
        if x0 >= x1 or y0 >= y1:
            raise WorkerError('INVALID_PARAMS', f'{label} 区域完全在图像外')
    return {'x': x, 'y': y, 'width': width, 'height': height}


def _validate_pen(index: int, op: dict[str, Any], image_w: int, image_h: int) -> dict[str, Any]:
    return {
        'type': 'pen',
        'points': _annotate_points(_spec_member(op, 'points', f'ops[{index}]'), f'ops[{index}].points'),
        'width': _annotate_stroke_width(_spec_member(op, 'width', f'ops[{index}]'), f'ops[{index}].width'),
        'color': list(_annotate_color(_spec_member(op, 'color', f'ops[{index}]'), f'ops[{index}]')),
    }


def _validate_text(index: int, op: dict[str, Any], image_w: int, image_h: int) -> dict[str, Any]:
    label = f'ops[{index}]'
    text = _spec_member(op, 'text', label)
    if not isinstance(text, str) or not text:
        raise WorkerError('INVALID_PARAMS', f'{label}.text 必须是非空字符串')
    font_size = _spec_int(_spec_member(op, 'font_size', label), f'{label}.font_size')
    if not 1 <= font_size <= _TEXT_FONT_SIZE_MAX:
        raise WorkerError('INVALID_PARAMS', f'{label}.font_size 须在 1..{_TEXT_FONT_SIZE_MAX}')
    return {
        'type': 'text',
        'x': _spec_number(_spec_member(op, 'x', label), f'{label}.x'),
        'y': _spec_number(_spec_member(op, 'y', label), f'{label}.y'),
        'text': text,
        'font_size': font_size,
        'color': list(_annotate_color(_spec_member(op, 'color', label), label)),
    }


def _validate_shape(fill_allowed: bool):
    def _validate(index: int, op: dict[str, Any], image_w: int, image_h: int) -> dict[str, Any]:
        label = f'ops[{index}]'
        # 线宽键名说明：矩形/椭圆的几何尺寸是 width/height（§3.9 schema），
        # 描边线宽为可选 stroke_width（缺省 1）——任务书的字面 schema
        # "{x,y,width,height,color,width,fill?}" 出现重复 JSON 键，按"几何
        # width + 描边 stroke_width"消解并在协议文档同步注明。
        stroke_width = op.get('stroke_width', 1)
        validated: dict[str, Any] = {
            'type': op['type'],
            **_annotate_rect(op, label, image_w, image_h, require_intersect=False),
            'stroke_width': _annotate_stroke_width(stroke_width, f'{label}.stroke_width'),
            'color': list(_annotate_color(_spec_member(op, 'color', label), label)),
        }
        if fill_allowed:
            fill = op.get('fill', False)
            if not isinstance(fill, bool):
                raise WorkerError('INVALID_PARAMS', f'{label}.fill 必须是布尔值')
            validated['fill'] = fill
        return validated
    return _validate


def _validate_arrow(index: int, op: dict[str, Any], image_w: int, image_h: int) -> dict[str, Any]:
    label = f'ops[{index}]'
    return {
        'type': 'arrow',
        'x1': _spec_number(_spec_member(op, 'x1', label), f'{label}.x1'),
        'y1': _spec_number(_spec_member(op, 'y1', label), f'{label}.y1'),
        'x2': _spec_number(_spec_member(op, 'x2', label), f'{label}.x2'),
        'y2': _spec_number(_spec_member(op, 'y2', label), f'{label}.y2'),
        'width': _annotate_stroke_width(_spec_member(op, 'width', label), f'{label}.width'),
        'color': list(_annotate_color(_spec_member(op, 'color', label), label)),
    }


def _validate_region(kind: str):
    def _validate(index: int, op: dict[str, Any], image_w: int, image_h: int) -> dict[str, Any]:
        label = f'ops[{index}]'
        validated: dict[str, Any] = {'type': kind,
                                     **_annotate_rect(op, label, image_w, image_h,
                                                      require_intersect=True)}
        if kind == 'blur_rect':
            strength = _spec_number(_spec_member(op, 'strength', label), f'{label}.strength')
            if not 0 < strength <= _BLUR_STRENGTH_MAX:
                raise WorkerError('INVALID_PARAMS',
                                  f'{label}.strength 须在 (0, {_BLUR_STRENGTH_MAX:.0f}]')
            validated['strength'] = strength
        else:
            block = _spec_int(_spec_member(op, 'block', label), f'{label}.block')
            if block < 2:
                raise WorkerError('INVALID_PARAMS', f'{label}.block 必须 ≥ 2')
            validated['block'] = block
        return validated
    return _validate


def _validate_eraser(index: int, op: dict[str, Any], image_w: int, image_h: int) -> dict[str, Any]:
    label = f'ops[{index}]'
    return {
        'type': 'eraser',
        'points': _annotate_points(_spec_member(op, 'points', label), f'{label}.points'),
        'width': _annotate_stroke_width(_spec_member(op, 'width', label), f'{label}.width'),
    }


_ANNOTATE_VALIDATORS = {
    'pen': _validate_pen,
    'text': _validate_text,
    'rect': _validate_shape(True),
    'ellipse': _validate_shape(True),
    'arrow': _validate_arrow,
    'blur_rect': _validate_region('blur_rect'),
    'pixelate_rect': _validate_region('pixelate_rect'),
    'eraser': _validate_eraser,
}


def validate_annotate_ops(raw: Any, image_w: int, image_h: int) -> list[dict[str, Any]]:
    """image.annotate 的 ops 校验（§3.9）：逐项形状/取值校验并归一化。

    返回值是仅含协议字段的可 JSON 化深拷贝（序列化进历史条目的就是它）；
    未知 type、缺参数、取值越界 → INVALID_PARAMS（消息带 ops 下标）。坐标
    一律为原图像素坐标（原点左上）。
    """
    if not isinstance(raw, list) or not raw:
        raise WorkerError('INVALID_PARAMS', 'ops 必须是非空数组')
    validated: list[dict[str, Any]] = []
    for index, op in enumerate(raw):
        if not isinstance(op, dict):
            raise WorkerError('INVALID_PARAMS', f'ops[{index}] 必须是对象')
        op_type = op.get('type')
        if op_type not in _ANNOTATE_OP_SET:
            raise WorkerError('INVALID_PARAMS', f'ops[{index}] 未知标注类型: {op_type!r}')
        validated.append(_ANNOTATE_VALIDATORS[op_type](index, op, image_w, image_h))
    return validated


def _annotate_font(size: int):
    """标注字体：候选链复用 processors/filters.py _watermark_font（MiSans →
    Noto CJK → DejaVu → PIL 内置，中英文字形与水印一致）。PIL 内置位图字体
    不随 size 缩放：Pillow ≥ 10.1 用 load_default(size=…) 按字号取点阵。"""
    from PIL import ImageFont
    from processors.filters import _watermark_font

    font = _watermark_font(size)
    if isinstance(font, ImageFont.FreeTypeFont):
        return font
    try:
        return ImageFont.load_default(size=int(size))  # Pillow ≥ 10.1
    except TypeError:
        return font


def _blend_draw(canvas, paint):
    """alpha < 255 的绘制路径：不透明画在透明 RGBA 图层上再整体 alpha_composite。

    RGB 画布经 RGBA 往返（alpha 恒 255，通道值无损）；paint(draw) 在给定
    ImageDraw 上完成不透明绘制。"""
    from PIL import Image, ImageDraw

    layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    paint(ImageDraw.Draw(layer))
    if canvas.mode == 'RGBA':
        return Image.alpha_composite(canvas, layer)
    return Image.alpha_composite(canvas.convert('RGBA'), layer).convert(canvas.mode)


def _draw_round_caps(draw, points: list[tuple[float, float]], width: int, color) -> None:
    """笔触圆头端点（PIL line 端帽是平的，标注笔需圆头）。"""
    radius = width / 2.0
    for x, y in (points[0], points[-1]):
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color)


def _clip_region(rect: dict[str, float], width: int, height: int) -> tuple[int, int, int, int]:
    """区域 op 的整数像素范围（校验已保证与图像相交，非空）。"""
    x0 = max(0, int(math.floor(rect['x'])))
    y0 = max(0, int(math.floor(rect['y'])))
    x1 = min(int(width), int(math.ceil(rect['x'] + rect['width'])))
    y1 = min(int(height), int(math.ceil(rect['y'] + rect['height'])))
    return x0, y0, x1, y1


def apply_annotate(img: np.ndarray, ops: list[dict[str, Any]], baseline: np.ndarray | None,
                   progress_cb: Any = None, cancel_token: Any = None) -> np.ndarray:
    """在文档像素副本上依序应用标注 ops（§3.9；函数式，不修改 img/baseline）。

    坐标一律为当前画布像素坐标（原点左上，PIL 裁剪越界绘制）。颜色不透明时
    直接绘制（替换像素）；带 alpha 时经透明图层 alpha_composite 混色（图层恒
    为 RGBA、恒用 4 元组墨水——RGB 画布无例外，混色后按画布模式转回）。eraser
    把笔画覆盖的像素恢复为 baseline（源图 open 态）像素——baseline 与当前画布
    通道数不一致（源图恒 RGBA、adjust 后画布为 RGB）时按基线前 C 通道恢复；
    几何不一致（open 后发生过 crop/scale 等几何变换）时不恢复（笔画区域保持
    本动作应用前像素，仅可擦除同批次更早 ops 的绘制结果）。
    """
    from PIL import Image, ImageDraw, ImageFilter  # 延迟导入（write_preview 同款）

    pil = np_to_pil(img)
    if pil.mode not in ('RGB', 'RGBA'):
        # Worker 打开的文档恒为 RGBA（processors/utils.py pil_to_np）、adjust
        # 后为 RGB；其余模式不在协议面（防御性拒绝，绝不静默错绘）。
        raise WorkerError('INVALID_PARAMS', f'标注不支持的图像模式: {pil.mode}')
    # np_to_pil（Image.fromarray）与 numpy 缓冲共享内存：先复制，保证不写入
    # doc.image（历史快照与源图都在别名保护之内）。
    canvas = pil.copy()
    baseline_arr = None if baseline is None else np.asarray(baseline)

    total = len(ops)
    for index, op in enumerate(ops):
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()
        canvas = _apply_annotate_op(canvas, op, baseline_arr, Image, ImageDraw, ImageFilter)
        if progress_cb is not None:
            progress_cb(10 + int(75 * (index + 1) / total), f'应用标注 {index + 1}/{total}')
    return np.array(canvas)


def _apply_annotate_op(canvas, op: dict[str, Any], baseline_arr: np.ndarray | None,
                       Image, ImageDraw, ImageFilter):
    """单个标注 op（canvas 为 Worker 自有的 PIL 副本，可原地绘制）。"""
    op_type = op['type']
    color = tuple(op['color']) if 'color' in op else None
    alpha = color[3] if color else 255
    # 墨水选择：alpha < 255 的绘制发生在 _blend_draw 的透明 RGBA 图层上——
    # 恒用完整 4 元组（3 元组在图层上等价 alpha=255，alpha_composite 后
    # 半透明语义退化为不透明落笔；§3.9 alpha 混色无 RGB 画布例外）。
    # alpha == 255 直绘画布：RGBA 画布携带 alpha 通道绘制；RGB 画布剥离为
    # 三元组（4 元组在 RGB 画布上不是合法颜色）。无色 op（eraser/blur_rect/
    # pixelate_rect，校验器不注入 color）不取墨水：RGB 画布上 color 为 None，
    # color[:3] 不可求值（'NoneType' object is not subscriptable —— CI 上
    # eraser-after-adjust 即因此 task.failed）；此类 op 也不用墨水。
    paint_color = None
    if color is not None:
        paint_color = color if (alpha < 255 or canvas.mode == 'RGBA') else color[:3]

    def _paint(paint_fn) -> None:
        if alpha < 255:
            replaced = _blend_draw(canvas, paint_fn)
            canvas.paste(replaced, (0, 0))
        else:
            paint_fn(ImageDraw.Draw(canvas))

    if op_type == 'pen':
        points = [(p[0], p[1]) for p in op['points']]

        def paint(draw):
            draw.line(points, fill=paint_color, width=op['width'], joint='curve')
            _draw_round_caps(draw, points, op['width'], paint_color)
        _paint(paint)
        return canvas

    if op_type == 'text':
        font = _annotate_font(op['font_size'])

        def paint(draw):
            draw.text((op['x'], op['y']), op['text'], font=font, fill=paint_color)
        _paint(paint)
        return canvas

    if op_type in ('rect', 'ellipse'):
        x, y, w, h = op['x'], op['y'], op['width'], op['height']
        stroke = op['stroke_width']

        def paint(draw):
            if op_type == 'rect':
                draw.rectangle([x, y, x + w, y + h],
                               fill=paint_color if op['fill'] else None,
                               outline=paint_color, width=stroke)
            else:
                draw.ellipse([x, y, x + w, y + h],
                             fill=paint_color if op['fill'] else None,
                             outline=paint_color, width=stroke)
        _paint(paint)
        return canvas

    if op_type == 'arrow':
        x1, y1, x2, y2 = op['x1'], op['y1'], op['x2'], op['y2']

        def paint(draw):
            draw.line([(x1, y1), (x2, y2)], fill=paint_color, width=op['width'])
            # 箭头头部：两段线与前进方向成 ±150°（张角 60°），长度
            # max(6, 3×width)——确定性几何，文档与测试锁定同一公式。
            head = max(6.0, 3.0 * op['width'])
            base_angle = math.atan2(y2 - y1, x2 - x1)
            for offset in (math.radians(150), -math.radians(150)):
                hx = x2 + head * math.cos(base_angle + offset)
                hy = y2 + head * math.sin(base_angle + offset)
                draw.line([(x2, y2), (hx, hy)], fill=paint_color, width=op['width'])
        _paint(paint)
        return canvas

    if op_type == 'blur_rect':
        x0, y0, x1, y1 = _clip_region(op, canvas.width, canvas.height)
        region = canvas.crop((x0, y0, x1, y1))
        canvas.paste(region.filter(ImageFilter.GaussianBlur(radius=op['strength'])), (x0, y0))
        return canvas

    if op_type == 'pixelate_rect':
        x0, y0, x1, y1 = _clip_region(op, canvas.width, canvas.height)
        region = canvas.crop((x0, y0, x1, y1))
        region_w, region_h = region.size
        block = op['block']
        small = region.resize((max(1, region_w // block), max(1, region_h // block)),
                              Image.Resampling.NEAREST)
        canvas.paste(small.resize((region_w, region_h), Image.Resampling.NEAREST), (x0, y0))
        return canvas

    if op_type == 'eraser':
        working = np.array(canvas)
        baseline_matched = None
        if baseline_arr is not None and baseline_arr.shape[:2] == working.shape[:2]:
            # 几何一致即可恢复；通道数不一致时按基线前 C 通道对齐（源图恒
            # RGBA 4ch——processors/utils.py pil_to_np，adjust 后画布为 RGB
            # 3ch，RGB 分量逐位对应、语义良定义）。画布通道多于基线（基线
            # 缺通道）时无法合成缺失通道，保持降级不恢复。
            if baseline_arr.ndim == 3 and working.ndim == 3 \
                    and baseline_arr.shape[2] >= working.shape[2]:
                baseline_matched = baseline_arr[:, :, :working.shape[2]]
        if baseline_matched is not None:
            mask = Image.new('L', canvas.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            points = [(p[0], p[1]) for p in op['points']]
            mask_draw.line(points, fill=255, width=op['width'], joint='curve')
            _draw_round_caps(mask_draw, points, op['width'], 255)
            selected = np.asarray(mask) > 0
            working[selected] = baseline_matched[selected]
            return Image.fromarray(working, mode=canvas.mode)
        # 基线不可用（None / 与当前画布几何不一致 / 通道数不足）：不恢复，
        # 笔画区域保持本动作应用前像素（语义见 apply_annotate docstring）。
        return canvas

    raise WorkerError(protocol.ERR_INTERNAL, f'未知标注类型: {op_type}')


# ---- image.save target_kb（Phase 9，docs/ipc-protocol.md §3.9）--------------
#
# 二分 JPEG/WebP quality 使编码字节 ≤ target_kb；quality 下限 30。探测编码
# 与 save_image 的 jpg/webp 分支同参（optimize/method），保证搜索结果与最终
# 落盘一致。

SAVE_TARGET_MIN_QUALITY = 30
SAVE_TARGET_MAX_QUALITY = 100
_TARGET_EXTS = frozenset({'.jpg', '.jpeg', '.webp'})


def validate_save_target(image: np.ndarray, path: str, target_kb: int) -> None:
    """target_kb 的提交前校验（§3.9）：仅 JPEG/WebP 有损编码适用；含 alpha
    通道的文档不能落 JPEG（透明度会失真/报错），保 alpha 用 WebP。"""
    ext = Path(path).suffix.lower()
    if ext not in _TARGET_EXTS:
        raise WorkerError('INVALID_PARAMS',
                          f'target_kb 仅适用于 JPEG/WebP 输出，得到扩展名: {ext or "(无)"}')
    if image.ndim == 3 and image.shape[2] == 4 and ext in ('.jpg', '.jpeg'):
        raise WorkerError('INVALID_PARAMS',
                          '文档含 alpha 通道，JPEG 无法保存透明度；请保存为 WebP（§3.9）')


def encode_image_size(image: np.ndarray, ext: str, quality: int) -> int:
    """内存编码后的字节数（探测用）：kwargs 与 processors/utils.save_image 的
    jpg/webp 分支完全一致，保证探测与最终落盘同参同大小。"""
    buffer = io.BytesIO()
    pil = np_to_pil(image)
    ext = ext.lower()
    if ext in ('.jpg', '.jpeg'):
        pil.save(buffer, format='JPEG', quality=int(quality), optimize=True)
    elif ext == '.webp':
        pil.save(buffer, format='WEBP', quality=int(quality), method=4)
    else:
        raise WorkerError('INVALID_PARAMS', f'target_kb 仅支持 JPEG/WebP 输出: {ext}')
    return buffer.tell()


def search_quality_for_target(image: np.ndarray, ext: str, target_bytes: int,
                              cancel_token: Any = None) -> tuple[int, int]:
    """二分满足 target_bytes 的最大 quality（闭区间 [30, 100]）。

    JPEG/WebP 编码大小对 quality 单调不降，二分收敛（≤7 次探测）。下限 30
    仍超 target 时返回 (30, encode(30))——调用方按该质量落盘并在响应如实
    返回实际字节（不失败、不谎报达标）。返回 (quality, 探测字节数)。
    """
    low, high = SAVE_TARGET_MIN_QUALITY, SAVE_TARGET_MAX_QUALITY
    best: tuple[int, int] | None = None
    while low <= high:
        mid = (low + high) // 2
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()
        size = encode_image_size(image, ext, mid)
        if size <= target_bytes:
            best = (mid, size)
            low = mid + 1
        else:
            high = mid - 1
    if best is None:
        return SAVE_TARGET_MIN_QUALITY, encode_image_size(image, ext, SAVE_TARGET_MIN_QUALITY)
    return best
