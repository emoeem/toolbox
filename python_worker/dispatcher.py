"""动作分发：请求 → 同步响应或异步任务（docs/ipc-protocol.md §3）。"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import protocol
from .adapters import batch_adapter, filter_adapter, generate_adapter
from .adapters.image_adapter import (ADJUST_KEYS, TRANSFORM_REQUIRED_PARAMS, Document, DocumentStore,
                                     WorkerError, adjust_chain, apply_transform)
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
            'image.history': self._image_history,
            'filter.list': self._filter_list,
            'filter.presets.list': self._filter_presets_list,
            'filter.presets.save': self._filter_presets_save,
            'filter.presets.load': self._filter_presets_load,
            'filter.presets.delete': self._filter_presets_delete,
            'generate.list': self._generate_list,
            'task.cancel': self._task_cancel,
            'task.query': self._task_query,
            'batch.cancel': self._batch_cancel,
            'gmic.check': self._gmic_check,
        }
        self._async: dict[str, Callable[[dict], Callable[..., dict]]] = {
            'image.save': self._image_save_job,
            'image.adjust': self._image_adjust_job,
            'image.transform': self._image_transform_job,
            'image.undo': self._image_undo_job,
            'image.redo': self._image_redo_job,
            'image.reset': self._image_reset_job,
            'filter.preview': self._filter_preview_job,
            'filter.apply': self._filter_apply_job,
            'generate.render': self._generate_render_job,
            'batch.start': self._batch_start_job,
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
                # 受理回执附加字段：异步任务工厂可在 job 上挂 accepted_extra
                #（目前仅 batch.start 的 total，协议 §3.5 同步响应 {task_id,
                # status, total}）；其余动作无此属性，受理形状不变（§2.3）。
                accepted = getattr(job, 'accepted_extra', None)
                if accepted:
                    result = {**result, **accepted}
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

    def _image_history(self, params: dict) -> dict[str, Any]:
        doc = self.ctx.store.get(_require(params, 'document_id'))
        return self.ctx.store.history(doc)

    def _filter_list(self, _params: dict) -> dict[str, Any]:
        return {'filters': filter_adapter.list_filters()}

    # 预设四动作均为纯 sync（docs/ipc-protocol.md §3.4）：参数校验与错误码
    # 归一在 filter_adapter，本层只做接线（模式同 image.metadata）。
    def _filter_presets_list(self, _params: dict) -> dict[str, Any]:
        return {'presets': filter_adapter.list_presets()}

    def _filter_presets_save(self, params: dict) -> dict[str, Any]:
        return filter_adapter.save_preset(params.get('name'), params.get('steps'))

    def _filter_presets_load(self, params: dict) -> dict[str, Any]:
        return filter_adapter.load_preset(params.get('name'))

    def _filter_presets_delete(self, params: dict) -> dict[str, Any]:
        return filter_adapter.delete_preset(params.get('name'))

    # ---- 生成器（docs/ipc-protocol.md §3.7，Phase 6C）-------------------------
    # generate.list 为纯目录 sync（模式同 filter.list）；generate.render 的
    # 未知/不可用生成器、尺寸与参数校验在提交任务前同步完成（先例同
    # image.transform 的 op 校验），非法即错误响应、不产生 task_id。
    def _generate_list(self, _params: dict) -> dict[str, Any]:
        return {'generators': generate_adapter.list_generators()}

    def _generate_render_job(self, params: dict) -> Callable[..., dict]:
        entry, prepared = generate_adapter.validate_render_request(params)
        temp_dir = self.ctx.temp_dir

        def job(progress_cb, cancel_token) -> dict:
            progress_cb(5, '准备渲染')
            image = generate_adapter.render_generator(entry, prepared, progress_cb, cancel_token)
            progress_cb(85, '写入结果文件')
            info = generate_adapter.write_render(image, temp_dir, entry['key'],
                                                 prepared['width'], prepared['height'])
            info['generator_key'] = entry['key']
            return info

        return job

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

    # ---- 批处理与依赖诊断（docs/ipc-protocol.md §3.5/§3.6）--------------------
    def _batch_cancel(self, params: dict) -> dict[str, Any]:
        """batch.cancel：语义同 task.cancel（复用 CancelToken），结果形状按
        §3.5 为 {cancelled}；已终结任务如实返回 cancelled=false，不谎报。"""
        result = self.ctx.ensure_runtime().cancel(_require(params, 'task_id'))
        if result is None:
            raise WorkerError(protocol.ERR_UNKNOWN_TASK, f'任务不存在: {params.get("task_id")}')
        return {'cancelled': bool(result.get('cancelling'))}

    def _gmic_check(self, _params: dict) -> dict[str, Any]:
        # 可用性如实返回（§3.6）；探测在适配层接线到 processors.gmic.check，
        # dispatcher 保持引擎无关（adapters/__init__.py 的分层规则）。
        return filter_adapter.check_gmic()

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
            # 全分辨率变更进历史（协议 §3.3：filter.apply 也产生 undo 条目）。
            # 参数化 undo（docs/competitive-analysis.md §4 行动项 1）：链条目只存
            # 链参数（协议 filters 数组的深拷贝），undo 从基线/最近快照锚点重放，
            # 不保留像素快照；栈顶是不可重放快照（transform 类）时由
            # _push_replay_history 内部退化为快照条目（重放屏障）。
            store._push_replay_history(doc, 'filter.apply',
                                       {'kind': 'chain', 'steps': copy.deepcopy(steps)})
            doc.image = result_image
            doc.modified = True
            doc.version += 1  # 协议 §3.1
            return {'width': int(result_image.shape[1]),
                    'height': int(result_image.shape[0]),
                    'version': doc.version}

        return job

    # ---- 批处理（docs/ipc-protocol.md §3.5，复用 processors 1.0 批处理资产）----
    def _batch_start_job(self, params: dict) -> Callable[..., dict]:
        # 参数形状/路径扫描/链校验在提交前同步完成（§3.5；先例同 filter.preview
        # 与 image.transform 的提交前判定），非法即错误响应、不产生 task_id。
        plan = batch_adapter.build_batch_plan(params)

        def job(progress_cb, cancel_token) -> dict:
            return batch_adapter.run_batch_plan(plan, progress_cb, cancel_token)

        # §3.5 同步响应 {task_id, status, total}：total 为扫描所得文件数，与
        # 完成事件 result.total 同源（同一 plan.files）。handle 把 accepted_extra
        # 并入 TaskRuntime.submit 的受理回执（task_id/status 之外的纯新增字段，
        # 消费方按 §2.3 忽略未知字段——C++ BatchService 只读 task_id）。
        job.accepted_extra = {'total': len(plan.files)}
        return job

    # ---- image.adjust / image.transform / 历史恢复（docs/ipc-protocol.md §3.1-§3.3）----
    #
    # 约定：可在提交任务前判定的错误（参数形状、栈空、crop 越界）在工厂里同步抛出
    # WorkerError，直接成为错误响应、不产生 task_id（与 filter.preview 的链校验一致）；
    # 任务体只做像素操作与预览文件写入，走 §2.3/§7 的标准任务生命周期。

    def _image_adjust_job(self, params: dict) -> Callable[..., dict]:
        document_id = _require(params, 'document_id')
        adjustments = _validate_adjustments(params.get('adjustments'))
        preview = _require_preview_flag(params.get('preview'))
        max_side = _require_max_side(params.get('max_side'))
        store = self.ctx.store
        temp_dir = self.ctx.temp_dir

        if preview:
            def job(progress_cb, cancel_token) -> dict:
                doc = store.get(document_id)
                version = doc.version  # §2.3：预览 result.version = 执行时的当前版本（与预览所据像素一致）
                progress_cb(5, '计算调整预览')
                cancel_token.raise_if_cancelled()
                adjusted = adjust_chain(doc.image, adjustments)
                progress_cb(90, '写入预览文件')
                info = filter_adapter.write_preview(adjusted, temp_dir, document_id, max_side)
                return {'version': version, 'path': info['path'],
                        'width': info['width'], 'height': info['height'],
                        'sha256': info['sha256']}

        else:
            def job(progress_cb, cancel_token) -> dict:
                doc = store.get(document_id)
                progress_cb(10, '应用调整')
                cancel_token.raise_if_cancelled()
                adjusted = adjust_chain(doc.image, adjustments)
                cancel_token.raise_if_cancelled()
                # 滑杆命令合并（coalescing，docs/competitive-analysis.md §4 行动项 2）：
                # 与上一条同为全分辨率 image.adjust 且中间无其它动作/撤销时并作
                # 单条历史（条目内重放序列追加本次 adjustments）；否则正常快照
                # 推送（快照条目携带 adjustments 作重放参数）。
                store._push_adjust_history(doc, 'image.adjust', adjustments)
                doc.image = adjusted
                doc.modified = True
                doc.version += 1
                return {'version': doc.version,
                        'width': int(adjusted.shape[1]), 'height': int(adjusted.shape[0])}

        return job

    def _image_transform_job(self, params: dict) -> Callable[..., dict]:
        document_id = _require(params, 'document_id')
        op = params.get('op')
        # JSON 值可能是任意类型：非字符串先拒绝，避免对 dict 做不可哈希成员测试。
        if not isinstance(op, str) or op not in TRANSFORM_REQUIRED_PARAMS:
            raise WorkerError(protocol.ERR_INVALID_PARAMS, f'未知变换 op: {op}')
        transform_params = _validate_transform_params(op, params.get('params'))
        if op == 'scale' and transform_params['sx'] <= 0:
            raise WorkerError(protocol.ERR_INVALID_PARAMS, 'scale 的 sx 必须 > 0')
        if op == 'crop':
            x, y, w, h = (transform_params[key] for key in ('x', 'y', 'w', 'h'))
            if w <= 0 or h <= 0:
                raise WorkerError(protocol.ERR_INVALID_PARAMS, 'crop 的 w/h 必须 > 0')
            # 越界判定需要当前图像尺寸：提交前同步检查（协议 §3.2）。
            image = self.ctx.store.get(document_id).image
            if x < 0 or y < 0 or x + w > int(image.shape[1]) or y + h > int(image.shape[0]):
                raise WorkerError(protocol.ERR_INVALID_PARAMS, 'crop 矩形超出图像范围')
        preview = _require_preview_flag(params.get('preview'))
        max_side = _require_max_side(params.get('max_side'))
        store = self.ctx.store
        temp_dir = self.ctx.temp_dir

        if preview:
            def job(progress_cb, cancel_token) -> dict:
                doc = store.get(document_id)
                version = doc.version  # §2.3：预览 result.version = 执行时的当前版本（与预览所据像素一致）
                progress_cb(5, '计算变换预览')
                cancel_token.raise_if_cancelled()
                transformed = apply_transform(doc.image, op, transform_params)
                progress_cb(90, '写入预览文件')
                info = filter_adapter.write_preview(transformed, temp_dir, document_id, max_side)
                return {'version': version, 'path': info['path'],
                        'width': info['width'], 'height': info['height'],
                        'sha256': info['sha256']}

        else:
            def job(progress_cb, cancel_token) -> dict:
                doc = store.get(document_id)
                progress_cb(10, '应用变换')
                cancel_token.raise_if_cancelled()
                transformed = apply_transform(doc.image, op, transform_params)
                cancel_token.raise_if_cancelled()
                # transform/crop 类保持像素快照且不带重放参数（scale/crop 有损，
                # 参数重放不可靠）：该条目是参数化 undo 的"重放屏障"——其上的
                # 滤镜链条目由 _push_replay_history 退化为快照条目（§4 行动项 1）。
                store._push_history(doc, 'image.transform')
                doc.image = transformed
                doc.modified = True
                doc.version += 1
                return {'version': doc.version,
                        'width': int(transformed.shape[1]), 'height': int(transformed.shape[0])}

        return job

    def _image_undo_job(self, params: dict) -> Callable[..., dict]:
        document_id = _require(params, 'document_id')
        doc = self.ctx.store.get(document_id)  # 同步 UNKNOWN_DOCUMENT / UNREDOABLE（协议 §3.3）
        if not doc.undo_stack:
            raise WorkerError(protocol.ERR_UNREDOABLE, f'文档无可撤销条目: {document_id}')
        return _history_restore_job(self.ctx, document_id, self.ctx.store.undo)

    def _image_redo_job(self, params: dict) -> Callable[..., dict]:
        document_id = _require(params, 'document_id')
        doc = self.ctx.store.get(document_id)
        if not doc.redo_stack:
            raise WorkerError(protocol.ERR_UNREDOABLE, f'文档无可重做条目: {document_id}')
        return _history_restore_job(self.ctx, document_id, self.ctx.store.redo)

    def _image_reset_job(self, params: dict) -> Callable[..., dict]:
        document_id = _require(params, 'document_id')
        self.ctx.store.get(document_id)  # 提交前确认文档存在（同步 UNKNOWN_DOCUMENT）
        return _history_restore_job(self.ctx, document_id, self.ctx.store.reset)


def _require(params: dict, key: str) -> str:
    value = params.get(key)
    if not value:
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'缺少 {key}')
    return str(value)


def _require_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'{label} 必须是数值')
    return float(value)


def _require_int(value: Any, label: str) -> int:
    number = _require_number(value, label)
    if not number.is_integer():
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'{label} 必须是整数')
    return int(number)


def _require_preview_flag(value: Any) -> bool:
    if not isinstance(value, bool):
        raise WorkerError(protocol.ERR_INVALID_PARAMS, 'preview 必须是布尔值')
    return value


def _require_max_side(value: Any) -> int:
    if value is None:
        return 768  # 协议 §3.2：与 filter.preview 同缺省
    return _require_int(value, 'max_side')


def _validate_adjustments(raw: Any) -> dict[str, float]:
    """image.adjust 的 adjustments 校验（协议 §3.2）：非空对象、键合法、值均为数值。"""
    if not isinstance(raw, dict) or not raw:
        raise WorkerError(protocol.ERR_INVALID_PARAMS, 'adjustments 必须是非空对象')
    adjustments: dict[str, float] = {}
    for key, value in raw.items():
        if key not in ADJUST_KEYS:
            raise WorkerError(protocol.ERR_INVALID_PARAMS, f'未知调整键: {key}')
        adjustments[key] = _require_number(value, f'adjustments.{key}')
    return adjustments


def _validate_transform_params(op: str, raw: Any) -> dict[str, Any]:
    """image.transform 的 params 校验（协议 §3.2 op/params 对应表）。"""
    if not isinstance(raw, dict):
        raise WorkerError(protocol.ERR_INVALID_PARAMS, 'params 必须是对象')
    validated: dict[str, Any] = {}
    for key in TRANSFORM_REQUIRED_PARAMS[op]:
        if key not in raw:
            raise WorkerError(protocol.ERR_INVALID_PARAMS, f'op={op} 缺少参数: {key}')
        if key in ('x', 'y', 'w', 'h'):
            validated[key] = _require_int(raw[key], f'params.{key}')
        else:
            validated[key] = _require_number(raw[key], f'params.{key}')
    return validated


def _history_restore_job(ctx: WorkerContext, document_id: str,
                         restore: Callable[..., None]) -> Callable[..., dict]:
    """image.undo / image.redo / image.reset 共用任务体（协议 §3.3）。

    恢复像素 → version += 1 → 写降采样预览文件（write_preview 缺省 max_side=768）。
    栈空在提交前已同步拒绝；任务体内再遇栈空（并发竞态）会抛
    WorkerError(UNREDOABLE)，由任务运行时归一为失败事件，不会谎报成功。
    restore 收到 (doc, progress_cb, cancel_token)：快照恢复直达；参数化条目
    （滤镜链）在恢复体内从基线/锚点重放（image_adapter.undo/redo），进度折算
    上报、协作取消在重放步进边界生效，取消/失败时文档状态不动
    （compute-before-commit，image_adapter.HistoryMixin.undo 注）。
    """
    store = ctx.store
    temp_dir = ctx.temp_dir

    def job(progress_cb, cancel_token) -> dict:
        doc = store.get(document_id)
        progress_cb(30, '恢复像素')
        cancel_token.raise_if_cancelled()
        restore(doc, progress_cb, cancel_token)
        doc.version += 1  # 协议 §3.1：undo/redo/reset 同样递增
        progress_cb(85, '写入预览文件')
        info = filter_adapter.write_preview(doc.image, temp_dir, document_id)
        return {'version': doc.version,
                'width': int(doc.image.shape[1]), 'height': int(doc.image.shape[0]),
                'path': info['path'], 'sha256': info['sha256']}

    return job


def _pid() -> int:
    import os
    return os.getpid()
