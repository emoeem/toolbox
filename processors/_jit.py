"""Optional numba JIT helper.

numba is an optional dependency: when it is missing, `maybe_jit` returns the
plain Python function so callers keep working (just much slower).

Set ``TOOLBOX_NO_NUMBA=1`` to force the pure-Python path even where numba is
installed.  CI runs *without* numba, and the two paths are not equivalent --
numba returns ``inf`` from ``math.pow``/``math.exp`` where CPython raises
``OverflowError`` -- so the fallback must be testable locally.
"""
from __future__ import annotations

import os

_FORCE_OFF = os.environ.get("TOOLBOX_NO_NUMBA", "").strip().lower() in ("1", "true", "yes")

try:  # pragma: no cover - depends on the environment
    if _FORCE_OFF:
        raise ImportError("TOOLBOX_NO_NUMBA set")
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
