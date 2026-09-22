from __future__ import annotations

import math

import cv2
import numpy as np

from .utils import ensure_rgb, u8, clamp


def linear_gradient(width: int, height: int, color_a=(255, 0, 128), color_b=(0, 255, 255),
                    angle: float = 0.0) -> np.ndarray:
    h, w = height, width
    rad = math.radians(angle)
    x, y = np.meshgrid(np.arange(w), np.arange(h))
    dx = x - w / 2
    dy = y - h / 2
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    proj = dx * cos_a + dy * sin_a
    proj_min = proj.min()
    proj_max = proj.max()
    t = (proj - proj_min) / (proj_max - proj_min + 1e-6)

    ca = np.array(color_a, dtype=np.float32)
    cb = np.array(color_b, dtype=np.float32)
    grad = ca[None, None, :] * (1 - t[..., None]) + cb[None, None, :] * t[..., None]
    return u8(clamp(grad))


def radial_gradient(width: int, height: int, color_a=(255, 0, 128), color_b=(0, 255, 255),
                     cx: float = 0.5, cy: float = 0.5) -> np.ndarray:
    h, w = height, width
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    center_x, center_y = cx * w, cy * h
    dist = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
    max_dist = np.sqrt(max(center_x, w - center_x) ** 2 + max(center_y, h - center_y) ** 2)
    t = dist / (max_dist + 1e-6)
    t = np.clip(t, 0, 1)

    ca = np.array(color_a, dtype=np.float32)
    cb = np.array(color_b, dtype=np.float32)
    grad = ca[None, None, :] * (1 - t[..., None]) + cb[None, None, :] * t[..., None]
    return u8(clamp(grad))


def mesh_gradient(width: int, height: int, control_colors: list[list[tuple]],
                  cx_positions: list[float] | None = None,
                  cy_positions: list[float] | None = None) -> np.ndarray:
    h, w = height, width
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)

    ca = np.array(control_colors, dtype=np.float32)
    rows = len(ca)
    cols = len(ca[0]) if rows > 0 else 0

    if cx_positions is None:
        cx_positions = [i / (cols - 1) for i in range(cols)] if cols > 1 else [0.5]
    if cy_positions is None:
        cy_positions = [i / (rows - 1) for i in range(rows)] if rows > 1 else [0.5]

    cx_arr = np.array(cx_positions) * w
    cy_arr = np.array(cy_positions) * h

    result = np.zeros((h, w, 3), dtype=np.float32)
    for c in range(3):
        ctrl_vals = ca[:, :, c]
        result[..., c] = _bilinear_grid(x, y, cx_arr, cy_arr, ctrl_vals)

    return u8(clamp(result))


def _bilinear_grid(x, y, cx, cy, ctrl_vals):
    h, w = x.shape
    rows = len(cy)
    cols = len(cx)
    out = np.zeros((h, w), dtype=np.float32)

    for j in range(rows - 1):
        for i in range(cols - 1):
            x0, x1 = cx[i], cx[i + 1]
            y0, y1 = cy[j], cy[j + 1]
            v00, v10 = ctrl_vals[j, i], ctrl_vals[j, i + 1]
            v01, v11 = ctrl_vals[j + 1, i], ctrl_vals[j + 1, i + 1]

            mask = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
            if not mask.any() or x0 == x1 or y0 == y1:
                continue

            t = (x - x0) / max(1e-6, x1 - x0)
            u = (y - y0) / max(1e-6, y1 - y0)
            a = v00 * (1 - t) + v10 * t
            b = v01 * (1 - t) + v11 * t
            val = a * (1 - u) + b * u
            out[mask] = val[mask]
    return out


PIRETTI_MESH = [
    [(255, 0, 128), (0, 255, 255), (128, 0, 255), (255, 128, 0)],
    [(0, 128, 255), (255, 255, 0), (128, 0, 255), (255, 0, 128)],
    [(255, 255, 0), (0, 255, 128), (0, 128, 255), (128, 255, 0)],
    [(128, 0, 255), (128, 255, 0), (255, 0, 128), (0, 255, 128)],
]

SUNSET_MESH = [
    [(50, 0, 100), (150, 0, 150), (255, 100, 50), (255, 200, 100)],
    [(100, 0, 150), (200, 50, 100), (255, 150, 50), (255, 200, 150)],
    [(150, 50, 100), (255, 100, 100), (255, 150, 100), (255, 200, 200)],
    [(200, 100, 100), (255, 150, 150), (255, 200, 150), (255, 255, 255)],
]

OCEAN_MESH = [
    [(0, 20, 50), (0, 50, 100), (0, 100, 150), (0, 150, 200)],
    [(0, 30, 80), (0, 80, 130), (0, 130, 180), (50, 180, 220)],
    [(0, 50, 110), (20, 110, 160), (60, 150, 200), (100, 200, 240)],
    [(30, 80, 140), (80, 150, 200), (150, 200, 230), (200, 230, 255)],
]

MESH_PRESETS = {
    "piretti": PIRETTI_MESH,
    "sunset": SUNSET_MESH,
    "ocean": OCEAN_MESH,
}
