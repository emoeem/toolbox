from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

import numpy as np
from PIL import Image

from processors.cancellation import CancelToken, CancelledError
from processors._jit import NUMBA_OK as _NUMBA_OK, maybe_jit as _maybe_jit, prange  # noqa: F401


class FractalColoring(str, Enum):
    SMOOTH = "smooth"
    BANDED = "banded"
    GRAYSCALE = "grayscale"


DIM_2D = 2
DIM_3D = 3


@dataclass
class JuliaConstant:
    real: float = -0.8
    imag: float = 0.156

    def to_tuple(self) -> tuple[float, float]:
        return (self.real, self.imag)


@dataclass
class PhoenixConstant:
    real: float = -0.5
    imag: float = 0.0

    def to_tuple(self) -> tuple[float, float]:
        return (self.real, self.imag)


@dataclass
class FractalParams:
    width: int = 512
    height: int = 512
    cx: float = -0.5
    cy: float = 0.0
    scale: float = 3.0
    power: float = 2.0
    iterations: int = 256
    bailout: float = 2.0
    coloring: FractalColoring = FractalColoring.SMOOTH
    julia_c: JuliaConstant = field(default_factory=JuliaConstant)
    phoenix_c: PhoenixConstant = field(default_factory=PhoenixConstant)
    nova_relaxation: float = 1.0
    supersampling: int = 1

    def validate(self) -> None:
        if self.width < 1 or self.height < 1:
            raise ValueError(f"width/height must be >=1, got {self.width}x{self.height}")
        if self.width > 4096 or self.height > 4096:
            raise ValueError(f"width/height must be <=4096, got {self.width}x{self.height}")
        if self.scale <= 0:
            raise ValueError(f"scale must be >0, got {self.scale}")
        if self.power <= 0:
            raise ValueError(f"power must be >0, got {self.power}")
        if not (1 <= self.iterations <= 10000):
            raise ValueError(f"iterations must be 1..10000, got {self.iterations}")
        if self.bailout <= 0:
            raise ValueError(f"bailout must be >0, got {self.bailout}")
        if not (1 <= self.supersampling <= 4):
            raise ValueError(f"supersampling must be 1..4, got {self.supersampling}")


@dataclass
class FractalResult:
    image: Image.Image
    iterations_array: np.ndarray
    escaped_mask: np.ndarray


@_maybe_jit(nopython=True, cache=True)
def _cabs(x: float, y: float) -> float:
    return math.sqrt(x * x + y * y)


@_maybe_jit(nopython=True, cache=True)
def _cpow(x: float, y: float, p: float) -> tuple[float, float]:
    r = math.sqrt(x * x + y * y)
    if r == 0.0:
        return 0.0, 0.0
    theta = math.atan2(y, x)
    rp = math.pow(r, p)
    tp = theta * p
    return rp * math.cos(tp), rp * math.sin(tp)


@_maybe_jit(nopython=True, cache=True)
def _mandelbrot_iter(px: float, py: float, power: float, max_iter: int, bailout: float) -> tuple[int, float]:
    c_x, c_y = px, py
    z_x, z_y = 0.0, 0.0
    bail2 = bailout * bailout
    for i in range(max_iter):
        z_x, z_y = _cpow(z_x, z_y, power)
        z_x += c_x
        z_y += c_y
        d2 = z_x * z_x + z_y * z_y
        if d2 > bail2:
            lzd = math.log(d2) / 2.0
            nu = math.log(lzd / math.log(power if power > 1 else 2.0)) / math.log(power if power > 1 else 2.0) if lzd > 0 else 0.0
            return i, max(0.0, i + 1 - nu)
    return max_iter, float(max_iter)


@_maybe_jit(nopython=True, cache=True)
def _julia_iter(px: float, py: float, power: float, max_iter: int, bailout: float, cx: float, cy: float) -> tuple[int, float]:
    z_x, z_y = px, py
    bail2 = bailout * bailout
    for i in range(max_iter):
        z_x, z_y = _cpow(z_x, z_y, power)
        z_x += cx
        z_y += cy
        d2 = z_x * z_x + z_y * z_y
        if d2 > bail2:
            lzd = math.log(d2) / 2.0
            lp = math.log(power) if power > 1 else math.log(2.0)
            nu = math.log(lzd / lp) / lp if lzd > 0 and lp > 0 else 0.0
            return i, max(0.0, i + 1 - nu)
    return max_iter, float(max_iter)


