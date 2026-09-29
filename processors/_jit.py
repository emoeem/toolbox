"""Optional numba JIT helper.

numba is an optional dependency: when it is missing, `maybe_jit` returns the
plain Python function so callers keep working (just much slower).
"""
from __future__ import annotations

try:  # pragma: no cover - depends on the environment
    from numba import jit, prange

    NUMBA_OK = True
except ImportError:  # pragma: no cover
    jit = None
    prange = range
    NUMBA_OK = False


def maybe_jit(nopython: bool = True, fastmath: bool = True, cache: bool = True,
              parallel: bool = False):
    if NUMBA_OK:
        return jit(nopython=nopython, fastmath=fastmath, cache=cache, parallel=parallel)

    def _decorator(fn):
        return fn

    return _decorator


__all__ = ["maybe_jit", "NUMBA_OK", "prange"]
