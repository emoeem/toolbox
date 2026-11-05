"""动作分发：请求 → 同步响应或异步任务（docs/ipc-protocol.md §3）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import protocol
from .adapters import filter_adapter
from .adapters.image_adapter import DocumentStore, WorkerError
from .task_runtime import TaskRuntime

WORKER_VERSION = '1.0.0'

# 交叉引用必须在函数内完成，避免 dispatcher ↔ image_adapter 循环依赖。


@dataclass
class WorkerContext:
    store: DocumentStore = field(default_factory=DocumentStore)
    runtime: TaskRuntime | None = None
    temp_dir: Path = Path('.').resolve()
    repo_root: Path = Path('.').resolve()

    def ensure_runtime(self) -> TaskRuntime:
        if self.runtime is None:
            raise WorkerError(protocol.ERR_INTERNAL, '任务运行时未初始化')
        return self.runtime


class Dispatcher:
    """同步动作直接返回响应消息；异步动作提交 TaskRuntime 并立即回执 task_id。"""

    def __init__(self, ctx: WorkerContext) -> None:
        self.ctx = ctx
        self._sync: dict[str, Callable[[dict], dict]] = {
            'worker.hello': self._hello,
            'worker.shutdown': self._shutdown,
            'capabilities.list': self._capabilities,
            'image.open': self._image_open,
            'image.close': self._image_close,
            'image.metadata': self._image_metadata,
            'filter.list': self._filter_list,
            'task.cancel': self._task_cancel,
            'task.query': self._task_query,
        }
        self._async: dict[str, Callable[[dict], Callable[..., dict]]] = {
            'image.save': self._image_save_job,
            'filter.preview': self._filter_preview_job,
            'filter.apply': self._filter_apply_job,
        }
        self._shutting_down = False

    # ---- 主入口 ------------------------------------------------------------
    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        action = request.get('action')
        params = request.get('params') or {}
        if not isinstance(params, dict):
            return protocol.make_error(request['request_id'], protocol.ERR_INVALID_PARAMS,
                                       'params 必须是对象')
        handler = self._sync.get(action)
        if handler is not None:
            try:
                return protocol.make_response(request['request_id'], True, handler(params))
            except WorkerError as exc:
                return protocol.make_error(request['request_id'], exc.code, exc.message, exc.details)
            except Exception as exc:  # 边界：任何处理器异常不得导致 Worker 退出
                return protocol.make_error(request['request_id'], protocol.ERR_INTERNAL, str(exc))

        job_factory = self._async.get(action)
        if job_factory is not None:
            try:
                job = job_factory(params)
                result = self.ctx.ensure_runtime().submit(action, job)
                return protocol.make_response(request['request_id'], True, result)
            except WorkerError as exc:
                return protocol.make_error(request['request_id'], exc.code, exc.message, exc.details)
            except Exception as exc:
                return protocol.make_error(request['request_id'], protocol.ERR_INTERNAL, str(exc))

        return protocol.make_error(request['request_id'], protocol.ERR_UNKNOWN_ACTION,
                                   f'未知动作: {action}')

    # ---- 引擎信息 ------------------------------------------------------------
    @staticmethod
    def _engine_info() -> dict[str, Any]:
        import cv2
        import numpy
        try:
            import numba  # noqa: F401
            numba_status = True
        except ImportError:
            numba_status = False
        return {'numpy': numpy.__version__, 'cv2': cv2.__version__, 'numba': numba_status}

    # ---- 同步动作 ------------------------------------------------------------
    def _hello(self, _params: dict) -> dict[str, Any]:
        return {
            'worker_version': WORKER_VERSION,
            'protocol': protocol.PROTOCOL_VERSION,
            'pid': _pid(),
            'engine': self._engine_info(),
        }

    def _shutdown(self, _params: dict) -> dict[str, Any]:
        self._shutting_down = True
        self.ctx.ensure_runtime().shutdown()
        self.ctx.store.close_all()
        return {'ok': True}

    @property
    def shutting_down(self) -> bool:
        return self._shutting_down

    def _capabilities(self, _params: dict) -> dict[str, Any]:
        return {
            'actions': sorted([*self._sync.keys(), *self._async.keys()]),
            'filter_count': len(filter_adapter.list_filters()),
            'engine': self._engine_info(),
        }

    def _image_open(self, params: dict) -> dict[str, Any]:
        path = params.get('path')
        if not path:
            raise WorkerError(protocol.ERR_INVALID_PARAMS, '缺少 path')
        doc = self.ctx.store.open(str(path))
        return {
            'document_id': doc.document_id,
            'width': int(doc.image.shape[1]),
            'height': int(doc.image.shape[0]),
            'format': doc.format,
            'file_size': Path(doc.source).stat().st_size,
        }

    def _image_close(self, params: dict) -> dict[str, Any]:
        document_id = params.get('document_id')
        if not document_id:
            raise WorkerError(protocol.ERR_INVALID_PARAMS, '缺少 document_id')
        if not self.ctx.store.close(document_id):
            raise WorkerError(protocol.ERR_UNKNOWN_DOCUMENT, f'文档不存在: {document_id}')
        return {'closed': True}

    def _image_metadata(self, params: dict) -> dict[str, Any]:
        doc = self.ctx.store.get(_require(params, 'document_id'))
        return {
            'width': int(doc.image.shape[1]),
            'height': int(doc.image.shape[0]),
            'format': doc.format,
            'source': doc.source,
            'modified': doc.modified,
        }

    def _filter_list(self, _params: dict) -> dict[str, Any]:
        return {'filters': filter_adapter.list_filters()}

    def _task_cancel(self, params: dict) -> dict[str, Any]:
        result = self.ctx.ensure_runtime().cancel(_require(params, 'task_id'))
        if result is None:
            raise WorkerError(protocol.ERR_UNKNOWN_TASK, f'任务不存在: {params.get("task_id")}')
        return result

    def _task_query(self, params: dict) -> dict[str, Any]:
        result = self.ctx.ensure_runtime().query(_require(params, 'task_id'))
        if result is None:
            raise WorkerError(protocol.ERR_UNKNOWN_TASK, f'任务不存在: {params.get("task_id")}')
        return result

    # ---- 异步任务工厂（返回 fn(progress_cb, cancel_token)）-------------------
    def _image_save_job(self, params: dict) -> Callable[..., dict]:
        document_id = _require(params, 'document_id')
        path = _require(params, 'path')
        quality = params.get('quality')
        store = self.ctx.store

        def job(progress_cb, cancel_token) -> dict:
            progress_cb(10, '写入文件')
            cancel_token.raise_if_cancelled()
            return store.save(document_id, str(path), quality)

        return job

    def _filter_preview_job(self, params: dict) -> Callable[..., dict]:
        document_id = _require(params, 'document_id')
        steps = params.get('filters')
        max_side = int(params.get('max_side') or 768)
        temp_dir = self.ctx.temp_dir
        store = self.ctx.store
        chain = filter_adapter.build_chain(steps)  # 参数错误在提交前同步报出

        def job(progress_cb, cancel_token) -> dict:
            doc = store.get(document_id)
            progress_cb(5, '准备预览')
            result_image = filter_adapter.run_chain(doc.image, chain, progress_cb, cancel_token)
            progress_cb(90, '写入预览文件')
            info = filter_adapter.write_preview(result_image, temp_dir, document_id, max_side)
            info['preview_of'] = document_id
            info['fingerprint'] = filter_adapter.chain_fingerprint(steps or [])
            return info

        return job

    def _filter_apply_job(self, params: dict) -> Callable[..., dict]:
        document_id = _require(params, 'document_id')
        steps = params.get('filters')
        store = self.ctx.store
        chain = filter_adapter.build_chain(steps)

        def job(progress_cb, cancel_token) -> dict:
            doc = store.get(document_id)
            result_image = filter_adapter.run_chain(doc.image, chain, progress_cb, cancel_token)
            doc.image = result_image
            doc.modified = True
            return {'width': int(result_image.shape[1]), 'height': int(result_image.shape[0])}

        return job


def _require(params: dict, key: str) -> str:
    value = params.get(key)
    if not value:
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'缺少 {key}')
    return str(value)


def _pid() -> int:
    import os
    return os.getpid()
