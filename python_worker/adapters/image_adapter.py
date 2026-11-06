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
class Document:
    document_id: str
    source: str
    image: np.ndarray
    format: str = ''
    modified: bool = False
    extras: dict[str, Any] = field(default_factory=dict)
    # 编辑状态（docs/ipc-protocol.md §3.1）：version 从 0 起，全分辨率变更成功后 +1。
    version: int = 0
    # 源图引用（reset 的恢复目标）。与 image 暂指同一对象：processors 均为函数式
    # （返回新数组，不原地修改），首次变更前 push_history 已做 .copy()，别名安全。
    source_image: np.ndarray | None = None
    # 历史栈（docs/ipc-protocol.md §3.3）：(动作名, 变更前的像素快照)。
    # undo_stack[-1] 是最近一次全分辨率变更的回退点；redo_stack[0] 是最近被撤销的状态。
    undo_stack: list[tuple[str, np.ndarray]] = field(default_factory=list)
    redo_stack: list[tuple[str, np.ndarray]] = field(default_factory=list)
    # 深度淘汰（HistoryMixin._trim_history）丢弃的前导动作名：这些动作的产物
    # 状态已不可达，history() 据此跳过，保证条目名与可达状态一一对齐（§3.3）。
    dropped_names: list[str] = field(default_factory=list)


class HistoryMixin:
    """文档历史（docs/ipc-protocol.md §3.3）：像素快照留在 Worker 进程内，不跨进程复制。

    预算策略对齐旧 app（app/main_window.py:346-357）：最多 30 条 + 512MB 字节
    预算；超限从最旧开始淘汰，但至少保留一条 undo 快照。淘汰不得破坏 §3.3
    契约（entries[0] 恒为初始状态、undo 到底恒回到 open 像素），见
    `_trim_history`。容量为 Worker 内部策略，非协议字段。
    """

    HISTORY_MAX_ENTRIES = 30
    HISTORY_BUDGET_BYTES = 512 * 1024 * 1024

    def _push_history(self, doc: Document, name: str) -> None:
        """全分辨率应用前调用：快照当前像素（undo 的回退点），截断 redo 分支。

        与旧 app `_push_history` 相同的时机约束：必须在换入新结果之前调用。
        """
        doc.undo_stack.append((name, doc.image.copy()))
        doc.redo_stack.clear()  # 协议 §3.3：非栈顶的新变更截断 redo 分支
        self._trim_history(doc)

    def _trim_history(self, doc: Document) -> None:
        """超限从最旧淘汰（对齐旧 app 预算策略），且 §3.3 两个不变量在任意
        淘汰深度下保持：entries[0] 恒为初始状态、undo 到底恒回到 open 像素。

        - 底条目的快照像素恒等于 source_image（首次 _push_history 快照的就是
          open 态），淘汰它时原地改写为对 source_image 的共享引用：释放的是
          独立副本的内存，状态与条目名一样不丢，底条目从此"钉"在源图上
          （processors 均为函数式，source_image 从不原地修改，共享引用安全）。
        - 预算仍超限时弹出次旧条目（undo_stack[1]）：其动作名记入
          dropped_names，该动作的产物状态从此不可达；history() 跳过不可达
          状态并对齐条目名，绝不伪称 open 或错位命名。
        """
        while len(doc.undo_stack) > self.HISTORY_MAX_ENTRIES:
            self._evict_oldest(doc)
        total = sum(snapshot.nbytes for _name, snapshot in doc.undo_stack)
        while len(doc.undo_stack) > 1 and total > self.HISTORY_BUDGET_BYTES:
            self._evict_oldest(doc)
            total = sum(snapshot.nbytes for _name, snapshot in doc.undo_stack)

    def _evict_oldest(self, doc: Document) -> None:
        """淘汰一步：底条目改写为源图共享引用（钉住 open 态），已钉住时弹出
        次旧条目（undo_stack[1]）并把其动作名记入 dropped_names。

        调用前提 len(undo_stack) >= 2（两条淘汰循环的守卫保证）。
        """
        name, snapshot = doc.undo_stack[0]
        if snapshot is not doc.source_image:
            # 底条目快照即 open 态像素的独立副本：改写为共享引用即完成本次淘汰。
            doc.undo_stack[0] = (name, doc.source_image)
            return
        if len(doc.undo_stack) > 1:
            dropped_name, _snapshot = doc.undo_stack.pop(1)
            doc.dropped_names.append(dropped_name)

    def undo(self, doc: Document) -> None:
        if not doc.undo_stack:
            raise WorkerError(protocol.ERR_UNREDOABLE, f'文档无可撤销条目: {doc.document_id}')
        name, snapshot = doc.undo_stack.pop()
        if not doc.undo_stack and doc.dropped_names:
            # 弹出的是钉在源图上的底条目：被离开的状态是最旧幸存快照，由最后
            # 一个被深度淘汰的动作产生——重做条目沿用该动作名，redo 分支条目
            # 名与可达状态保持一致（§3.3 条目命名规则）。
            name = doc.dropped_names[-1]
        # 当前状态正是该动作的产物，重做时沿用同一动作名（§3.3 条目命名规则）。
        doc.redo_stack.append((name, doc.image.copy()))
        doc.image = snapshot

    def redo(self, doc: Document) -> None:
        if not doc.redo_stack:
            raise WorkerError(protocol.ERR_UNREDOABLE, f'文档无可重做条目: {doc.document_id}')
        name, future = doc.redo_stack.pop()
        doc.undo_stack.append((name, doc.image.copy()))
        doc.image = future

    def reset(self, doc: Document) -> None:
        doc.image = doc.source_image.copy()
        doc.undo_stack.clear()
        doc.redo_stack.clear()
        doc.dropped_names.clear()
        doc.modified = False  # 像素回到源图，无未保存修改

    def history(self, doc: Document) -> dict[str, Any]:
        """image.history（sync）的结果：entries + current + canUndo/canRedo。

        条目与可达状态一一对应（§3.3）：
        - 无深度淘汰：entries[i+1] 沿用 undo_stack[i] 的动作名（原规则）。
        - 有深度淘汰：底条目钉在源图上（undo 它 = open），其上的第一个幸存
          快照由最后一个被淘汰的动作产生，故 entries[1] 取 dropped_names[-1]，
          其后沿用幸存条目自身的动作名；底条目被 undo 后（栈空）其重做条目
          已按同一名规则改名，redo 分支自然对齐。
        - redo 分支按重做顺序排列（redo_stack[-1] 最先被重做），保证
          "点击条目 = 连续 undo/redo"落到的像素与条目名一致。
        """
        entries: list[dict[str, Any]] = [{'index': 0, 'name': 'open'}]
        if doc.dropped_names and doc.undo_stack:
            entries.append({'index': 1, 'name': doc.dropped_names[-1]})
            entries.extend({'index': i + 2, 'name': name}
                           for i, (name, _snapshot) in enumerate(doc.undo_stack[1:]))
        else:
            entries.extend({'index': i + 1, 'name': name}
                           for i, (name, _snapshot) in enumerate(doc.undo_stack))
        for j, (name, _snapshot) in enumerate(reversed(doc.redo_stack)):
            entries.append({'index': len(doc.undo_stack) + j + 1, 'name': name})
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
