"""滤镜适配：FilterDefRegistry / FilterChain 的协议化（docs/ipc-protocol.md §3）。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

# import processors 触发全部滤镜注册（FilterDefRegistry 填充）。
import processors  # noqa: F401
from processors import filter_presets as preset_store
from processors.cancellation import CancelToken
from processors.filter_chain import FilterChain, FilterStep
from processors.filter_chain_task import downscale_preview, run_filter_chain_sync
from processors.filter_defs import CATEGORY_LABELS, FilterDefRegistry

from .image_adapter import WorkerError


def list_filters() -> list[dict[str, Any]]:
    registry = FilterDefRegistry.instance()
    items: list[dict[str, Any]] = []
    for key, defn in registry.all().items():
        items.append({
            'key': defn.key,
            'name': defn.display_name,
            'category': defn.category.value,
            'category_label': CATEGORY_LABELS.get(defn.category, defn.category.value),
            'description': defn.description,
            'available': not defn.optional_deps,
            'optional_deps': defn.optional_deps,
            'preview_supported': defn.preview_supported,
            'batch_supported': defn.batch_supported,
            'params': [_param_to_dict(p) for p in defn.params],
        })
    items.sort(key=lambda item: (item['category'], item['name']))
    return items


def _param_to_dict(param) -> dict[str, Any]:
    return {
        'name': param.name,
        'label': param.label,
        'type': param.type,
        'default': param.default,
        'minimum': param.minimum,
        'maximum': param.maximum,
        'step': param.step,
        'choices': param.choices,
        'description': param.description,
    }


def build_chain(steps: list[dict[str, Any]]) -> FilterChain:
    """从协议 JSON 构造 FilterChain；未知 key / 参数错误归一为 INVALID_PARAMS。"""
    if not isinstance(steps, list):
        raise WorkerError('INVALID_PARAMS', 'filters 必须是数组')
    chain = FilterChain()
    for i, raw in enumerate(steps):
        if not isinstance(raw, dict) or not raw.get('filter_key'):
            raise WorkerError('INVALID_PARAMS', f'filters[{i}] 缺少 filter_key')
        try:
            chain.add_step(FilterStep.from_dict(raw))
        except (KeyError, ValueError) as exc:
            raise WorkerError('INVALID_PARAMS', f'filters[{i}]: {exc}') from exc
    ok, errors = chain.validate_all()
    if not ok:
        raise WorkerError('INVALID_PARAMS', '; '.join(errors))
    return chain


def run_chain(image: np.ndarray, chain: FilterChain,
              progress: Callable[[int], None], cancel_token: CancelToken) -> np.ndarray:
    def _step_progress(done: int, total: int) -> None:
        progress(int(done * 100 // max(1, total)))

    try:
        return run_filter_chain_sync(image, chain, progress_cb=_step_progress,
                                     cancel_token=cancel_token)
    except Exception as exc:  # FilterStepError 等处理器异常 → 协议错误
        raise WorkerError('ENGINE_ERROR', str(exc)) from exc


def write_preview(image: np.ndarray, temp_dir: Path, document_id: str,
                  max_side: int = 768) -> dict[str, Any]:
    """把预览图写入临时文件并返回带校验的描述（协议 §4）。"""
    temp_dir.mkdir(parents=True, exist_ok=True)
    preview_path = temp_dir / f'preview-{document_id}.png'
    # 预览统一 PNG：无损、解码快、C++ 端直接上纹理。
    from PIL import Image
    payload = np.ascontiguousarray(downscale_preview(image, max(16, int(max_side))))
    Image.fromarray(_to_uint8(payload)).save(preview_path, format='PNG')
    return {
        'path': str(preview_path),
        'width': int(payload.shape[1]),
        'height': int(payload.shape[0]),
        'sha256': _sha256_file(preview_path),
    }


def _to_uint8(image: np.ndarray) -> np.ndarray:
    if image.dtype == np.uint8:
        return image
    clipped = np.clip(image, 0, 255)
    return clipped.astype(np.uint8)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b''):
            digest.update(chunk)
    return digest.hexdigest()


def chain_fingerprint(steps: list[dict[str, Any]]) -> str:
    """预览缓存 key 的输入：链参数的稳定 JSON 摘要。"""
    return hashlib.sha256(
        json.dumps(steps, sort_keys=True, ensure_ascii=False).encode('utf-8'),
    ).hexdigest()[:16]


# ---- 滤镜链预设（docs/ipc-protocol.md §3.4）--------------------------------
#
# processors/filter_presets.py 是既有资产：存储路径（缺省
# ~/.toolbox/filter_presets/*.filterchain.json，可被 Settings 覆盖）、临时文件
# + rename 的原子写与 schema_version 管理全部原样复用，本层只做协议化——
# 形状裁剪与错误码归一，不重写任何存储逻辑。

def list_presets() -> list[dict[str, Any]]:
    """filter.presets.list：只暴露协议字段 {name, step_count}（§3.4）。"""
    presets: list[dict[str, Any]] = []
    for item in preset_store.list_presets():
        presets.append({'name': item['name'], 'step_count': item['step_count']})
    return presets


def save_preset(name: Any, steps: Any) -> dict[str, Any]:
    """filter.presets.save：steps 逐项经 FilterStep.from_dict 校验后存盘。

    形状非法（steps 非数组、缺 filter_key、name 非非空字符串）归一为
    INVALID_PARAMS；存储层 ValueError（空 name）同样归一。同名预设覆盖
    （存储层 overwrite=True 缺省语义）。有意不做 FilterDef 参数校验：预设是
    持久化用户状态，允许保存引用当前环境不可用滤镜的链，参数校验沿用
    apply 路径（FilterChain.validate_all）。
    """
    name = _require_preset_name(name)
    chain = FilterChain(steps=_validate_preset_steps(steps))
    try:
        preset_store.save_preset(name, chain)
    except ValueError as exc:  # 存储层残余校验（如空 name）
        raise WorkerError('INVALID_PARAMS', f'保存预设失败: {exc}') from exc
    return {'saved': True, 'name': name}


def load_preset(name: Any) -> dict[str, Any]:
    """filter.presets.load：不存在 → FILE_NOT_FOUND；文件内容问题 → ENGINE_ERROR。"""
    name = _require_preset_name(name)
    try:
        chain = preset_store.load_preset(name)
    except FileNotFoundError as exc:
        raise WorkerError('FILE_NOT_FOUND', f'预设不存在: {name}') from exc
    except ValueError as exc:  # schema_version 超前 / 步骤解析失败 / JSON 损坏
        raise WorkerError('ENGINE_ERROR', f'预设文件无法解析: {exc}') from exc
    return {'name': name, 'steps': [step.to_dict() for step in chain]}


def delete_preset(name: Any) -> dict[str, Any]:
    """filter.presets.delete：预设不存在 → FILE_NOT_FOUND（不谎报删除成功）。"""
    name = _require_preset_name(name)
    try:
        deleted = preset_store.delete_preset(name)
    except OSError as exc:
        raise WorkerError('ENGINE_ERROR', f'预设删除失败: {exc}') from exc
    if not deleted:
        raise WorkerError('FILE_NOT_FOUND', f'预设不存在: {name}')
    return {'deleted': True}


def _require_preset_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise WorkerError('INVALID_PARAMS', 'name 必须是非空字符串')
    return name


def _validate_preset_steps(steps: Any) -> list[FilterStep]:
    """协议 steps → FilterStep 列表；FilterStep.from_dict 校验失败归一 INVALID_PARAMS。"""
    if not isinstance(steps, list):
        raise WorkerError('INVALID_PARAMS', 'steps 必须是数组')
    validated: list[FilterStep] = []
    for i, raw in enumerate(steps):
        try:
            validated.append(FilterStep.from_dict(raw))
        except (TypeError, ValueError) as exc:
            raise WorkerError('INVALID_PARAMS', f'steps[{i}]: {exc}') from exc
    return validated
