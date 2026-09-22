from __future__ import annotations

import math

import cv2
import numpy as np

from .utils import ensure_rgb, u8, clamp


def stack_horizontal(images: list[np.ndarray], padding: int = 0,
                     bg_color=(0, 0, 0)) -> np.ndarray:
    imgs = [ensure_rgb(img) for img in images]
    h = max(img.shape[0] for img in imgs)
    resized = []
    for img in imgs:
        if img.shape[0] != h:
            ratio = h / img.shape[0]
            w = int(img.shape[1] * ratio)
            resized.append(cv2.resize(img, (w, h)))
        else:
            resized.append(img)
    total_w = sum(img.shape[1] for img in resized) + padding * (len(resized) - 1)
    result = np.full((h, total_w, 3), bg_color, dtype=np.uint8)
    x = 0
    for img in resized:
        result[:, x:x + img.shape[1]] = img
        x += img.shape[1] + padding
    return result


def stack_vertical(images: list[np.ndarray], padding: int = 0,
                    bg_color=(0, 0, 0)) -> np.ndarray:
    imgs = [ensure_rgb(img) for img in images]
    w = max(img.shape[1] for img in imgs)
    resized = []
    for img in imgs:
        if img.shape[1] != w:
            ratio = w / img.shape[1]
            h = int(img.shape[0] * ratio)
            resized.append(cv2.resize(img, (w, h)))
        else:
            resized.append(img)
    total_h = sum(img.shape[0] for img in resized) + padding * (len(resized) - 1)
    result = np.full((total_h, w, 3), bg_color, dtype=np.uint8)
    y = 0
    for img in resized:
        result[y:y + img.shape[0], :] = img
        y += img.shape[0] + padding
    return result


def grid_stack(images: list[np.ndarray], cols: int, padding: int = 0,
               bg_color=(0, 0, 0), equal_size: bool = True) -> np.ndarray:
    if not images:
        raise ValueError("需要至少一张图片")
    imgs = [ensure_rgb(img) for img in images]
    n = len(imgs)
    rows = math.ceil(n / cols)
    if equal_size:
        cell_h = max(img.shape[0] for img in imgs)
        cell_w = max(img.shape[1] for img in imgs)
        resized = []
        for img in imgs:
            rh = cell_h / img.shape[0]
            rw = cell_w / img.shape[1]
            r = min(rh, rw)
            nh, nw = int(img.shape[0] * r), int(img.shape[1] * r)
            resized_img = cv2.resize(img, (nw, nh))
            canvas = np.full((cell_h, cell_w, 3), bg_color, dtype=np.uint8)
            cy = (cell_h - nh) // 2
            cx = (cell_w - nw) // 2
            canvas[cy:cy + nh, cx:cx + nw] = resized_img
            resized.append(canvas)
    else:
        cell_h = max(img.shape[0] for img in imgs)
        cell_w = max(img.shape[1] for img in imgs)
        resized = [cv2.resize(img, (cell_w, cell_h)) for img in imgs]

    total_h = rows * cell_h + padding * (rows - 1)
    total_w = cols * cell_w + padding * (cols - 1)
    result = np.full((total_h, total_w, 3), bg_color, dtype=np.uint8)
    for idx, img in enumerate(resized):
        row, col = divmod(idx, cols)
        y = row * (cell_h + padding)
        x = col * (cell_w + padding)
        result[y:y + cell_h, x:x + cell_w] = img
    return result


def split_grid(img: np.ndarray, rows: int, cols: int) -> list[np.ndarray]:
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    tile_h = h // rows
    tile_w = w // cols
    tiles = []
    for r in range(rows):
        for c in range(cols):
            y0 = r * tile_h
            x0 = c * tile_w
            tiles.append(img_[y0:y0 + tile_h, x0:x0 + tile_w])
    return tiles


def collage_grid(images: list[np.ndarray], rows: int, cols: int, padding: int = 0,
                 bg_color=(0, 0, 0)) -> np.ndarray:
    return grid_stack(images, cols, padding, bg_color, equal_size=True)


COLLAGE_PRESETS = [
    ("2x1 横向", "2x1"),
    ("1x2 纵向", "1x2"),
    ("2x2 方形", "2x2"),
    ("3x3", "3x3"),
    ("4x4", "4x4"),
    ("3x2", "3x2"),
    ("2x3", "2x3"),
    ("4x2", "4x2"),
    ("1x4 纵向条", "1x4"),
    ("4x1 横向条", "4x1"),
]


def collage_custom(images: list[np.ndarray], cols: int = 2, rows: int | None = None,
                   padding: int = 0, bg_color=(0, 0, 0)) -> np.ndarray:
    if rows is None:
        rows = math.ceil(len(images) / cols)
    return grid_stack(images, cols, padding, bg_color, equal_size=True)