@_maybe_jit(nopython=True, cache=True)
def _burning_ship_iter(px: float, py: float, power: float, max_iter: int, bailout: float) -> tuple[int, float]:
    c_x, c_y = px, py
    z_x, z_y = 0.0, 0.0
    bail2 = bailout * bailout
    for i in range(max_iter):
        z_x, z_y = _cpow(z_x, z_y, power)
        z_x = abs(z_x) + c_x
        z_y = abs(z_y) + c_y
        d2 = z_x * z_x + z_y * z_y
        if d2 > bail2:
            lzd = math.log(d2) / 2.0
            lp = math.log(power) if power > 1 else math.log(2.0)
            nu = math.log(lzd / lp) / lp if lzd > 0 and lp > 0 else 0.0
            return i, max(0.0, i + 1 - nu)
    return max_iter, float(max_iter)


@_maybe_jit(nopython=True, cache=True)
def _tricorn_iter(px: float, py: float, power: float, max_iter: int, bailout: float) -> tuple[int, float]:
    c_x, c_y = px, py
    z_x, z_y = 0.0, 0.0
    bail2 = bailout * bailout
    for i in range(max_iter):
        z_x, z_y = _cpow(z_x, -z_y, power)
        z_x += c_x
        z_y += c_y
        d2 = z_x * z_x + z_y * z_y
        if d2 > bail2:
            lzd = math.log(d2) / 2.0
            lp = math.log(power) if power > 1 else math.log(2.0)
            nu = math.log(lzd / lp) / lp if lzd > 0 and lp > 0 else 0.0
            return i, max(0.0, i + 1 - nu)
    return max_iter, float(max_iter)


@_maybe_jit(nopython=True, cache=True)
def _phoenix_iter(px: float, py: float, power: float, max_iter: int, bailout: float,
                  pcx: float, pcy: float) -> tuple[int, float]:
    c_x, c_y = px, py
    z_x, z_y = 0.0, 0.0
    zx_prev, zy_prev = 0.0, 0.0
    bail2 = bailout * bailout
    for i in range(max_iter):
        old_x, old_y = z_x, z_y
        z_x, z_y = _cpow(z_x, z_y, power)
        z_x += c_x + pcx * zx_prev
        z_y += c_y + pcy * zy_prev
        zx_prev, zy_prev = old_x, old_y
        d2 = z_x * z_x + z_y * z_y
        if d2 > bail2:
            lzd = math.log(d2) / 2.0
            lp = math.log(power) if power > 1 else math.log(2.0)
            nu = math.log(lzd / lp) / lp if lzd > 0 and lp > 0 else 0.0
            return i, max(0.0, i + 1 - nu)
    return max_iter, float(max_iter)


@_maybe_jit(nopython=True, cache=True)
def _newton_iter(px: float, py: float, power: float, max_iter: int, bailout: float) -> tuple[int, float]:
    z_x, z_y = px, py
    for i in range(max_iter):
        r2 = z_x * z_x + z_y * z_y
        r = math.sqrt(r2)
        if r < 1e-15:
            return i, float(i)
        zn_x, zn_y = _cpow(z_x, z_y, power)
        denom = power * r2
        if abs(denom) < 1e-15:
            return i, float(i)
        nx = z_x - (zn_x * z_x + zn_y * z_y) / denom
        ny = z_y - (zn_y * z_x - zn_x * z_y) / denom
        ddx = nx - z_x
        ddy = ny - z_y
        z_x, z_y = nx, ny
        if math.sqrt(ddx * ddx + ddy * ddy) < 1e-9:
            return i, float(i)
    return max_iter, float(max_iter)


@_maybe_jit(nopython=True, cache=True)
def _nova_iter(px: float, py: float, power: float, max_iter: int, bailout: float, relax: float) -> tuple[int, float]:
    c_x, c_y = px, py
    z_x, z_y = px, py
    for i in range(max_iter):
        r2 = z_x * z_x + z_y * z_y
        r = math.sqrt(r2)
        if r < 1e-15:
            return i, float(i)
        zn_x, zn_y = _cpow(z_x, z_y, power)
        denom = power * r2
        if abs(denom) < 1e-15:
            return i, float(i)
        z_x -= relax * ((zn_x * z_x + zn_y * z_y) / denom - c_x + z_x)
        z_y -= relax * ((zn_y * z_x - zn_x * z_y) / denom - c_y + z_y)
        if abs((px - z_x) * (px - z_x) + (py - z_y) * (py - z_y)) < 1e-18:
            return i, float(i)
    return max_iter, float(max_iter)


