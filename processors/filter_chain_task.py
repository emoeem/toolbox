from __future__ import annotations

import hashlib
import threading
from typing import Any, Callable

import cv2
import numpy as np

from processors.cancellation import CancelToken, CancelledError
from processors.filter_chain import FilterChain, FilterStepError


_cache_lock = threading.Lock()
_filter_chain_preview_cache: dict[str, np.ndarray] = {}
_MAX_PREVIEW_CACHE = 8


def downscale_preview(image: np.ndarray, max_side: int) -> np.ndarray:
    h, w = image.shape[:2]
    side = max(h, w)
    if side <= max_side:
        return image.copy()
    ratio = max_side / side
    new_w, new_h = max(1, int(w * ratio)), max(1, int(h * ratio))
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def preview_cache_key(
    image: np.ndarray,
    chain: FilterChain,
    max_side: int = 256,
    image_generation: int = 0,
) -> str:
    h, w = image.shape[:2]
    hw = f"{h}x{w}"
    chain_json = chain.to_json()
    h_src = hashlib.sha1(np.ascontiguousarray(image[::4, ::4]).tobytes()).hexdigest()[:16]
    h_chain = hashlib.sha1(chain_json.encode("utf-8")).hexdigest()[:16]
    return f"{hw}_g{image_generation}_{h_src}_{h_chain}_m{max_side}"


def preview_cache_get(key: str) -> np.ndarray | None:
    with _cache_lock:
        v = _filter_chain_preview_cache.get(key)
        if v is not None:
            _filter_chain_preview_cache.pop(key)
            _filter_chain_preview_cache[key] = v
        return v


def preview_cache_set(key: str, value: np.ndarray) -> None:
    with _cache_lock:
        if key in _filter_chain_preview_cache:
            _filter_chain_preview_cache.pop(key)
        elif len(_filter_chain_preview_cache) >= _MAX_PREVIEW_CACHE:
            oldest = next(iter(_filter_chain_preview_cache))
            del _filter_chain_preview_cache[oldest]
        _filter_chain_preview_cache[key] = value


def preview_cache_clear() -> None:
    with _cache_lock:
        _filter_chain_preview_cache.clear()


def _chain_step_map(chain: FilterChain) -> list[tuple[int, FilterStep]]:
    return [(i, s) for i, s in enumerate(chain.steps) if s.enabled]


def make_filter_chain_worker(
    image: np.ndarray,
    chain: FilterChain,
    progress_cb: Callable[[int, int], None] | None = None,
    cancel_token: CancelToken | None = None,
) -> Callable[[Callable[[int], None], CancelToken], np.ndarray]:
    def worker(qprogress: Callable[[int], None], qcancel: CancelToken) -> np.ndarray:
        ct = cancel_token or qcancel
        if progress_cb is None:
            def _per_step(i: int, total: int) -> None:
                qprogress(int(i * 100 // max(1, total)))
        else:
            def _per_step(i: int, total: int) -> None:
                progress_cb(i, total)
                qprogress(int(i * 100 // max(1, total)))
        ok, errs = chain.validate_all()
        if not ok:
            raise ValueError("; ".join(errs))
        steps = _chain_step_map(chain)
        total_steps = len(steps)
        current = image
        _per_step(0, total_steps)
        for pi, (orig_idx, step) in enumerate(steps):
            if ct is not None:
                ct.raise_if_cancelled()
            try:
                current = step.apply(current, cancel_token=ct)
            except FilterStepError as exc:
                if exc.step_index < 0:
                    raise FilterStepError(orig_idx, step.filter_key, str(exc), original=exc.original) from exc
                raise
            _per_step(pi + 1, total_steps)
        return current
    return worker


def run_filter_chain_sync(
    image: np.ndarray,
    chain: FilterChain,
    progress_cb: Callable[[int, int], None] | None = None,
    cancel_token: CancelToken | None = None,
) -> np.ndarray:
    ct = cancel_token or CancelToken()
    ok, errs = chain.validate_all()
    if not ok:
        raise ValueError("; ".join(errs))
    steps = _chain_step_map(chain)
    total = len(steps)
    current = image
    for pi, (orig_idx, step) in enumerate(steps):
        ct.raise_if_cancelled()
        try:
            current = step.apply(current, cancel_token=ct)
        except FilterStepError as exc:
            if exc.step_index < 0:
                raise FilterStepError(orig_idx, step.filter_key, str(exc), original=exc.original) from exc
            raise
        if progress_cb is not None:
            progress_cb(pi + 1, total)
    return current


__all__ = [
    "downscale_preview",
    "preview_cache_key",
    "preview_cache_get",
    "preview_cache_set",
    "preview_cache_clear",
    "make_filter_chain_worker",
    "run_filter_chain_sync",
]
