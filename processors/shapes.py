from __future__ import annotations

import math

import cv2
import numpy as np

from .utils import ensure_rgb, ensure_rgba, u8, clamp


SHAPE_PRESETS = [
    ("圆形", "circle"),
    ("心形", "heart"),
    ("星形", "star"),
    ("圆角矩形", "rounded_rect"),
    ("椭圆", "ellipse"),
    ("三角形", "triangle"),
    ("六边形", "hexagon"),
    ("八边形", "octagon"),
    ("水滴", "droplet"),
    ("箭头", "arrow"),
    ("钻石", "diamond"),
    ("花瓣", "petal"),
    ("云形", "cloud"),
]


def shape_mask(width: int, height: int, shape: str, feather: int = 0) -> np.ndarray:
    h, w = height, width
    y, x = np.indices((h, w), dtype=np.float32)
    cx, cy = w / 2.0, h / 2.0
    mask = np.zeros((h, w), dtype=np.float32)

    if shape == "circle":
        r = min(w, h) / 2
        dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        mask = np.where(dist <= r, 1.0, 0.0)

    elif shape == "heart":
        xv = (x - cx) / (min(w, h) * 0.25)
        yv = -(y - cy) / (min(w, h) * 0.25)
        val = (xv ** 2 + yv ** 2 - 1) ** 3 - xv ** 2 * yv ** 3
        mask = np.where(val <= 0, 1.0, 0.0)

    elif shape == "star":
        r_outer = min(w, h) * 0.48
        r_inner = r_outer * 0.4
        angles = np.arctan2(y - cy, x - cx) + math.pi / 2
        angles = np.where(angles < 0, angles + 2 * math.pi, angles)
        sides = 5
        angle_per = 2 * math.pi / sides
        segment = (angles % angle_per) / angle_per
        radius = r_outer - (r_outer - r_inner) * np.abs(segment - 0.5) * 2
        dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        mask = np.where(dist <= radius, 1.0, 0.0)

    elif shape == "rounded_rect":
        r = min(w, h) * 0.15
        mask = np.where(
            ((x >= r) & (x <= w - r) & ((y >= 0) & (y <= h))) |
            ((y >= r) & (y <= h - r) & ((x >= 0) & (x <= w))) |
            (((x - r) ** 2 + (y - r) ** 2) <= r ** 2 & (x < r) & (y < r)) |
            (((w - x - r) ** 2 + (y - r) ** 2) <= r ** 2 & (x > w - r) & (y < r)) |
            (((x - r) ** 2 + (h - y - r) ** 2) <= r ** 2 & (x < r) & (y > h - r)) |
            (((w - x - r) ** 2 + (h - y - r) ** 2) <= r ** 2 & (x > w - r) & (y > h - r)),
            1.0, 0.0
        ).astype(np.float32)

    elif shape == "ellipse":
        rx = w * 0.48
        ry = h * 0.48
        val = ((x - cx) ** 2 / rx ** 2 + (y - cy) ** 2 / ry ** 2)
        mask = np.where(val <= 1, 1.0, 0.0)

    elif shape == "triangle":
        pts = np.array([
            [cx, h * 0.05],
            [w * 0.95, h * 0.95],
            [w * 0.05, h * 0.95],
        ], dtype=np.int32)
        img = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(img, [pts], 1)
        mask = img.astype(np.float32)

    elif shape == "hexagon":
        pts = []
        for i in range(6):
            ang = math.pi / 3 * i - math.pi / 6
            pts.append([cx + math.cos(ang) * min(w, h) * 0.48,
                        cy + math.sin(ang) * min(w, h) * 0.48])
        pts = np.array(pts, dtype=np.int32)
        img = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(img, [pts], 1)
        mask = img.astype(np.float32)

    elif shape == "octagon":
        pts = []
        for i in range(8):
            ang = math.pi / 4 * i - math.pi / 8
            pts.append([cx + math.cos(ang) * min(w, h) * 0.48,
                        cy + math.sin(ang) * min(w, h) * 0.48])
        pts = np.array(pts, dtype=np.int32)
        img = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(img, [pts], 1)
        mask = img.astype(np.float32)

    elif shape == "diamond":
        pts = np.array([
            [cx, h * 0.05],
            [w * 0.95, cy],
            [cx, h * 0.95],
            [w * 0.05, cy],
        ], dtype=np.int32)
        img = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(img, [pts], 1)
        mask = img.astype(np.float32)

    elif shape == "droplet":
        xv = (x - cx) / (min(w, h) * 0.4)
        yv = -(y - cy) / (min(w, h) * 0.4)
        val = xv ** 2 + yv ** 2 * (1 - yv)
        mask = np.where(val <= 1, 1.0, 0.0)

    elif shape == "cloud":
        base = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(base, (int(w * 0.3), int(h * 0.6)), int(min(w, h) * 0.2), 255, -1)
        cv2.circle(base, (int(w * 0.5), int(h * 0.5)), int(min(w, h) * 0.22), 255, -1)
        cv2.circle(base, (int(w * 0.7), int(h * 0.6)), int(min(w, h) * 0.2), 255, -1)
        cv2.circle(base, (int(w * 0.4), int(h * 0.45)), int(min(w, h) * 0.15), 255, -1)
        cv2.circle(base, (int(w * 0.6), int(h * 0.45)), int(min(w, h) * 0.15), 255, -1)
        mask = (base / 255.0).astype(np.float32)

    else:
        mask = np.ones((h, w), dtype=np.float32)

    if feather > 0:
        mask = cv2.GaussianBlur(mask, (feather * 2 + 1, feather * 2 + 1), sigmaX=feather / 3.0)

    return mask


def apply_shape_mask(img: np.ndarray, shape: str = "circle", feather: int = 0,
                     fill_color=(255, 255, 255)) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    mask = shape_mask(w, h, shape, feather)

    filled = np.full_like(img_, fill_color, dtype=np.float32)
    result = img_ * mask[..., None] + filled * (1 - mask[..., None])
    return u8(clamp(result))


def apply_shape_alpha(img: np.ndarray, shape: str = "circle", feather: int = 0) -> np.ndarray:
    img_ = ensure_rgba(img).astype(np.float32)
    h, w = img_.shape[:2]
    mask = shape_mask(w, h, shape, feather) * 255
    img_[..., 3] = mask
    return u8(clamp(img_))