@_maybe_jit(nopython=True, cache=True)
def _magnet1_iter(px: float, py: float, max_iter: int, bailout: float) -> tuple[int, float]:
    c_x, c_y = px, py
    z_x, z_y = 0.0, 0.0
    bail2 = bailout * bailout
    for i in range(max_iter):
        r2 = z_x * z_x + z_y * z_y
        r = math.sqrt(r2)
        if abs(r - 1.0) < 1e-15:
            return i, float(i)
        if r > 1e10:
            return i, float(i)
        z_x = z_x * z_x - z_y * z_y + c_x - 1.0
        z_y = 2.0 * z_x * z_y + c_y
        d2 = z_x * z_x + z_y * z_y
        if d2 > bail2:
            return i, float(i)
    return max_iter, float(max_iter)


@_maybe_jit(nopython=True, cache=True)
def _magnet2_iter(px: float, py: float, max_iter: int, bailout: float) -> tuple[int, float]:
    c_x, c_y = px, py
    z_x, z_y = 0.0, 0.0
    bail2 = bailout * bailout
    for i in range(max_iter):
        r2 = z_x * z_x + z_y * z_y
        r = math.sqrt(r2)
        if abs(r - 1.0) < 1e-15:
            return i, float(i)
        if r > 1e10:
            return i, float(i)
        z_x = z_x * z_x - z_y * z_y + c_x
        z_y = 2.0 * z_x * z_y + c_y
        d2 = z_x * z_x + z_y * z_y
        if d2 > bail2:
            return i, float(i)
    return max_iter, float(max_iter)


@_maybe_jit(nopython=True, cache=True)
def _celtic_iter(px: float, py: float, power: float, max_iter: int, bailout: float) -> tuple[int, float]:
    c_x, c_y = px, py
    z_x, z_y = 0.0, 0.0
    bail2 = bailout * bailout
    for i in range(max_iter):
        z_x, z_y = _cpow(abs(z_x), z_y, power)
        z_x += c_x
        z_y += c_y
        d2 = z_x * z_x + z_y * z_y
        if d2 > bail2:
            lzd = math.log(d2) / 2.0
            lp = math.log(power) if power > 1 else math.log(2.0)
            nu = math.log(lzd / lp) / lp if lzd > 0 and lp > 0 else 0.0
            return i, max(0.0, i + 1 - nu)
    return max_iter, float(max_iter)


@_maybe_jit(nopython=True, cache=True)
def _buffalo_iter(px: float, py: float, power: float, max_iter: int, bailout: float) -> tuple[int, float]:
    c_x, c_y = px, py
    z_x, z_y = 0.0, 0.0
    bail2 = bailout * bailout
    for i in range(max_iter):
        z_x, z_y = _cpow(z_x, z_y, power)
        z_x = abs(z_x) + c_x
        z_y = -abs(z_y) + c_y
        d2 = z_x * z_x + z_y * z_y
        if d2 > bail2:
            lzd = math.log(d2) / 2.0
            lp = math.log(power) if power > 1 else math.log(2.0)
            nu = math.log(lzd / lp) / lp if lzd > 0 and lp > 0 else 0.0
            return i, max(0.0, i + 1 - nu)
    return max_iter, float(max_iter)


@_maybe_jit(nopython=True, cache=True)
def _perp_ship_iter(px: float, py: float, power: float, max_iter: int, bailout: float) -> tuple[int, float]:
    c_x, c_y = px, py
    z_x, z_y = 0.0, 0.0
    bail2 = bailout * bailout
    for i in range(max_iter):
        z_x, z_y = _cpow(z_x, z_y, power)
        tmp = abs(z_x) + c_x
        z_y = -abs(z_y) + c_y
        z_x = tmp
        d2 = z_x * z_x + z_y * z_y
        if d2 > bail2:
            lzd = math.log(d2) / 2.0
            lp = math.log(power) if power > 1 else math.log(2.0)
            nu = math.log(lzd / lp) / lp if lzd > 0 and lp > 0 else 0.0
            return i, max(0.0, i + 1 - nu)
    return max_iter, float(max_iter)


