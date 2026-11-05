"""滤镜适配：FilterDefRegistry / FilterChain 的协议化（docs/ipc-protocol.md §3）。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

# import processors 触发全部滤镜注册（FilterDefRegistry 填充）。
import processors  # noqa: F401
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
