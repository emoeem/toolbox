from __future__ import annotations

import json
import math

import cv2
import numpy as np

from .utils import ensure_rgb, u8, clamp


def lut_identity() -> np.ndarray:
    return np.arange(256, dtype=np.uint8)


def lut_invert() -> np.ndarray:
    return (255 - np.arange(256, dtype=np.uint8)).astype(np.uint8)


def lut_contrast(c: float = 1.0) -> np.ndarray:
    mid = 127.5
    vals = c * (np.arange(256, dtype=np.float32) - mid) + mid
    return u8(clamp(vals)).astype(np.uint8)


def lut_sqrt() -> np.ndarray:
    vals = np.sqrt(np.arange(256, dtype=np.float32) / 255.0) * 255
    return u8(clamp(vals)).astype(np.uint8)


def lut_power(gamma: float = 1.0) -> np.ndarray:
    vals = np.power(np.arange(256, dtype=np.float32) / 255.0, gamma) * 255
    return u8(clamp(vals)).astype(np.uint8)


def apply_lut(img: np.ndarray, lut: np.ndarray | list, channel: str = "all") -> np.ndarray:
    img_ = ensure_rgb(img)
    lut_arr = np.array(lut, dtype=np.uint8).ravel()
    result = img_.copy()
    if channel == "all":
        result = cv2.LUT(result, lut_arr)
    elif channel == "R":
        result[:, :, 0] = cv2.LUT(result[:, :, 0], lut_arr)
    elif channel == "G":
        result[:, :, 1] = cv2.LUT(result[:, :, 1], lut_arr)
    elif channel == "B":
        result[:, :, 2] = cv2.LUT(result[:, :, 2], lut_arr)
    return u8(clamp(result))


def load_lut_from_cube(path: str | Path) -> np.ndarray | None:
    try:
        with open(path) as f:
            lines = f.readlines()
        lut_data = []
        size = 33
        for line in lines:
            line = line.strip()
            if line.startswith("LUT_3D_SIZE"):
                size = int(line.split()[-1])
            elif line and not line.startswith("#") and not line.upper().startswith(("TITLE", "LUT", "DOMAIN", "PARAM")):
                parts = line.split()
                if len(parts) == 3:
                    lut_data.append([float(parts[0]), float(parts[1]), float(parts[2])])
        if not lut_data:
            return None
        arr = np.array(lut_data, dtype=np.float32)
        arr = np.clip(arr, 0, 1) * 255
        return u8(clamp(arr)).astype(np.uint8).reshape(size, size, size, 3)
    except Exception:
        return None


def apply_cube_lut(img: np.ndarray, cube_lut: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    h, w = img_.shape[:2]
    size = cube_lut.shape[0]
    src = img_.reshape(-1, 3)[:, ::-1].copy()
    lut = cube_lut.reshape(size, -1, 3).astype(np.float32)
    out = cv2.transform(src.reshape(1, -1, 3), lut).reshape(h, w, -1, 3)
    result = out[:, :, 0, ::-1]
    return u8(clamp(result * 255))


LUT_PRESETS = {
    "标准": lut_identity,
    "反色": lut_invert,
    "高对比度": lambda: lut_contrast(1.5),
    "低对比度": lambda: lut_contrast(0.7),
    "平方根": lut_sqrt,
    "伽马 0.5": lambda: lut_power(0.5),
    "伽马 2.0": lambda: lut_power(2.0),
    "伽马 2.2": lambda: lut_power(2.2),
}


def tone_curve(img: np.ndarray, points: list[tuple[int, int]] | np.ndarray) -> np.ndarray:
    pts = np.array(sorted(points, key=lambda p: p[0]) if isinstance(points, list) else points,
                   dtype=np.float32)
    xs = pts[:, 0] if pts.ndim == 2 else pts
    ys = pts[:, 1] if pts.ndim == 2 else pts
    xs = np.concatenate([[0], xs, [255]])
    ys = np.concatenate([[0], ys, [255]])
    lut = np.interp(np.arange(256), xs, ys, left=ys[0], right=ys[-1])
    lut = np.clip(lut, 0, 255).astype(np.uint8)
    return apply_lut(img, lut)