@_maybe_jit(nopython=True, cache=True)
def _multicorn_iter(px: float, py: float, power: float, max_iter: int, bailout: float) -> tuple[int, float]:
    c_x, c_y = px, py
    z_x, z_y = 0.0, 0.0
    bail2 = bailout * bailout
    for i in range(max_iter):
        z_x, z_y = _cpow(z_x, -z_y, power)
        z_x += c_x
        z_y += c_y
        d2 = z_x * z_x + z_y * z_y
        if d2 > bail2:
            lzd = math.log(d2) / 2.0
            lp = math.log(power) if power > 1 else math.log(2.0)
            nu = math.log(lzd / lp) / lp if lzd > 0 and lp > 0 else 0.0
            return i, max(0.0, i + 1 - nu)
    return max_iter, float(max_iter)


def _buddhabrot_iter(px: float, py: float, max_iter: int, bailout: float) -> list[tuple[float, float]]:
    c_x, c_y = px, py
    z_x, z_y = 0.0, 0.0
    bail2 = bailout * bailout
    path = []
    for i in range(max_iter):
        path.append((z_x, z_y))
        nz_x = z_x * z_x - z_y * z_y + c_x
        nz_y = 2.0 * z_x * z_y + c_y
        z_x, z_y = nz_x, nz_y
        d2 = z_x * z_x + z_y * z_y
        if d2 > bail2:
            return path
    return []


@_maybe_jit(nopython=True, cache=True)
def _marsaglia_theta(rng_state: np.ndarray) -> tuple[float, float, np.ndarray]:
    import random as _pyrandom
    while True:
        u1 = _pyrandom.random() * 2.0 - 1.0
        u2 = _pyrandom.random() * 2.0 - 1.0
        s = u1 * u1 + u2 * u2
        if 0.0 < s < 1.0:
            break
    norm = math.sqrt(-2.0 * math.log(s) / s)
    return u1 * norm, u2 * norm, rng_state


