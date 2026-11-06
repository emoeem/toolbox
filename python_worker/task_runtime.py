"""任务运行时：线程池、状态机、协作取消与进度节流（docs/ipc-protocol.md §2.3/§7）。"""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from processors.cancellation import CancelToken, CancelledError

from . import protocol

# 状态机：queued → running → completed | failed；queued|running → cancelling → cancelled
STATUS_QUEUED = 'queued'
STATUS_RUNNING = 'running'
STATUS_COMPLETED = 'completed'
STATUS_FAILED = 'failed'
STATUS_CANCELLING = 'cancelling'
STATUS_CANCELLED = 'cancelled'

PROGRESS_MIN_INTERVAL = 0.1  # 秒；同一任务两条进度事件的最小间隔（§7 节流）

# 终结任务保留数量上限：防止长期会话无限增长；超出时按提交顺序清理。
MAX_RETAINED_TASKS = 256

Emitter = Callable[[dict], None]


class Task:
    def __init__(self, task_id: str, name: str, fn: Callable[..., Any],
                 emitter: Emitter | None = None) -> None:
        self.task_id = task_id
        self.name = name
        self.fn = fn
        self.status = STATUS_QUEUED
        self.progress = 0
        self.cancel_token = CancelToken()
        self._emitter = emitter
        self._last_progress_at = 0.0
        self._lock = threading.Lock()

    # ---- 供任务函数调用（与 processors 的 (progress_cb, cancel_token) 约定一致）----
    def progress_cb(self, value: int, message: str = '',
                    extra: dict[str, Any] | None = None) -> None:
        """extra：动作特有增补字段（批处理 done/total/current/state，§3.5）；
        节流与既有语义不变，不传 extra 的任务消息形状不变。"""
        with self._lock:
            now = _monotonic()
            if now - self._last_progress_at < PROGRESS_MIN_INTERVAL:
                return
            self._last_progress_at = now
            self.progress = int(value)
        self._emit(protocol.make_progress(self.task_id, value, message, extra))

    def _set_status(self, status: str) -> None:
        with self._lock:
            self.status = status

    def _emit(self, msg: dict[str, Any]) -> None:
        if self._emitter is not None:
            self._emitter(msg)


def _monotonic() -> float:
    return time.monotonic()


class TaskRuntime:
    """线程池任务运行时。Worker 进程内单实例。"""

    def __init__(self, max_workers: int = 2, emitter: Emitter | None = None) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max(1, max_workers), thread_name_prefix='toolbox-task')
        self._emitter = emitter
        self._tasks: dict[str, Task] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def submit(self, name: str, fn: Callable[[Callable[..., None], CancelToken], dict]) -> dict[str, Any]:
        """fn(progress_cb, cancel_token) -> result dict。返回 task_id。"""
        task_id = f'task-{uuid.uuid4().hex[:8]}'
        task = Task(task_id, name, fn, emitter=self._emitter)
        with self._lock:
            self._tasks[task_id] = task
            self._order.append(task_id)
            self._purge_locked()

        def _run() -> dict[str, Any]:
            task._set_status(STATUS_RUNNING)
            try:
                result = task.fn(task.progress_cb, task.cancel_token) or {}
            except CancelledError:
                task._set_status(STATUS_CANCELLED)
                task._emit(protocol.make_task_failed(task_id, protocol.ERR_CANCELLED, '任务已取消'))
                return {}
            except Exception as exc:  # 边界处必须把异常变成协议消息
                task._set_status(STATUS_FAILED)
                task._emit(protocol.make_task_failed(
                    task_id, protocol.ERR_ENGINE_ERROR, str(exc), {'task': task.name},
                ))
                return {}
            task._set_status(STATUS_COMPLETED)
            task._emit(protocol.make_task_completed(task_id, result))
            return result

        self._pool.submit(_run)
        # §2.3 受理回执固定为 queued：受理响应在提交时刻生成，任务体随后被
        # 线程池立即领取（此刻内部快照可能已是 running 甚至 completed）属于
        # 调度细节，不应回读 task.status——否则在 max_workers=1 且线程空闲时
        # 回执会随机变成 'running'，违反协议示例的确定性形状。真实生命周期
        # 由随后的 task.progress / task.completed|failed 事件推送。
        return {'task_id': task_id, 'status': STATUS_QUEUED}

    def cancel(self, task_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        if task.status in (STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED):
            return {'task_id': task_id, 'status': task.status, 'cancelling': False}
        task.cancel_token.cancel()
        task._set_status(STATUS_CANCELLING)
        return {'task_id': task_id, 'status': task.status, 'cancelling': True}

    def query(self, task_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        return {'task_id': task_id, 'status': task.status, 'progress': task.progress}

    def shutdown(self) -> None:
        with self._lock:
            tasks = list(self._tasks.values())
        for task in tasks:
            if task.status in (STATUS_QUEUED, STATUS_RUNNING, STATUS_CANCELLING):
                task.cancel_token.cancel()
        self._pool.shutdown(wait=False)

    def has_active(self) -> bool:
        with self._lock:
            return any(t.status in (STATUS_QUEUED, STATUS_RUNNING, STATUS_CANCELLING)
                       for t in self._tasks.values())

    def _purge_locked(self) -> None:
        while len(self._order) > MAX_RETAINED_TASKS:
            oldest = self._order.pop(0)
            task = self._tasks.get(oldest)
            if task is None:
                continue
            if task.status in (STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED):
                self._tasks.pop(oldest, None)
            else:
                # 未终结任务不能丢：推回队尾保留。
                self._order.append(oldest)
                break
