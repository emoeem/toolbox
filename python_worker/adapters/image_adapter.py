"""图像文档存储与编辑状态：document_id → 内存 ndarray（协议 §3.1/§3.3/§4）。"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# import processors 触发滤镜注册；core 提供调整/变换原语（复用资产，不重写算法）。
from processors import core as image_core
from processors.utils import load_image, save_image

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
    None（参数化条目）；两者并存仅限携带重放参数的快照条目（image.adjust）——
    - 快照条目（pixels 非 None）：保存该动作**之前**的像素，undo 直达；replay
      为该条目自身动作的重放参数（可无损重放的动作才有，见下），供"重放越过
      本条目"重建其后的参数化条目状态。image.adjust 属于此类（adjustments 可
      确定性重放）；image.transform 属于快照条目但 replay=None（scale/crop 有损，
      参数重放不可靠——重放屏障）。
    - 参数化条目（replay 非 None）：只存动作参数（filter 链 steps），不存像素，
      内存 O(参数)。undo 时从基线/最近快照锚点重放（`_replay_state_before`）。
    replay 载荷形状（Worker 内部策略，非协议字段）：
      {'kind': 'chain', 'steps': <协议 filters 数组>}
      {'kind': 'adjust', 'applies': [<adjustments 对象>, ...]}  # 合并条目为多段
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
        replay 为该动作自身的重放参数（可无损重放时携带，如 image.adjust 的
        adjustments；transform 类不携带——重放屏障，见 HistoryEntry 注）。
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
        new_image = self._replay_apply(doc.image, entry.replay, progress_cb, cancel_token)
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
            state = self._replay_apply(state, entry.replay, progress_cb, cancel_token)
        return state

    def _replay_apply(self, state: np.ndarray, replay: dict[str, Any],
                      progress_cb: Any, cancel_token: Any) -> np.ndarray:
        """按载荷类别重放单个动作。adjust：逐段 adjust_chain（确定性浮点管线，
        与原应用 bitwise 一致）；chain：重建 FilterChain 走既有运行器（复用
        filter_adapter，函数级延迟导入避免模块循环）。"""
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

    def save(self, document_id: str, path: str, quality: int | None = None) -> dict[str, Any]:
        doc = self.get(document_id)
        target = Path(path)
        try:
            kwargs = {'quality': quality} if quality is not None else {}
            saved = save_image(doc.image, target, **kwargs)
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