def _render_buddhabrot(width: int, height: int, params: FractalParams,
                       cancel_token: CancelToken | None = None,
                       progress_cb: Callable[[int], None] | None = None) -> np.ndarray:
    h, w = height, width
    sx = params.scale
    sy = params.scale * height / width
    x_min = params.cx - sx / 2
    y_min = params.cy - sy / 2
    dx = sx / width
    dy = sy / height
    hist = np.zeros((h, w), dtype=np.float64)
    n_samples = max(50000, width * height * 4)
    import random
    rng = random.Random(42)
    step = n_samples // 20
    for s in range(n_samples):
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()
        c_x = random.uniform(x_min - 0.2, x_min + sx + 0.2)
        c_y = random.uniform(y_min - 0.2, y_min + sy + 0.2)
        path = _buddhabrot_iter(c_x, c_y, params.iterations, params.bailout)
        for (z_x, z_y) in path:
            px = int((z_x - x_min) / dx)
            py = int((z_y - y_min) / dy)
            if 0 <= px < w and 0 <= py < h:
                hist[py, px] += 1.0
        if progress_cb is not None and step > 0 and s % step == 0:
            progress_cb(int(100 * s // n_samples))
    if progress_cb is not None:
        progress_cb(100)
    if hist.max() == 0:
        return np.zeros((h, w, 3), dtype=np.uint8)
    log_hist = np.log(1.0 + hist)
    log_max = log_hist.max()
    norm = log_hist / log_max
    out = np.zeros((h, w, 3), dtype=np.uint8)
    out[..., 0] = (255 * norm).astype(np.uint8)
    out[..., 1] = (180 * norm).astype(np.uint8)
    out[..., 2] = (90 * norm).astype(np.uint8)
    return out


_2D_FORMULAS = {}


def _register_2d_formula(key: str, zh_name: str, dimension: int,
                         can_power: bool, can_julia: bool, can_phoenix: bool,
                         can_nova: bool, default_power: float,
                         escape_fn: Callable, is_density: bool = False,
                         is_geometric: bool = False,
                         extra_defaults: dict | None = None,
                         can_bailout: bool = True,
                         can_iterations: bool = True):
    _2D_FORMULAS[key] = {
        "key": key,
        "zh_name": zh_name,
        "dimension": dimension,
        "can_power": can_power,
        "can_julia": can_julia,
        "can_phoenix": can_phoenix,
        "can_nova": can_nova,
        "default_power": default_power,
        "escape_fn": escape_fn,
        "is_density": is_density,
        "is_geometric": is_geometric,
        "extra_defaults": extra_defaults or {},
        "can_bailout": can_bailout,
        "can_iterations": can_iterations,
    }


def _all_2d_formula_keys() -> list[str]:
    return list(_2D_FORMULAS.keys())


def _formula_info(key: str) -> dict | None:
    return _2D_FORMULAS.get(key)


def _register_all_2d_formulas() -> None:
    if _2D_FORMULAS:
        return

    _register_2d_formula("mandelbrot", "Mandelbrot集", DIM_2D,
                          True, False, False, False, 2.0, _mandelbrot_iter)
    _register_2d_formula("multibrot", "Multibrot", DIM_2D,
                          True, False, False, False, 3.0, _mandelbrot_iter)
    _register_2d_formula("julia", "Julia集", DIM_2D,
                          True, True, False, False, 2.0, _julia_iter)
    _register_2d_formula("burning_ship", "Burning Ship", DIM_2D,
                          True, False, False, False, 2.0, _burning_ship_iter)
    _register_2d_formula("tricorn", "Tricorn", DIM_2D,
                          True, False, False, False, 2.0, _tricorn_iter)
    _register_2d_formula("multicorn", "Multicorn", DIM_2D,
                          True, False, False, False, 3.0, _multicorn_iter)
    _register_2d_formula("celtic", "Celtic", DIM_2D,
                          True, False, False, False, 2.0, _celtic_iter)
    _register_2d_formula("buffalo", "Buffalo", DIM_2D,
                          True, False, False, False, 2.0, _buffalo_iter)
    _register_2d_formula("perpendicular_burning_ship", "Perpendicular Burning Ship", DIM_2D,
                          True, False, False, False, 2.0, _perp_ship_iter)
    _register_2d_formula("phoenix", "Phoenix", DIM_2D,
                          True, False, True, False, 2.0, _phoenix_iter)
    _register_2d_formula("newton", "Newton", DIM_2D,
                          True, False, False, False, 3.0, _newton_iter, can_bailout=False)
    _register_2d_formula("nova", "Nova", DIM_2D,
                          True, False, False, True, 3.0, _nova_iter, can_bailout=False)
    _register_2d_formula("magnet_i", "Magnet I", DIM_2D,
                          False, False, False, False, 2.0, _magnet1_iter)
    _register_2d_formula("magnet_ii", "Magnet II", DIM_2D,
                          False, False, False, False, 2.0, _magnet2_iter)
    _register_2d_formula("buddhabrot", "Buddhabrot", DIM_2D,
                          False, False, False, False, 2.0, None, is_density=True)


_register_all_2d_formulas()


_ESCAPE_FN_SIGNATURES = {
    "mandelbrot": "ppb",
    "multibrot": "ppb",
    "julia": "ppbjj",
    "burning_ship": "ppb",
    "tricorn": "ppb",
    "multicorn": "ppb",
    "celtic": "ppb",
    "buffalo": "ppb",
    "perpendicular_burning_ship": "ppb",
    "phoenix": "ppbpc",
    "newton": "ppb",
    "nova": "ppbr",
    "magnet_i": "ppb",
    "magnet_ii": "ppb",
}


def _call_escape(fn_key: str, params: FractalParams, px: float, py: float) -> tuple[int, float]:
    info = _2D_FORMULAS[fn_key]
    fn = info["escape_fn"]
    power = params.power if info["can_power"] else info["default_power"]
    if fn_key == "magnet_i" or fn_key == "magnet_ii":
        return fn(px, py, params.iterations, params.bailout)
    if fn_key == "julia":
        return fn(px, py, power, params.iterations, params.bailout, params.julia_c.real, params.julia_c.imag)
    elif fn_key == "phoenix":
        return fn(px, py, power, params.iterations, params.bailout, params.phoenix_c.real, params.phoenix_c.imag)
    elif fn_key == "nova":
        return fn(px, py, power, params.iterations, params.bailout, params.nova_relaxation)
    else:
        return fn(px, py, power, params.iterations, params.bailout)


def _escape_time_row(row: int, width: int, height: int, params: FractalParams,
                     fn_key: str) -> tuple[np.ndarray, np.ndarray]:
    h, w = height, width
    sx = params.scale
    sy = params.scale * height / width
    x_min = params.cx - sx / 2
    y_center = params.cy
    dy = sy / h
    y = y_center - sy / 2 + dy * row + dy / 2
    xs = x_min + sx / w * (np.arange(w) + 0.5)
    iters = np.zeros(w, dtype=np.int32)
    smooth = np.zeros(w, dtype=np.float64)
    for j in range(w):
        i, s = _call_escape(fn_key, params, float(xs[j]), y)
        iters[j] = i
        smooth[j] = s
    return iters, smooth


def _render_2d(width: int, height: int, formula_key: str, params: FractalParams,
               cancel_token: CancelToken | None = None,
               progress_cb: Callable[[int], None] | None = None) -> FractalResult:
    params.validate()
    info = _2D_FORMULAS[formula_key]
    if info is None:
        raise ValueError(f"Unknown 2D fractal formula: {formula_key}")

    if info["is_density"]:
        rgb = _render_buddhabrot(width, height, params, cancel_token, progress_cb)
        img = Image.fromarray(rgb, "RGB")
        return FractalResult(image=img, iterations_array=np.zeros((height, width), dtype=np.int32),
                             escaped_mask=np.ones((height, width), dtype=bool))

    h, w = height, width
    iters_full = np.zeros((h, w), dtype=np.int32)
    smooth_full = np.zeros((h, w), dtype=np.float64)
    row_step = max(1, h // 50)

    for row in range(h):
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()
        iters, sm = _escape_time_row(row, w, h, params, formula_key)
        iters_full[row] = iters
        smooth_full[row] = sm
        if progress_cb is not None and (row % row_step == 0 or row == h - 1):
            progress_cb(int(100 * (row + 1) / h))

    if progress_cb is not None:
        progress_cb(100)

    max_iter = params.iterations
    escaped = iters_full < max_iter
    iterations_norm = np.clip(smooth_full / float(max_iter), 0.0, 1.0)

    coloring = params.coloring
    if coloring == FractalColoring.GRAYSCALE:
        gray = np.where(escaped, iterations_norm, 0.0)
        gray = (gray * 255.0).astype(np.uint8)
        rgb = np.stack([gray, gray, gray], axis=-1)
    elif coloring == FractalColoring.BANDED:
        band_vals = np.where(escaped, iters_full % 256, 0)
        rgb = _apply_gradient(band_vals.astype(np.float64) / 255.0)
    else:
        rgb = _apply_gradient(iterations_norm)

    rgb = np.where(escaped[..., None], rgb, np.array([0, 0, 0], dtype=np.uint8))
    img = Image.fromarray(rgb, "RGB")
    return FractalResult(image=img, iterations_array=iters_full, escaped_mask=escaped)


def _apply_gradient(norm: np.ndarray) -> np.ndarray:
    w, h = norm.shape[:2]
    flat = norm.ravel()
    flat = np.clip(flat, 0.0, 1.0)
    r = np.floor(255 * flat).astype(np.uint8)
    g = np.floor(255 * np.clip(0.5 + 0.5 * np.sin(6.283185 * flat + 2.4), 0.0, 1.0)).astype(np.uint8)
    b = np.floor(255 * np.clip(0.5 + 0.5 * np.sin(6.283185 * flat + 5.0), 0.0, 1.0)).astype(np.uint8)
    out = np.stack([r, g, b], axis=-1).reshape(w, h, 3)
    return out


def render_fractal(width: int, height: int, formula_key: str,
                   params: FractalParams | None = None,
                   cancel_token: CancelToken | None = None,
                   progress_cb: Callable[[int], None] | None = None) -> FractalResult:
    if params is None:
        params = FractalParams(width=width, height=height)
    params.validate()
    info = _2D_FORMULAS.get(formula_key)
    if info is None:
        raise ValueError(f"Unknown fractal formula: {formula_key}")
    params.width = width
    params.height = height
    return _render_2d(width, height, formula_key, params, cancel_token, progress_cb)


_3D_FORMULAS = {}


@dataclass
class Fractal3DCamera:
    distance: float = 3.2
    yaw: float = 0.0
    pitch: float = 25.0
    fov: float = 60.0


def _ray_march_mandelbulb(ox: float, oy: float, oz: float, dx: float, dy: float, dz: float,
                          power: float, iterations: int, max_dist: float) -> float:
    x, y, z = ox, oy, oz
    total_dist = 0.0
    bailout = 1e10
    max_steps = 64
    for _ in range(max_steps):
        r2 = x * x + y * y + z * z
        r = math.sqrt(r2)
        if r > bailout:
            return total_dist
        if r < 1e-12:
            return total_dist + 1e-6
        theta = math.acos(max(-1.0, min(1.0, z / r)))
        phi = math.atan2(y, x)
        rp = math.pow(r, power)
        new_theta = theta * power
        new_phi = phi * power
        x = rp * math.sin(new_theta) * math.cos(new_phi) + ox
        y = rp * math.sin(new_theta) * math.sin(new_phi) + oy
        z = rp * math.cos(new_theta) + oz
        de = 0.0
        dr = power * math.pow(r, power - 1.0)
        if dr > 0:
            de = 0.5 * math.log(r) * r / dr
        total_dist += de
        ox += dx * de
        oy += dy * de
        oz += dz * de
        x, y, z = ox, oy, oz
        if total_dist > max_dist:
            return total_dist
    return total_dist


def _render_mandelbulb(width: int, height: int, power: float, iterations: int,
                        camera: Fractal3DCamera | None = None,
                        cancel_token: CancelToken | None = None,
                        progress_cb: Callable[[int], None] | None = None) -> FractalResult:
    if camera is None:
        camera = Fractal3DCamera()
    w, h = width, height
    cx, cy = w / 2.0, h / 2.0
    fov_rad = math.radians(camera.fov)
    scale = math.tan(fov_rad / 2.0)
    yaw_rad = math.radians(camera.yaw)
    pitch_rad = math.radians(camera.pitch)
    cy, sp = math.cos(yaw_rad), math.sin(yaw_rad)
    cp, snp = math.cos(pitch_rad), math.sin(pitch_rad)
    out = np.zeros((h, w, 3), dtype=np.uint8)
    max_dist = 10.0
    row_step = max(1, h // 50)
    for j in range(h):
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()
        v = (j - cy) / cy * scale
        for i in range(w):
            u = (i - cx) / cx * scale
            dx = u * cp * cy - v * snp * cy + sp * snp
            dy = u * snp * cp + v * cp * cp - sp * snp
            dz = -u * sp + v * snp + cp
            dlen = math.sqrt(dx * dx + dy * dy + dz * dz)
            dx, dy, dz = dx / dlen, dy / dlen, dz / dlen
            ox, oy, oz = 0.0, 0.0, camera.distance
            dist = _ray_march_mandelbulb(ox, oy, oz, dx, dy, dz, power, iterations, max_dist)
            if dist < max_dist - 0.01:
                alpha = max(0.0, 1.0 - dist / max_dist)
                out[j, i] = (int(255 * alpha), int(180 * alpha), int(100 * alpha))
        if progress_cb is not None and (j % row_step == 0 or j == h - 1):
            progress_cb(int(100 * (j + 1) / h))
    if progress_cb is not None:
        progress_cb(100)
    iters = np.zeros((h, w), dtype=np.int32)
    return FractalResult(image=Image.fromarray(out, "RGB"), iterations_array=iters, escaped_mask=np.ones((h, w), dtype=bool))


def render_mandelbulb(width: int, height: int, power: float = 8.0,
                       iterations: int = 64,
                       cancel_token: CancelToken | None = None,
                       progress_cb: Callable[[int], None] | None = None) -> FractalResult:
    return _render_mandelbulb(width, height, power, iterations, None, cancel_token, progress_cb)


__all__ = [
    "FractalColoring", "FractalParams", "FractalResult",
    "JuliaConstant", "PhoenixConstant", "Fractal3DCamera",
    "DIM_2D", "DIM_3D",
    "render_fractal", "render_mandelbulb",
    "formula_keys", "formula_info",
    "register_fractal_filters",
]


def formula_keys() -> list[str]:
    return _all_2d_formula_keys()


def formula_info(key: str) -> dict | None:
    return _formula_info(key)


def _make_processor(formula_key: str):
    info = _2D_FORMULAS[formula_key]

    def processor(img, cx=-0.5, cy=0.0, scale=3.0, power=2.0,
                  iterations=256, bailout=2.0, coloring="smooth",
                  julia_c_x=-0.8, julia_c_y=0.156,
                  phoenix_c_x=-0.5, phoenix_c_y=0.0,
                  nova_relaxation=1.0,
                  width_override=0, height_override=0,
                  cancel_token=None):
        h, w = img.shape[:2] if img is not None else (512, 512)
        if width_override > 0:
            w = width_override
        if height_override > 0:
            h = height_override
        params = FractalParams(
            width=w, height=h,
            cx=cx, cy=cy, scale=scale,
            power=power if info["can_power"] else info["default_power"],
            iterations=iterations,
            bailout=bailout if info["can_bailout"] else 2.0,
            coloring=FractalColoring(coloring),
            julia_c=JuliaConstant(real=julia_c_x, imag=julia_c_y),
            phoenix_c=PhoenixConstant(real=phoenix_c_x, imag=phoenix_c_y),
            nova_relaxation=nova_relaxation,
        )
        result = render_fractal(w, h, formula_key, params, cancel_token=cancel_token)
        return np.array(result.image)

    processor.__name__ = f"apply_fractal_{formula_key}"
    processor.__qualname__ = processor.__name__
    return processor


def register_fractal_filters() -> int:
    from processors.filter_defs import (
        register_filter, FilterDefRegistry, FilterCategory,
        FilterParam, PARAM_TYPE_INT, PARAM_TYPE_FLOAT, PARAM_TYPE_ENUM, PARAM_TYPE_BOOL,
    )

    reg = FilterDefRegistry.instance()
    count = 0
    for formula_key, info in _2D_FORMULAS.items():
        defn_key = f"fractal_{formula_key}"
        if reg.has(defn_key):
            continue

        processor = _make_processor(formula_key)
        params: list[FilterParam] = []

        params.append(FilterParam(
            name="cx", label="中心 X", type=PARAM_TYPE_FLOAT,
            default=info.get("extra_defaults", {}).get("cx", -0.5),
            minimum=-10.0, maximum=10.0, step=0.01,
        ))
        params.append(FilterParam(
            name="cy", label="中心 Y", type=PARAM_TYPE_FLOAT,
            default=info.get("extra_defaults", {}).get("cy", 0.0),
            minimum=-10.0, maximum=10.0, step=0.01,
        ))
        params.append(FilterParam(
            name="scale", label="缩放范围", type=PARAM_TYPE_FLOAT,
            default=info.get("extra_defaults", {}).get("scale", 3.0),
            minimum=0.01, maximum=100.0, step=0.01,
        ))

        if info["can_power"]:
            params.append(FilterParam(
                name="power", label="幂次 (power)", type=PARAM_TYPE_FLOAT,
                default=info["default_power"],
                minimum=1.0, maximum=10.0, step=0.1,
            ))

        params.append(FilterParam(
            name="iterations", label="迭代次数", type=PARAM_TYPE_INT,
            default=info.get("extra_defaults", {}).get("iterations", 256),
            minimum=10, maximum=2048, step=10,
        ))

        if info["can_bailout"]:
            params.append(FilterParam(
                name="bailout", label="逃逸半径 (bailout)", type=PARAM_TYPE_FLOAT,
                default=info.get("extra_defaults", {}).get("bailout", 2.0),
                minimum=1.0, maximum=1000.0, step=0.1,
            ))

        params.append(FilterParam(
            name="coloring", label="着色模式", type=PARAM_TYPE_ENUM,
            default="smooth",
            choices=["smooth", "banded", "grayscale"],
        ))

        if info["can_julia"]:
            params.append(FilterParam(
                name="julia_c_x", label="Julia 常数 Re", type=PARAM_TYPE_FLOAT,
                default=-0.8, minimum=-10.0, maximum=10.0, step=0.01,
            ))
            params.append(FilterParam(
                name="julia_c_y", label="Julia 常数 Im", type=PARAM_TYPE_FLOAT,
                default=0.156, minimum=-10.0, maximum=10.0, step=0.01,
            ))

        if info["can_phoenix"]:
            params.append(FilterParam(
                name="phoenix_c_x", label="Phoenix 常数 Re", type=PARAM_TYPE_FLOAT,
                default=-0.5, minimum=-10.0, maximum=10.0, step=0.01,
            ))
            params.append(FilterParam(
                name="phoenix_c_y", label="Phoenix 常数 Im", type=PARAM_TYPE_FLOAT,
                default=0.0, minimum=-10.0, maximum=10.0, step=0.01,
            ))

        if info["can_nova"]:
            params.append(FilterParam(
                name="nova_relaxation", label="Nova 松弛系数", type=PARAM_TYPE_FLOAT,
                default=1.0, minimum=0.0, maximum=5.0, step=0.01,
            ))

        register_filter(
            key=defn_key,
            display_name=f"分形 · {info['zh_name']}",
            processor=processor,
            category=FilterCategory.FRACTAL,
            params=params,
            description=f"2D {info['zh_name']} 分形生成",
            preview_supported=True,
            batch_supported=True,
        )
        count += 1

    return count
