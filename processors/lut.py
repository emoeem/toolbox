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
    """3D .cube LUT 应用：对 size×size×size×3 查找表逐像素三线性插值。

    cube_lut 轴序与 load_lut_from_cube 的 reshape(size, size, size, 3) 对齐：
    .cube 数据行红分量变化最快，故 cube[b_idx, g_idx, r_idx] 为该网格点的
    输出 RGB（0-255）。此前实现误用 cv2.transform（NxK 矩阵乘，非查找表），
    对非 2 立方或任意图像必在 reshape(h, w, -1, 3) 处抛
    “cannot reshape array of size … into shape (h, w, newaxis, 3)”
    ——tests/test_worker_assist.py LutTests.test_apply_success 曾因此失败。
    """
    img_ = ensure_rgb(img)
    # ensure_rgb 仅保证 3 通道（GRAY/RGBA→RGB），通道序保持 cv2 的 BGR。
    h, w = img_.shape[:2]
    size = cube_lut.shape[0]
    # 像素值（BGR 0-255）→ RGB 归一化 → 网格分数坐标 [0, size-1]
    rgb = img_.astype(np.float32)[..., ::-1] / 255.0
    coord = np.clip(rgb, 0.0, 1.0) * float(size - 1)
    lo = np.floor(coord).astype(np.intp)
    frac = coord - lo
    hi = np.minimum(lo + 1, size - 1)
    # 网格轴序 [..., b, g, r]；每通道各自的整数/分数坐标
    b0, b1, bf = lo[..., 2], hi[..., 2], frac[..., 2]
    g0, g1, gf = lo[..., 1], hi[..., 1], frac[..., 1]
    r0, r1, rf = lo[..., 0], hi[..., 0], frac[..., 0]

    def _at(bi, gi, ri):
        return cube_lut[bi, gi, ri].astype(np.float32)  # 高级索引 → (h, w, 3)

    # 逐轴线性混合：先红、再绿、最后蓝
    rf = rf[..., None]
    c00 = _at(b0, g0, r0) * (1.0 - rf) + _at(b0, g0, r1) * rf
    c01 = _at(b0, g1, r0) * (1.0 - rf) + _at(b0, g1, r1) * rf
    c10 = _at(b1, g0, r0) * (1.0 - rf) + _at(b1, g0, r1) * rf
    c11 = _at(b1, g1, r0) * (1.0 - rf) + _at(b1, g1, r1) * rf
    gf = gf[..., None]
    c0 = c00 * (1.0 - gf) + c01 * gf
    c1 = c10 * (1.0 - gf) + c11 * gf
    bf = bf[..., None]
    out_rgb = c0 * (1.0 - bf) + c1 * bf
    # RGB → BGR 回写，保持仓库其余处理器的 cv2 通道约定
    return u8(clamp(out_rgb[..., ::-1]))


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
