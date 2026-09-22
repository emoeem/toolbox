from __future__ import annotations

import numpy as np

from .utils import ensure_rgb, u8, clamp


def lomo(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    hsv = cv2.cvtColor((img_ * 255).astype(np.uint8), cv2.COLOR_RGB2HSV)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1].astype(np.float32) * 1.3, 0, 255).astype(np.uint8)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2].astype(np.float32) ** 1.2 * 255, 0, 255).astype(np.uint8)
    result = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB).astype(np.float32)
    h, w = img_.shape[:2]
    y, x = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / np.sqrt(cx ** 2 + cy ** 2)
    vig = 1 - dist ** 2 * 0.6
    result *= vig[..., None]
    result[:, :, 0] = np.clip(result[:, :, 0] * 1.2 + 30, 0, 255)
    result[:, :, 2] = np.clip(result[:, :, 2] * 0.85, 0, 255)
    return u8(result)


def polaroid(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    img_[:, :, 0] = np.clip(img_[:, :, 0] * 1.1 + 20, 0, 255)
    img_[:, :, 1] = np.clip(img_[:, :, 1] * 1.05 + 10, 0, 255)
    img_[:, :, 2] = np.clip(img_[:, :, 2] * 0.85 + 30, 0, 255)
    return u8(clamp(img_))


def kodachrome(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    kernel = np.array([[0.272, 0.534, 0.131],
                       [0.349, 0.686, 0.168],
                       [0.393, 0.769, 0.189]], dtype=np.float32)
    result = cv2.transform(img_, kernel)
    result = np.clip(result * 1.1 + 10, 0, 255)
    return u8(result)


def technicolor(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    r, g, b = img_[..., 0], img_[..., 1], img_[..., 2]
    result = np.zeros_like(img_)
    result[..., 0] = np.clip(r + 0.15 * g + 0.15 * b, 0, 1)
    result[..., 1] = np.clip(0.85 * g + 0.15 * b, 0, 1)
    result[..., 2] = np.clip(b * 0.85 + 0.15 * r, 0, 1)
    return u8(result * 255)


def cross_process(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    img_[..., 0] = np.clip(1 - (1 - img_[..., 0]) ** 1.5, 0, 1)
    img_[..., 2] = np.clip(img_[..., 2] ** 0.7, 0, 1)
    img_[..., 1] = np.clip(img_[..., 1] ** 1.1, 0, 1)
    return u8(img_ * 255)


def bleach_bypass(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    g = (img_[..., 0] * 0.299 + img_[..., 1] * 0.587 + img_[..., 2] * 0.114)
    luma = g
    result = np.zeros_like(img_)
    result[..., 0] = img_[..., 0] * 0.5 + luma * 0.5
    result[..., 1] = img_[..., 1] * 0.5 + luma * 0.5
    result[..., 2] = img_[..., 2] * 0.5 + luma * 0.3 + 0.2
    return u8(np.clip(result * 255, 0, 255))


def orange_teal(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    hsv = cv2.cvtColor(img_.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    orange_mask = (h < 30) | (h > 160)
    teal_mask = (h >= 80) & (h <= 160)
    new_hsv = hsv.copy()
    new_hsv[orange_mask, 1] = np.clip(new_hsv[orange_mask, 1] * 1.4, 0, 255)
    new_hsv[teal_mask, 0] = np.clip(new_hsv[teal_mask, 0] * 0.9 - 10, 0, 179)
    new_hsv[teal_mask, 1] = np.clip(new_hsv[teal_mask, 1] * 1.6, 0, 255)
    result = cv2.cvtColor(new_hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    return u8(clamp(result.astype(np.float32) * 1.1))


def fuji_film(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    img_[..., 0] = np.clip(img_[..., 0] ** 1.1 + 0.05, 0, 1)
    img_[..., 1] = np.clip(img_[..., 1] ** 1.05 + 0.02, 0, 1)
    img_[..., 2] = np.clip(img_[..., 2] ** 0.95 - 0.02, 0, 1)
    return u8(img_ * 255)


def cinema_4d(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    result = img_ * np.array([1.15, 1.0, 0.85], dtype=np.float32) + np.array([10, 5, 15], dtype=np.float32)
    hsv = cv2.cvtColor(u8(clamp(result)), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 0.85, 0, 255)
    result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)
    h, w = result.shape[:2]
    y, x = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / np.sqrt(cx ** 2 + cy ** 2)
    vig = 1 - dist ** 2 * 0.3
    result *= vig[..., None]
    return u8(clamp(result))


def tri_tone(img: np.ndarray, shadow=(0, 0, 80), midtone=(100, 100, 100),
             highlight=(255, 220, 180)) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    gray = img_.mean(axis=-1, keepdims=True) / 255.0
    s = np.array(shadow, dtype=np.float32)
    m = np.array(midtone, dtype=np.float32)
    h = np.array(highlight, dtype=np.float32)
    t = gray
    low = np.where(t < 0.5, 1 - t * 2, 0)
    mid = np.where((t >= 0.25) & (t <= 0.75), np.minimum((t - 0.25) * 4, (0.75 - t) * 4), 0)
    high = np.where(t > 0.5, (t - 0.5) * 2, 0)
    result = s[None, None, :] * low + m[None, None, :] * mid + h[None, None, :] * high
    return u8(clamp(result))


def duo_tone(img: np.ndarray, color1=(50, 100, 200), color2=(255, 200, 50)) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    gray = img_.mean(axis=-1, keepdims=True) / 255.0
    c1 = np.array(color1, dtype=np.float32)
    c2 = np.array(color2, dtype=np.float32)
    result = c1[None, None, :] * (1 - gray) + c2[None, None, :] * gray
    return u8(clamp(result))


def hdr_tone_mapping(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    result = cv2.detailEnhance((img_ * 255).astype(np.uint8), sigma_s=20, sigma_r=0.15)
    hsv = cv2.cvtColor(result, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2] * 1.1, 0, 255)
    result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    return result


def glow(img: np.ndarray, sigma: float = 15.0, intensity: float = 0.8) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    blur = cv2.GaussianBlur(img_, (0, 0), sigma)
    result = img_ + blur * intensity
    return u8(clamp(result))


def bokeh(img: np.ndarray, mask_radius_ratio: float = 0.3) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    mask = np.clip(1 - dist / (min(h, w) * mask_radius_ratio), 0, 1)
    blurred = cv2.GaussianBlur(img_, (31, 31), 15)
    result = img_ * mask[..., None] + blurred * (1 - mask[..., None])
    return u8(clamp(result))


def chromatic_aberration(img: np.ndarray, amount: int = 10) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    r = img_[:, :, 0]
    g = img_[:, :, 1]
    b = img_[:, :, 2]
    M_r = np.float32([[1, 0, -amount], [0, 1, 0]])
    M_b = np.float32([[1, 0, amount], [0, 1, 0]])
    r = cv2.warpAffine(r, M_r, (w, h), borderMode=cv2.BORDER_REPLICATE)
    b = cv2.warpAffine(b, M_b, (w, h), borderMode=cv2.BORDER_REPLICATE)
    result = np.dstack([r, g, b])
    return result


def fisheye(img: np.ndarray, strength: float = 0.5) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    fx, fy = w / 2, h / 2
    K = np.float32([[fx, 0, w / 2], [0, fy, h / 2], [0, 0, 1]])
    D = np.float32([strength * 2, strength * 2, 0, 0])
    map1, map2 = cv2.initUndistortRectifyMap(K, D, None, K, (w, h), cv2.CV_32FC1)
    result = cv2.remap(img_, map1, map2, cv2.INTER_LINEAR)
    return result


def barrel_distortion(img: np.ndarray, amount: float = 0.3) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    cx, cy = w / 2, h / 2
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    x = (x - cx) / cx
    y = (y - cy) / cy
    r = np.sqrt(x ** 2 + y ** 2)
    r_new = r * (1 + amount * r ** 2)
    r_new = np.clip(r_new, 0, 2.0)
    mask = r > 0
    src_x = np.where(mask, x * r_new / (r + 1e-6), x)
    src_y = np.where(mask, y * r_new / (r + 1e-6), y)
    src_x = (src_x * cx + cx).astype(np.float32)
    src_y = (src_y * cy + cy).astype(np.float32)
    result = cv2.remap(img_, src_x, src_y, cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    return result


def pinhole(img: np.ndarray, strength: float = 0.3) -> np.ndarray:
    return barrel_distortion(img, -strength)


def mirror_reflection(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    half_top = img_[:h // 2]
    half_bottom = cv2.flip(half_top, 0)
    result = np.vstack([half_top, half_bottom])
    return result


def dual_split(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    half_left = img_[:, :w // 2]
    half_right = cv2.flip(half_left, 1)
    result = np.hstack([half_left, half_right])
    return result


def kaleidoscope(img: np.ndarray, segments: int = 6) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    size = min(h, w)
    cx, cy = w // 2, h // 2
    cropped = img_[cy - size // 2:cy + size // 2, cx - size // 2:cx + size // 2]
    seg_w = size // segments
    seg = cropped[:, :seg_w]
    flipped = cv2.flip(seg, 1)
    strip = np.hstack([seg, flipped])
    copies = []
    for i in range(segments // 2):
        copies.append(strip)
    full = np.hstack(copies)
    full = cv2.resize(full, (w, h))
    return full


def pixelate(img: np.ndarray, block_size: int = 10) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    sw, sh = max(1, w // block_size), max(1, h // block_size)
    small = cv2.resize(img_, (sw, sh), interpolation=cv2.INTER_LINEAR)
    big = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
    return big


def halftone(img: np.ndarray, dot_size: int = 4) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img)
    gray = cv2.cvtColor(img_, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    result = np.full((h, w, 3), 255, dtype=np.uint8)
    for y in range(0, h, dot_size):
        for x in range(0, w, dot_size):
            block = gray[y:y + dot_size, x:x + dot_size].mean()
            radius = int((1 - block / 255.0) * dot_size * 0.5)
            cx, cy = x + dot_size // 2, y + dot_size // 2
            cv2.circle(result, (cx, cy), radius, (0, 0, 0), -1)
    return result


def dither_bayer(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    bayer = np.array([[0, 8, 2, 10],
                       [12, 4, 14, 6],
                       [3, 11, 1, 9],
                       [15, 7, 13, 5]], dtype=np.float32) / 16.0 - 0.5
    h, w = img_.shape[:2]
    tile = np.tile(bayer, (h // 4 + 1, w // 4 + 1))[:h, :w]
    for c in range(3):
        img_[..., c] = np.clip(img_[..., c] + tile * 0.3, 0, 1)
    quantized = (img_ > 0.5).astype(np.float32)
    return u8(quantized * 255)


def reduce_colors(img: np.ndarray, num_colors: int = 8) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    data = img_.reshape(-1, 3)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    compactness, labels, centers = cv2.kmeans(data, num_colors, None, criteria, 10, cv2.KMEANS_PP_CENTERS)
    centers = np.clip(centers, 0, 1)
    quantized = centers[labels.flatten()].reshape(img_.shape)
    return u8(quantized * 255)


def neon_glow(img: np.ndarray, blur_amount: int = 15, strength: float = 1.5) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    edges = cv2.Laplacian(cv2.cvtColor(img_.astype(np.uint8), cv2.COLOR_RGB2GRAY), cv2.CV_64F)
    edges = np.abs(edges)
    edges_norm = (edges / edges.max().clip(min=1)).astype(np.float32) * 255
    edge_mask = cv2.GaussianBlur(edges_norm, (blur_amount * 2 + 1, blur_amount * 2 + 1), blur_amount)
    edge_mask = edge_mask * strength
    result = img_ + edge_mask[..., None] * 2
    return u8(clamp(result))


def double_exposure(img: np.ndarray, factor: float = 0.5) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    result = (img_ + np.roll(img_, (int(img_.shape[0] * factor), int(img_.shape[1] * factor)), axis=(0, 1))) / 2
    return u8(result * 255)


def light_leaks(img: np.ndarray, intensity: float = 0.5) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    overlay = np.zeros((h, w, 3), dtype=np.float32)
    y, x = np.ogrid[:h, :w]
    for i, (cx, cy, color) in enumerate([(w * 0.3, h * 0.2, (1.0, 0.6, 0.3)),
                                           (w * 0.7, h * 0.8, (0.9, 0.4, 0.2)),
                                           (w * 0.5, h * 0.5, (0.8, 0.7, 0.3))]):
        dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        fade = np.exp(-dist ** 2 / (10000 * intensity ** 2))
        overlay += np.array(color, dtype=np.float32)[None, None, :] * fade[..., None]
    result = img_ + overlay * 100
    return u8(clamp(result))


def bn_waffle(img: np.ndarray) -> np.ndarray:
    return duo_tone(img, (30, 30, 50), (255, 240, 200))


def apple_tv(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    img_[..., 0] = np.clip(img_[..., 0] ** 1.15, 0, 255)
    img_[..., 2] = np.clip(img_[..., 2] * 0.9 + 20, 0, 255)
    hsv = cv2.cvtColor(img_.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 0.85, 0, 255)
    result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)
    return u8(clamp(result))


def vintage_teal(img: np.ndarray) -> np.ndarray:
    return orange_teal(img)


def washed_out(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    img_ = img_ ** 1.3
    img_ = img_ * 0.7 + 0.3 * (img_.mean())
    return u8(np.clip(img_ * 255, 0, 255))


def cyanotype(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    gray = cv2.cvtColor(img_.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    blue = gray * 0.6 + 50
    result = np.zeros_like(img_)
    result[..., 0] = gray * 0.3
    result[..., 1] = gray * 0.5
    result[..., 2] = blue
    return u8(clamp(result))


def sepia_ii(img: np.ndarray, intensity: float = 0.9) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    kernel = np.array([[0.393, 0.769, 0.189],
                       [0.349, 0.686, 0.168],
                       [0.272, 0.534, 0.131]], dtype=np.float32)
    sepia = cv2.transform(img_, kernel)
    result = img_ * (1 - intensity) + sepia * intensity
    return u8(clamp(result))


def warm_sunset(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    img_[..., 0] = np.clip(img_[..., 0] * 1.25 + 20, 0, 255)
    img_[..., 1] = np.clip(img_[..., 1] * 1.05 + 10, 0, 255)
    img_[..., 2] = np.clip(img_[..., 2] * 0.85 - 10, 0, 255)
    return u8(clamp(img_))


def cool_winter(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    img_[..., 0] = np.clip(img_[..., 0] * 0.9 + 10, 0, 255)
    img_[..., 1] = np.clip(img_[..., 1] * 0.95 + 5, 0, 255)
    img_[..., 2] = np.clip(img_[..., 2] * 1.15 + 20, 0, 255)
    return u8(clamp(img_))


def pastel(img: np.ndarray, strength: float = 0.7) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    blurred = cv2.GaussianBlur(img_, (21, 21), 10)
    result = img_ * (1 - strength) + blurred * strength
    result = np.clip(result * 1.1 + 0.05, 0, 1)
    return u8(result * 255)


def cream(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    img_[..., 0] = np.clip(img_[..., 0] * 1.15 + 15, 0, 255)
    img_[..., 1] = np.clip(img_[..., 1] * 1.08 + 10, 0, 255)
    img_[..., 2] = np.clip(img_[..., 2] * 0.95 - 5, 0, 255)
    return u8(clamp(img_))


def black_iron(img: np.ndarray) -> np.ndarray:
    return duo_tone(img, (10, 10, 15), (255, 180, 120))


def aqua(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    img_[..., 0] = np.clip(img_[..., 0] * 0.85 + 10, 0, 255)
    img_[..., 1] = np.clip(img_[..., 1] * 1.1 + 20, 0, 255)
    img_[..., 2] = np.clip(img_[..., 2] * 1.1 + 30, 0, 255)
    return u8(clamp(img_))


def green_moon(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    result = np.zeros_like(img_)
    result[..., 0] = img_[..., 0] * 0.8
    result[..., 1] = img_[..., 1] * 1.2 + 20
    result[..., 2] = img_[..., 2] * 0.7
    return u8(clamp(result))


def cyberpunk(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    img_[..., 0] = np.clip(img_[..., 0] ** 1.1 * 1.3, 0, 1)
    img_[..., 1] = np.clip(img_[..., 1] ** 0.8 * 0.8, 0, 1)
    img_[..., 2] = np.clip(img_[..., 2] ** 1.2 * 1.2, 0, 1)
    return u8(img_ * 255)


def sunset_orange(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    img_[..., 0] = np.clip(img_[..., 0] * 1.3 + 25, 0, 255)
    img_[..., 1] = np.clip(img_[..., 1] * 1.0 + 5, 0, 255)
    img_[..., 2] = np.clip(img_[..., 2] * 0.8 - 20, 0, 255)
    return u8(clamp(img_))


def movie_blue(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    img_[..., 0] = np.clip(img_[..., 0] * 0.85 - 10, 0, 255)
    img_[..., 1] = np.clip(img_[..., 1] * 1.0 + 5, 0, 255)
    img_[..., 2] = np.clip(img_[..., 2] * 1.2 + 20, 0, 255)
    return u8(clamp(img_))


def forest_green(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    img_[..., 0] = np.clip(img_[..., 0] * 0.9, 0, 255)
    img_[..., 1] = np.clip(img_[..., 1] * 1.2 + 20, 0, 255)
    img_[..., 2] = np.clip(img_[..., 2] * 0.85, 0, 255)
    return u8(clamp(img_))


def rose_pink(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    img_[..., 0] = np.clip(img_[..., 0] * 1.2 + 15, 0, 255)
    img_[..., 1] = np.clip(img_[..., 1] * 0.95 + 5, 0, 255)
    img_[..., 2] = np.clip(img_[..., 2] * 1.05 + 5, 0, 255)
    return u8(clamp(img_))


def mono_red(img: np.ndarray) -> np.ndarray:
    return duo_tone(img, (180, 0, 0), (255, 200, 200))


def mono_blue(img: np.ndarray) -> np.ndarray:
    return duo_tone(img, (0, 0, 180), (200, 200, 255))


def mono_green(img: np.ndarray) -> np.ndarray:
    return duo_tone(img, (0, 100, 0), (200, 255, 200))


def mono_yellow(img: np.ndarray) -> np.ndarray:
    return duo_tone(img, (180, 150, 0), (255, 255, 200))


def mono_purple(img: np.ndarray) -> np.ndarray:
    return duo_tone(img, (100, 0, 150), (230, 200, 255))


def mono_cyan(img: np.ndarray) -> np.ndarray:
    return duo_tone(img, (0, 100, 130), (180, 255, 255))


def grainy(img: np.ndarray, intensity: float = 25.0) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    noise = np.random.RandomState(42).normal(0, intensity, img_.shape).astype(np.float32)
    return u8(clamp(img_ + noise))


def noise_add(img: np.ndarray, intensity: float = 0.1) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    noise = np.random.RandomState(0).normal(0, intensity, img_.shape).astype(np.float32)
    return u8(clamp((img_ + noise) * 255))


def salt_pepper(img: np.ndarray, density: float = 0.05) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    mask = np.random.RandomState(42).rand(h, w)
    salt = mask < density / 2
    pepper = mask > 1 - density / 2
    img_[salt] = 255
    img_[pepper] = 0
    return u8(clamp(img_))


def scanline(img: np.ndarray, opacity: float = 0.3) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    scan = np.zeros((h, 1), dtype=np.float32)
    scan[1::2] = 1.0
    scan = np.tile(scan, (1, w))
    result = img_ * (1 - opacity * scan[..., None])
    return u8(clamp(result))


def crt(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    scanlines = np.ones((h, w, 3), dtype=np.float32)
    scanlines[1::2] = 0.6
    y = np.linspace(0, 1, h)
    x = np.linspace(0, 1, w)
    yy, xx = np.meshgrid(x, y)
    vignette = 1 - ((xx - 0.5) ** 2 + (yy - 0.5) ** 2) * 1.2
    result = img_ * scanlines * vignette[..., None]
    return u8(clamp(result))


def tv_static(img: np.ndarray, amount: float = 0.15) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    noise = np.random.RandomState(123).rand(*img_.shape).astype(np.float32) * 255
    result = img_ * (1 - amount) + noise * amount
    return u8(clamp(result))


def hologram(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    result = np.zeros_like(img_)
    result[..., 0] = img_[..., 1]
    result[..., 1] = img_[..., 2]
    result[..., 2] = img_[..., 0]
    result = result * np.array([0.3, 1.0, 0.3], dtype=np.float32)
    h, w = img_.shape[:2]
    y = np.linspace(0, 1, h)
    yy, _ = np.meshgrid(np.zeros(w), y)
    result = result * (0.5 + 0.5 * np.sin(yy * 30))[..., None]
    return u8(clamp(result * 255))


def thermal(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.uint8)
    gray = cv2.cvtColor(img_, cv2.COLOR_RGB2GRAY)
    colormap = cv2.COLORMAP_JET
    result = cv2.applyColorMap(gray, colormap)
    result = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
    return result


def night_vision(img: np.ndarray, intensity: float = 1.5) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.uint8)
    gray = cv2.cvtColor(img_, cv2.COLOR_RGB2GRAY).astype(np.float32)
    edges = cv2.Laplacian(gray, cv2.CV_64F)
    edges = np.abs(edges) * intensity
    result = np.zeros((gray.shape[0], gray.shape[1], 3), dtype=np.float32)
    result[..., 1] = np.clip(gray * 0.8 + edges, 0, 255)
    return u8(clamp(result))


def infrared(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    gray = img_.mean(axis=-1)
    result = np.zeros_like(img_)
    result[..., 0] = gray
    result[..., 1] = gray * 0.3
    result[..., 2] = gray * 0.5
    return u8(clamp(result))


def ascii_filter(img: np.ndarray, size: int = 2) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    h, w = img_.shape[:2]
    size = max(1, size)
    sw, sh = max(1, w // (size * 6)), max(1, h // (size * 8))
    gray = cv2.cvtColor((img_ * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    small = cv2.resize(gray, (sw, sh), interpolation=cv2.INTER_LINEAR)
    chars = " .:-=+*#%@"
    out = np.zeros_like(gray)
    for y in range(sh):
        for x in range(sw):
            ch = chars[int(np.clip(small[y, x] * (len(chars) - 1), 0, len(chars) - 1))]
            val = chars.index(ch) / len(chars)
            out[y * 8:(y + 1) * 8, x * 6:(x + 1) * 6] = val
    rgb = np.stack([out, out, out], axis=-1)
    return u8(clamp(rgb * 255))


def silhouette(img: np.ndarray, threshold: int = 128, bg_color=(0, 0, 0),
               fg_color=(255, 255, 255)) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.uint8)
    gray = cv2.cvtColor(img_, cv2.COLOR_RGB2GRAY)
    _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    result = np.zeros_like(img_)
    result[mask > 0] = fg_color
    result[mask == 0] = bg_color
    return result


def posterize(img: np.ndarray, levels: int = 4) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    result = np.clip(np.round(img_ * levels) / levels * 255 - 255 / levels + 255, 0, 255)
    return u8(result)


def threshold(img: np.ndarray, value: int = 128, bg=(0, 0, 0), fg=(255, 255, 255)) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.uint8)
    gray = cv2.cvtColor(img_, cv2.COLOR_RGB2GRAY)
    _, mask = cv2.threshold(gray, value, 255, cv2.THRESH_BINARY)
    result = np.zeros_like(img_)
    result[mask > 0] = fg
    result[mask == 0] = bg
    return result


def emboss(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    kernel = np.array([[-2, -1, 0], [-1, 1, 1], [0, 1, 2]], dtype=np.float32) * strength
    result = cv2.filter2D(img_, -1, kernel)
    result = np.clip(result + 128, 0, 255)
    return u8(result)


def motion_blur(img: np.ndarray, length: int = 15, angle: float = 0) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img)
    kernel = np.zeros((length, length), dtype=np.float32)
    kernel[length // 2, :] = np.ones(length) / length
    M = cv2.getRotationMatrix2D((length / 2 - 0.5, length / 2 - 0.5), -angle, 1.0)
    kernel = cv2.warpAffine(kernel, M, (length, length))
    result = cv2.filter2D(img_, -1, kernel)
    return result


def directional_blur(img: np.ndarray, size: int = 10, angle: float = 0) -> np.ndarray:
    return motion_blur(img, size, angle)


def zoom_blur(img: np.ndarray, steps: int = 10, strength: float = 5.0) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    result = img_.copy()
    for i in range(1, steps + 1):
        k = i / steps * strength
        M = np.float32([[1 + k * 0.1 * (cx / w), 0, -cx * k * 0.1],
                         [0, 1 + k * 0.1 * (cy / h), -cy * k * 0.1]])
        shifted = cv2.warpAffine(img_, M, (w, h))
        result = result + shifted
    result = result / (steps + 1)
    return u8(clamp(result))


def radial_blur(img: np.ndarray, strength: int = 15) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    angle = np.deg2rad(strength / 5.0)
    result = img_.astype(np.float32)
    for i in range(1, 10):
        a = angle * i / 10
        M = cv2.getRotationMatrix2D((cx, cy), -a * 180 / np.pi, 1.0)
        rotated = cv2.warpAffine(img_.astype(np.float32), M, (w, h), flags=cv2.INTER_LINEAR)
        result += rotated
    result /= 10
    return u8(clamp(result))


def lens_flare(img: np.ndarray, cx_ratio: float = 0.3, cy_ratio: float = 0.3,
               intensity: float = 1.0) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    fx, fy = int(cx_ratio * w), int(cy_ratio * h)
    overlay = np.zeros((h, w, 3), dtype=np.float32)
    for i, (size, color) in enumerate([(min(w, h) * 0.3, (255, 220, 180)),
                                        (min(w, h) * 0.15, (255, 180, 120)),
                                        (min(w, h) * 0.08, (255, 255, 200)),
                                        (min(w, h) * 0.03, (255, 255, 255))]):
        y, x = np.ogrid[:h, :w]
        dist = np.sqrt((x - fx) ** 2 + (y - fy) ** 2)
        fade = np.exp(-dist ** 2 / (size ** 2))
        overlay += np.array(color, dtype=np.float32)[None, None, :] * fade[..., None]
    result = img_ + overlay * intensity
    return u8(clamp(result))


def add_watermark(img: np.ndarray, text: str = "©", position: str = "bottom_right",
                  size: int = 40, color=(255, 255, 255), opacity: float = 0.5,
                  tiled: bool = False) -> np.ndarray:
    import cv2
    import numpy as np
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    overlay = img_.copy()
    cv2.putText(overlay.astype(np.uint8), text, (0, 0), cv2.FONT_HERSHEY_SIMPLEX,
                size / 30, color, 2)
    if tiled:
        for y in range(0, h, int(size * 2)):
            for x in range(0, w, int(size * len(text) * 1.5)):
                cv2.putText(overlay.astype(np.uint8), text, (x, y + size),
                            cv2.FONT_HERSHEY_SIMPLEX, size / 30, color, 2)
    else:
        cv2.putText(overlay.astype(np.uint8), text, (0, 0), cv2.FONT_HERSHEY_SIMPLEX,
                    size / 30, color, 2)
    if position == "bottom_right":
        x0 = w - size * len(text)
        y0 = h - size
        cv2.putText(overlay.astype(np.uint8), text, (max(10, x0), y0),
                    cv2.FONT_HERSHEY_SIMPLEX, size / 30, color, 2)
    elif position == "top_right":
        cv2.putText(overlay.astype(np.uint8), text, (w - size * len(text), size),
                    cv2.FONT_HERSHEY_SIMPLEX, size / 30, color, 2)
    elif position == "bottom_left":
        cv2.putText(overlay.astype(np.uint8), text, (10, h - size),
                    cv2.FONT_HERSHEY_SIMPLEX, size / 30, color, 2)
    elif position == "top_left":
        cv2.putText(overlay.astype(np.uint8), text, (10, size),
                    cv2.FONT_HERSHEY_SIMPLEX, size / 30, color, 2)
    elif position == "center":
        cv2.putText(overlay.astype(np.uint8), text, (w // 2 - size * len(text) // 2, h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, size / 30, color, 2)
    result = img_ * (1 - opacity) + overlay * opacity
    return u8(clamp(result))


def _register_advanced_filters():
    from . import filters
    ADVANCED = {
        "lomo": ("Lomo", lomo),
        "polaroid": ("宝丽来", polaroid),
        "kodachrome": ("柯达胶卷", kodachrome),
        "technicolor": ("特艺色", technicolor),
        "cross_process": ("交叉冲洗", cross_process),
        "bleach_bypass": ("漂白", bleach_bypass),
        "orange_teal": ("橙青色调", orange_teal),
        "fuji_film": ("富士胶片", fuji_film),
        "cinema_4d": ("电影感", cinema_4d),
        "tri_tone": ("三色调", tri_tone),
        "duo_tone": ("双色调", duo_tone),
        "hdr_tone_mapping": ("HDR", hdr_tone_mapping),
        "glow": ("发光", glow),
        "bokeh": ("虚化", bokeh),
        "chromatic_aberration": ("色差", chromatic_aberration),
        "fisheye": ("鱼眼", fisheye),
        "barrel_distortion": ("桶形失真", barrel_distortion),
        "pinhole": ("针孔", pinhole),
        "mirror_reflection": ("上下镜像", mirror_reflection),
        "dual_split": ("左右镜像", dual_split),
        "kaleidoscope": ("万花筒", kaleidoscope),
        "pixelate": ("像素化", pixelate),
        "halftone": ("半调", halftone),
        "dither_bayer": ("Bayer 抖动", dither_bayer),
        "reduce_colors": ("减色", reduce_colors),
        "neon_glow": ("霓虹", neon_glow),
        "double_exposure": ("双重曝光", double_exposure),
        "light_leaks": ("漏光", light_leaks),
        "bn_waffle": ("蓝黄复古", bn_waffle),
        "apple_tv": ("Apple TV 风", apple_tv),
        "vintage_teal": ("复古青绿", vintage_teal),
        "washed_out": ("褪色", washed_out),
        "cyanotype": ("蓝晒", cyanotype),
        "sepia_ii": ("深棕", sepia_ii),
        "warm_sunset": ("暖色日落", warm_sunset),
        "cool_winter": ("冷冬", cool_winter),
        "pastel": ("柔和粉彩", pastel),
        "cream": ("奶油色", cream),
        "black_iron": ("黑铁", black_iron),
        "aqua": ("青水", aqua),
        "green_moon": ("绿月", green_moon),
        "cyberpunk": ("赛博朋克", cyberpunk),
        "sunset_orange": ("橙日落", sunset_orange),
        "movie_blue": ("电影蓝", movie_blue),
        "forest_green": ("森林绿", forest_green),
        "rose_pink": ("玫瑰粉", rose_pink),
        "mono_red": ("单红", mono_red),
        "mono_blue": ("单蓝", mono_blue),
        "mono_green": ("单绿", mono_green),
        "mono_yellow": ("单黄", mono_yellow),
        "mono_purple": ("单紫", mono_purple),
        "mono_cyan": ("单青", mono_cyan),
        "grainy": ("颗粒感", grainy),
        "noise_add": ("噪点", noise_add),
        "salt_pepper": ("椒盐", salt_pepper),
        "scanline": ("扫描线", scanline),
        "crt": ("CRT", crt),
        "tv_static": ("电视雪花", tv_static),
        "hologram": ("全息", hologram),
        "thermal": ("热成像", thermal),
        "night_vision": ("夜视", night_vision),
        "infrared": ("红外", infrared),
        "ascii_filter": ("ASCII 艺术", ascii_filter),
        "silhouette": ("剪影", silhouette),
        "posterize": ("海报化", posterize),
        "threshold": ("阈值", threshold),
        "emboss": ("浮雕", emboss),
        "motion_blur": ("运动模糊", motion_blur),
        "zoom_blur": ("变焦模糊", zoom_blur),
        "radial_blur": ("径向模糊", radial_blur),
        "lens_flare": ("镜头光晕", lens_flare),
    }
    old_count = len(filters.ALL_FILTERS)
    filters.ALL_FILTERS.update(ADVANCED)
    return len(filters.ALL_FILTERS)


def register_all() -> int:
    return _register_advanced_filters()
