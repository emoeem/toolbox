from __future__ import annotations

import math

import cv2
import numpy as np
from skimage import color as sk_color

from .utils import clamp, ensure_rgb, ensure_rgba, u8


def _gray_weighted(img: np.ndarray) -> np.ndarray:
    img = ensure_rgb(img).astype(np.float32)
    return (img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114)


def _from_gray(g: np.ndarray) -> np.ndarray:
    return u8(clamp(np.stack([g, g, g], axis=-1)))


def grayscale_standard(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    gray = _gray_weighted(img)
    g = _from_gray(gray)
    if strength >= 1.0:
        return g
    img_rgb = ensure_rgb(img).astype(np.float32)
    result = img_rgb * (1.0 - strength) + g.astype(np.float32) * strength
    return u8(clamp(result))


def monochrome(img: np.ndarray) -> np.ndarray:
    return grayscale_standard(img, 1.0)


def black_and_white(img: np.ndarray, threshold: int = 128) -> np.ndarray:
    gray = _gray_weighted(img)
    bw = np.where(gray > threshold, 255, 0).astype(np.uint8)
    return _from_gray(bw)


def sepia(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    r, g, b = img_[..., 0], img_[..., 1], img_[..., 2]
    sr = r * 0.393 + g * 0.769 + b * 0.189
    sg = r * 0.349 + g * 0.686 + b * 0.168
    sb = r * 0.272 + g * 0.534 + b * 0.131
    sepia_img = np.stack([sr, sg, sb], axis=-1)
    sepia_img = np.clip(sepia_img, 0, 255)
    if strength >= 1.0:
        return u8(sepia_img)
    result = img_ * (1.0 - strength) + sepia_img * strength
    return u8(clamp(result))


def vintage(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    r, g, b = img_[..., 0], img_[..., 1], img_[..., 2]
    r = r * 0.9 + 25
    g = g * 0.85 + 15
    b = b * 0.7 + 30
    result = np.stack([r, g, b], axis=-1)
    result = np.clip(result, 0, 255)
    h, w = img_.shape[:2]
    y, x = np.indices((h, w))
    cx, cy = w / 2, h / 2
    dist = np.sqrt(((x - cx) / cx) ** 2 + ((y - cy) / cy) ** 2)
    vig = np.clip(1.0 - dist * 0.4, 0.4, 1.0)
    result *= vig[..., None]
    noise = np.random.default_rng(42).normal(0, 6, result.shape).astype(np.float32)
    result += noise
    return u8(clamp(result))


def warm(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    r, b = img_[..., 0] + 25 * strength, img_[..., 2] - 20 * strength
    g = img_[..., 1] + 5 * strength
    return u8(clamp(np.stack([r, g, b], axis=-1)))


def cool(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    r, b = img_[..., 0] - 20 * strength, img_[..., 2] + 25 * strength
    g = img_[..., 1] + 5 * strength
    return u8(clamp(np.stack([r, g, b], axis=-1)))


def browni(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    r, g, b = img_[..., 0], img_[..., 1], img_[..., 2]
    r = r ** 1.1 * 1.1
    g = g ** 1.05 * 0.95
    b = b ** 1.3 * 0.7
    return u8(clamp(np.stack([r, g, b], axis=-1) * 255))


def polaroid(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    result = img_.copy()
    result[..., 0] = np.clip(result[..., 0] ** 0.95 * 1.1, 0, 1)
    result[..., 1] = np.clip(result[..., 1] ** 0.97 * 1.0, 0, 1)
    result[..., 2] = np.clip(result[..., 2] ** 1.1 * 0.9, 0, 1)
    result += np.random.default_rng(7).normal(0, 0.02, result.shape).astype(np.float32)
    return u8(clamp(result * 255))


def night_vision(img: np.ndarray) -> np.ndarray:
    gray = _gray_weighted(img)
    g = gray / 255.0
    r = np.clip(g * 0.5, 0, 1)
    b = np.clip(g * 0.3, 0, 1)
    result = np.stack([r * 255, g * 255, b * 255], axis=-1)
    noise = np.random.default_rng(42).normal(0, 3, result.shape).astype(np.float32)
    result += noise
    return u8(clamp(result))


def retro_yellow(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    r = img_[..., 0] * 1.15 + 20
    g = img_[..., 1] * 1.1 + 15
    b = img_[..., 2] * 0.75
    return u8(clamp(np.stack([r, g, b], axis=-1)))


def coda_chrome(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    r = img_[..., 0] ** 1.05 * 1.05
    g = img_[..., 1] ** 1.0 * 1.0
    b = img_[..., 2] ** 0.95 * 0.95
    return u8(clamp(np.stack([r, g, b], axis=-1)))


def cw_black(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    r, g, b = img_[..., 0], img_[..., 1], img_[..., 2]
    r = np.clip(pow(r, 2.0), 0, 1) * 255
    g = np.clip(pow(g, 1.5), 0, 1) * 255
    b = np.clip(pow(b, 1.0), 0, 1) * 255
    return u8(clamp(np.stack([r, g, b], axis=-1)))


def gaussian_blur(img: np.ndarray, ksize: int = 11, sigma: float = 2.0) -> np.ndarray:
    img_ = ensure_rgb(img)
    k = ksize if ksize % 2 == 1 else ksize + 1
    return cv2.GaussianBlur(img_, (k, k), sigmaX=sigma, sigmaY=sigma)


def box_blur(img: np.ndarray, ksize: int = 9) -> np.ndarray:
    img_ = ensure_rgb(img)
    k = ksize if ksize % 2 == 1 else ksize + 1
    return cv2.blur(img_, (k, k))


def median_blur(img: np.ndarray, ksize: int = 5) -> np.ndarray:
    img_ = ensure_rgb(img)
    k = ksize if ksize % 2 == 1 else ksize + 1
    return cv2.medianBlur(img_, k)


def bilateral_blur(img: np.ndarray, d: int = 9, sigma_color: float = 75,
                   sigma_space: float = 75) -> np.ndarray:
    img_ = ensure_rgb(img)
    return cv2.bilateralFilter(img_, d, sigma_color, sigma_space)


def motion_blur(img: np.ndarray, ksize: int = 15, angle: float = 0.0) -> np.ndarray:
    img_ = ensure_rgb(img)
    k = ksize if ksize % 2 == 1 else ksize + 1
    kernel = np.zeros((k, k))
    mid = k // 2
    cos_a = math.cos(math.radians(angle))
    sin_a = math.sin(math.radians(angle))
    for i in range(k):
        x = i - mid
        px = int(mid + x * cos_a)
        py = int(mid + x * sin_a)
        if 0 <= px < k and 0 <= py < k:
            kernel[py, px] = 1.0
    kernel /= kernel.sum() if kernel.sum() > 0 else 1
    return cv2.filter2D(img_, -1, kernel)


def zoom_blur(img: np.ndarray, strength: float = 0.5) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    result = np.zeros_like(img_)
    for i in range(1, 8):
        s = 1 - strength * i / 16.0
        if s <= 0:
            break
        M = cv2.getRotationMatrix2D((cx, cy), 0, s)
        shifted = cv2.warpAffine(img_, M, (w, h))
        result += shifted / 8
    return u8(clamp(result))


def pixelate(img: np.ndarray, block_size: int = 8) -> np.ndarray:
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    bs = max(1, block_size)
    small = cv2.resize(img_, (max(1, w // bs), max(1, h // bs)), interpolation=cv2.INTER_LINEAR)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


def enhanced_pixelation(img: np.ndarray, block_size: int = 12) -> np.ndarray:
    return pixelate(img, block_size)


def circular_pixelation(img: np.ndarray, block_size: int = 10) -> np.ndarray:
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    y, x = np.indices((h, w))
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    max_dist = math.sqrt(cx ** 2 + cy ** 2)
    norm_dist = dist / max_dist
    block = np.maximum(2, (block_size * (1 - norm_dist * 0.7)).astype(int))

    result = img_.copy()
    for by in range(0, h, block_size):
        for bx in range(0, w, block_size):
            region = result[by:by + block_size, bx:bx + block_size]
            if region.size == 0:
                continue
            avg = region.mean(axis=(0, 1)).astype(np.uint8)
            result[by:by + block_size, bx:bx + block_size] = avg
    return result


def edge_detection(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    gray = cv2.cvtColor(img_.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    edges = cv2.Sobel(gray, cv2.CV_32F, 1, 1, ksize=3)
    edges = np.abs(edges)
    edges = edges / edges.max() * 255 if edges.max() > 0 else edges
    edges = np.clip(edges * strength, 0, 255).astype(np.uint8)
    return cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)


def sketch(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    img_ = ensure_rgb(img)
    gray = cv2.cvtColor(img_, cv2.COLOR_RGB2GRAY)
    inv = cv2.bitwise_not(gray)
    blurred = cv2.GaussianBlur(inv, (21, 21), sigmaX=0, sigmaY=0)
    sketched = cv2.divide(gray, 255 - blurred, scale=256)
    sketched = np.clip(sketched * strength, 0, 255).astype(np.uint8)
    return cv2.cvtColor(sketched, cv2.COLOR_GRAY2RGB)


def sobel_edge(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img)
    gray = cv2.cvtColor(img_, cv2.COLOR_RGB2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx ** 2 + gy ** 2)
    mag = mag / mag.max() * 255 if mag.max() > 0 else mag
    mag = np.clip(mag, 0, 255).astype(np.uint8)
    return cv2.cvtColor(mag, cv2.COLOR_GRAY2RGB)


def laplacian(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img)
    gray = cv2.cvtColor(img_, cv2.COLOR_RGB2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_32F)
    lap = np.abs(lap)
    lap = lap / lap.max() * 255 if lap.max() > 0 else lap
    lap = np.clip(lap, 0, 255).astype(np.uint8)
    return cv2.cvtColor(lap, cv2.COLOR_GRAY2RGB)


def emboss(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    gray = (img_[..., 0] * 0.299 + img_[..., 1] * 0.587 + img_[..., 2] * 0.114)
    kernel = np.array([[-2, -1, 0], [-1, 1, 1], [0, 1, 2]], dtype=np.float32)
    embossed = cv2.filter2D(gray, -1, kernel * strength)
    embossed = np.clip(embossed + 128, 0, 255).astype(np.uint8)
    return _from_gray(embossed)


def emboss_simple(img: np.ndarray) -> np.ndarray:
    return emboss(img, 1.0)


def dehaze(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    dark = np.min(img_, axis=-1)
    dark = cv2.GaussianBlur(dark, (5, 5), sigmaX=0)
    h, w = dark.shape
    flat = dark.flatten()
    idx = np.argsort(flat)[-max(1, h * w // 1000):]
    a = img_.reshape(-1, 3)[idx].mean(axis=0)
    t = 1 - strength * np.min(img_ / np.maximum(a, 0.001), axis=-1)
    t = np.clip(t, 0.1, 1)
    t = cv2.GaussianBlur(t, (15, 15), sigmaX=0)
    t = t[..., None]
    result = (img_ - a[None, None, :]) / np.maximum(t, 0.1) + a[None, None, :]
    return u8(clamp(result * 255))


def haze(img: np.ndarray, strength: float = 0.3) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    haze_color = 200
    y, x = np.indices((h, w))
    cx, cy = w / 2.0, h / 2.0
    dist = np.sqrt(((x - cx) / cx) ** 2 + ((y - cy) / cy) ** 2)
    factor = np.clip(0.2 + dist * strength, 0, 1)
    result = img_ * (1 - factor[..., None]) + haze_color * factor[..., None]
    return u8(clamp(result))


def invert_colors(img: np.ndarray) -> np.ndarray:
    return cv2.bitwise_not(ensure_rgb(img))


def solarize(img: np.ndarray, threshold: int = 128) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    result = np.where(img_ > threshold, 255 - img_, img_)
    return u8(clamp(result))


def exposure_linear(img: np.ndarray, stops: float = 0.0) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    result = img_ * (2 ** stops)
    return u8(clamp(result * 255))


def false_color(img: np.ndarray, colormap: str = "jet") -> np.ndarray:
    gray = _gray_weighted(img).astype(np.uint8)
    maps = {
        "jet": cv2.COLORMAP_JET, "hsv": cv2.COLORMAP_HSV, "hot": cv2.COLORMAP_HOT,
        "cool": cv2.COLORMAP_COOL, "rainbow": cv2.COLORMAP_RAINBOW,
        "bone": cv2.COLORMAP_BONE, "winter": cv2.COLORMAP_WINTER,
        "spring": cv2.COLORMAP_SPRING, "summer": cv2.COLORMAP_SUMMER,
        "ocean": cv2.COLORMAP_OCEAN,
    }
    cmap = maps.get(colormap, cv2.COLORMAP_JET)
    colored = cv2.applyColorMap(gray, cmap)
    return cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)


def glitch(img: np.ndarray, amount: float = 0.1) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    rng = np.random.default_rng(42)
    result = img_.copy()
    num_slices = max(1, int(h * amount * 3))
    for _ in range(num_slices):
        y1 = rng.integers(0, h - 1)
        height = rng.integers(2, max(3, int(h * amount * 10)))
        y2 = min(h, y1 + height)
        shift = rng.integers(-max(1, int(w * amount)), max(1, int(w * amount)))
        slice_ = result[y1:y2].copy()
        result[y1:y2] = np.roll(slice_, shift, axis=1)
    channel = rng.integers(0, 3)
    result[..., channel] = np.roll(result[..., channel], int(w * amount), axis=1)
    return u8(clamp(result))


def anaglyph(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    shift = int(img_.shape[1] * 0.02)
    result = np.zeros_like(img_)
    result[:, shift:, 0] = img_[:, :-shift, 0]
    result[:, :-shift, 0] = 0
    result[:, shift:, 1] = img_[:, :-shift, 1]
    result[:, shift:, 2] = img_[:, :-shift, 2]
    return u8(clamp(result))


def noise(img: np.ndarray, std: float = 20.0) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    rng = np.random.default_rng(42)
    n = rng.normal(0, std, img_.shape).astype(np.float32)
    return u8(clamp(img_ + n))


def film_grain(img: np.ndarray, amount: float = 0.3) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    h, w = img_.shape[:2]
    rng = np.random.default_rng(42)
    grain = rng.normal(0, amount * 0.15, (h, w, 1)).astype(np.float32)
    grain = np.repeat(grain, 3, axis=-1)
    result = img_ + grain
    return u8(clamp(result * 255))


def pixellate_bw(img: np.ndarray, block_size: int = 8) -> np.ndarray:
    p = pixelate(img, block_size)
    return black_and_white(p)


def posterize(img: np.ndarray, levels: int = 4) -> np.ndarray:
    if levels < 2:
        levels = 2
    img_ = ensure_rgb(img).astype(np.float32)
    step = 255.0 / (levels - 1)
    result = np.round(img_ / step) * step
    return u8(clamp(result))


def wave(img: np.ndarray, amplitude: float = 8.0, wavelength: float = 50.0) -> np.ndarray:
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    y, x = np.indices((h, w))
    x_map = x + amplitude * np.sin(2 * np.pi * y / wavelength)
    y_map = y + amplitude * np.cos(2 * np.pi * x / wavelength)
    return cv2.remap(img_, x_map.astype(np.float32), y_map.astype(np.float32),
                     cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def swirl(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    y, x = np.indices((h, w), dtype=np.float32)
    dx, dy = x - cx, y - cy
    dist = np.sqrt(dx ** 2 + dy ** 2)
    max_dist = np.sqrt(cx ** 2 + cy ** 2)
    angle = strength * (1 - dist / max_dist) * 6
    cos_a = np.cos(angle)
    sin_a = np.sin(angle)
    src_x = cx + dx * cos_a - dy * sin_a
    src_y = cy + dx * sin_a + dy * cos_a
    return cv2.remap(img_, src_x, src_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def bulge(img: np.ndarray, strength: float = 0.5) -> np.ndarray:
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    y, x = np.indices((h, w), dtype=np.float32)
    dx, dy = x - cx, y - cy
    dist = np.sqrt(dx ** 2 + dy ** 2)
    max_dist = np.sqrt(cx ** 2 + cy ** 2)
    r = dist / max_dist
    factor = r ** (1.0 + strength * 2)
    src_x = cx + dx * factor
    src_y = cy + dy * factor
    return cv2.remap(img_, src_x, src_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def pinch(img: np.ndarray, strength: float = 0.5) -> np.ndarray:
    return bulge(img, -strength)


def glass_sphere(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    y, x = np.indices((h, w), dtype=np.float32)
    dx, dy = x - cx, y - cy
    dist = np.sqrt(dx ** 2 + dy ** 2)
    max_dist = np.sqrt(cx ** 2 + cy ** 2)
    r = dist / max_dist
    factor = np.sin(r * np.pi / 2) ** 0.5
    src_x = cx + dx * factor
    src_y = cy + dy * factor
    return cv2.remap(img_, src_x, src_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def twirl(img: np.ndarray, strength: float = 10.0) -> np.ndarray:
    return swirl(img, strength)


def deuteranomaly(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    m = np.array([[0.625, 0.375, 0], [0.7, 0.3, 0], [0, 0, 1]])
    result = np.dot(img_.reshape(-1, 3), m.T).reshape(img_.shape)
    return u8(clamp(result * 255))


def deuteranopia(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    m = np.array([[0.56667, 0.43333, 0], [0.55833, 0.44167, 0], [0, 0, 1]])
    result = np.dot(img_.reshape(-1, 3), m.T).reshape(img_.shape)
    return u8(clamp(result * 255))


def protanopia(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    m = np.array([[0.56667, 0.43333, 0], [0.55833, 0.44167, 0], [0, 0, 1]])
    result = np.dot(img_.reshape(-1, 3), m.T).reshape(img_.shape)
    return u8(clamp(result * 255))


def tritanopia(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    m = np.array([[1, 0, 0], [0, 0.95, 0.05], [0, 0.475, 0.525]])
    result = np.dot(img_.reshape(-1, 3), m.T).reshape(img_.shape)
    return u8(clamp(result * 255))


def dither_bayer(img: np.ndarray, levels: int = 4, order: int = 4) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    bayer = {
        2: np.array([[0, 128], [192, 64]]) / 255.0,
        4: np.array([
            [0, 128, 32, 160],
            [192, 64, 224, 96],
            [48, 176, 16, 144],
            [240, 112, 208, 80],
        ]) / 255.0,
    }
    matrix = bayer.get(order, bayer[4])
    oh, ow = matrix.shape
    h, w = img_.shape[:2]
    tiled = np.tile(matrix, (h // oh + 1, w // ow + 1))[:h, w]
    result = np.zeros_like(img_)
    for c in range(3):
        channel = img_[..., c]
        quantized = np.round(channel * (levels - 1) + (tiled - 0.5) / levels) / (levels - 1)
        result[..., c] = np.clip(quantized, 0, 1)
    return u8(clamp(result * 255))


def floyd_steinberg(img: np.ndarray, levels: int = 4) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    h, w = img_.shape[:2]
    result = img_.copy()
    for y in range(h):
        for x in range(w):
            old = result[y, x].copy()
            new = np.round(old * (levels - 1)) / (levels - 1)
            result[y, x] = new
            err = old - new
            for dx, dy, factor in [(1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    result[ny, nx] += err * factor
    return u8(clamp(result * 255))


def sharpen_simple(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    img_ = ensure_rgb(img)
    blurred = cv2.GaussianBlur(img_, (3, 3), sigmaX=0)
    sharpened = cv2.addWeighted(img_, 1.0 + strength, blurred, -strength, 0)
    return u8(clamp(sharpened))


def unsharp_mask(img: np.ndarray, strength: float = 1.0, sigma: float = 1.5) -> np.ndarray:
    img_ = ensure_rgb(img)
    blurred = cv2.GaussianBlur(img_, (0, 0), sigmaX=sigma)
    sharpened = cv2.addWeighted(img_, 1.0 + strength, blurred, -strength, 0)
    return u8(clamp(sharpened))


def halftone(img: np.ndarray, dot_size: int = 6) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    gray = (img_[..., 0] * 0.299 + img_[..., 1] * 0.587 + img_[..., 2] * 0.114)
    h, w = gray.shape
    d = max(1, dot_size)
    result = np.ones((h, w, 3), dtype=np.float32) * 255
    for by in range(0, h, d):
        for bx in range(0, w, d):
            region = gray[by:by + d, bx:bx + d]
            if region.size == 0:
                continue
            avg = region.mean()
            r = (1 - avg) * d / 2
            yy, xx = np.indices(region.shape)
            dist = np.sqrt((xx - d / 2) ** 2 + (yy - d / 2) ** 2)
            circle = (dist < r).astype(np.float32)
            result[by:by + d, bx:bx + d] = circle[..., None] * 0
    return u8(clamp(result))


def oil_paint(img: np.ndarray, radius: int = 4) -> np.ndarray:
    img_ = ensure_rgb(img)
    r = max(1, radius)
    return cv2.bilateralFilter(img_, r * 2 + 1, r * 10, r * 10)


def water_color(img: np.ndarray, strength: float = 0.5) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    small = cv2.resize(img_, (max(1, w // 4), max(1, h // 4)), interpolation=cv2.INTER_AREA)
    small = cv2.bilateralFilter(small, 9, 75, 75)
    result = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
    result = cv2.addWeighted(img_, 1 - strength, result.astype(np.float32), strength, 0)
    return u8(clamp(result))


def hdr(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    lab = sk_color.rgb2lab(img_)
    l = lab[..., 0]
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l_u8 = np.clip(l, 0, 100).astype(np.uint8)
    l_enhanced = clahe.apply(l_u8).astype(np.float32)
    lab[..., 0] = l_enhanced
    result = sk_color.lab2rgb(lab)
    return u8(clamp(result * 255))


def glow(img: np.ndarray, strength: float = 0.5) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    blurred = cv2.GaussianBlur(img_, (21, 21), sigmaX=10)
    result = cv2.addWeighted(img_, 1.0, blurred, strength, 0)
    return u8(clamp(result))


def vignette_blur(img: np.ndarray, strength: float = 0.5) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    y, x = np.indices((h, w), dtype=np.float32)
    dist = np.sqrt(((x - cx) / cx) ** 2 + ((y - cy) / cy) ** 2)
    mask = np.clip(dist * strength * 2, 0, 1)
    blurred = cv2.GaussianBlur(img_, (21, 21), sigmaX=10)
    result = img_ * (1 - mask[..., None]) + blurred * mask[..., None]
    return u8(clamp(result))


def toon(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img)
    hsv = cv2.cvtColor(img_, cv2.COLOR_RGB2HSV)
    hsv[..., 1] = np.clip(hsv[..., 1].astype(np.float32) * 1.5, 0, 255).astype(np.uint8)
    hsv[..., 2] = np.round(hsv[..., 2].astype(np.float32) / 51) * 51
    result = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    gray = cv2.cvtColor(img_, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8))
    result[edges > 0] = 0
    return result


def smooth_toon(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img)
    blurred = cv2.bilateralFilter(img_, 9, 75, 75)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_RGB2HSV)
    hsv[..., 2] = np.round(hsv[..., 2].astype(np.float32) / 32) * 32
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


def neon(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    gray = cv2.cvtColor(img_.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150).astype(np.float32) / 255
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8)).astype(np.float32)
    edges = cv2.GaussianBlur(edges, (5, 5), sigmaX=2)
    result = img_ + edges[..., None] * strength * 100
    return u8(clamp(result))


def old_tv(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    scanlines = np.ones((h, 1), dtype=np.float32)
    scanlines[::2] = 0.7
    result = img_ * scanlines
    result += np.random.default_rng(7).normal(0, 8, result.shape).astype(np.float32)
    r_shift = np.roll(result[..., 0], 1, axis=1)
    b_shift = np.roll(result[..., 2], -1, axis=1)
    result[..., 0] = r_shift
    result[..., 2] = b_shift
    return u8(clamp(result))


def crt_curvature(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    cy, cx = h / 2.0, w / 2.0
    y, x = np.indices((h, w), dtype=np.float32)
    nx = (x - cx) / cx
    ny = (y - cy) / cy
    dx = nx ** 2 * 0.15
    dy = ny ** 2 * 0.15
    src_x = cx + (nx + dx) * cx
    src_y = cy + (ny + dy) * cy
    result = cv2.remap(img_, src_x, src_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_BLACK)
    scanlines = np.ones((h, 1), dtype=np.float32)
    scanlines[::2] = 0.85
    result = (result.astype(np.float32) * scanlines[..., None]).astype(np.uint8)
    return result


def bloom(img: np.ndarray, threshold: float = 0.7, strength: float = 0.5) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    lum = img_.mean(axis=-1)
    bright = np.where(lum > threshold, lum, 0)
    bright = np.stack([bright, bright, bright], axis=-1)
    blurred = cv2.GaussianBlur(bright.astype(np.float32), (0, 0), sigmaX=15)
    result = img_ + blurred * strength
    return u8(clamp(result * 255))


def crystallize(img: np.ndarray, cell_size: int = 12) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    cs = max(2, cell_size)
    for by in range(0, h, cs):
        for bx in range(0, w, cs):
            region = img_[by:by + cs, bx:bx + cs]
            if region.size == 0:
                continue
            avg = region.mean(axis=(0, 1)).astype(np.uint8)
            img_[by:by + cs, bx:bx + cs] = avg
    return u8(clamp(img_))


def water_color_new(img: np.ndarray) -> np.ndarray:
    return water_color(img, 0.6)


def dust_scratches(img: np.ndarray, amount: float = 0.1) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    rng = np.random.default_rng(42)
    result = img_.copy()
    num_dust = int(h * w * amount * 0.01)
    for _ in range(num_dust):
        x = rng.integers(0, w)
        y = rng.integers(0, h)
        size = rng.integers(1, 4)
        color = 255 if rng.random() > 0.5 else 0
        yy, yy2 = np.clip(y - size, 0, h), np.clip(y + size, 0, h)
        xx, xx2 = np.clip(x - size, 0, w), np.clip(x + size, 0, w)
        result[yy:yy2, xx:xx2] = color
    num_scratches = int(h * amount * 2)
    for _ in range(num_scratches):
        x1 = rng.integers(0, w)
        y1 = rng.integers(0, h)
        angle = rng.uniform(-0.3, 0.3)
        length = rng.integers(20, 200)
        x2 = int(x1 + length * math.cos(angle))
        y2 = int(y1 + length * math.sin(angle))
        color = 200 if rng.random() > 0.5 else 30
        cv2.line(result, (x1, y1), (x2, y2), (color, color, color), 1)
    return u8(clamp(result))


def denoise(img: np.ndarray, strength: float = 10.0) -> np.ndarray:
    img_ = ensure_rgb(img)
    return cv2.fastNlMeansDenoisingColored(img_, None, strength, strength, 7, 21)


def equalize_histogram(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img)
    ycrcb = cv2.cvtColor(img_, cv2.COLOR_RGB2YCrCb)
    ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
    return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2RGB)


def clahe_apply(img: np.ndarray, clip_limit: float = 2.0, tile_size: int = 8) -> np.ndarray:
    img_ = ensure_rgb(img)
    ycrcb = cv2.cvtColor(img_, cv2.COLOR_RGB2YCrCb)
    clahe_obj = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
    ycrcb[:, :, 0] = clahe_obj.apply(ycrcb[:, :, 0])
    return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2RGB)


def mosaic(img: np.ndarray, block_size: int = 12) -> np.ndarray:
    return pixelate(img, block_size)


def cartoon(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img)
    blurred = cv2.bilateralFilter(img_, 9, 75, 75)
    edges = cv2.adaptiveThreshold(cv2.cvtColor(img_, cv2.COLOR_RGB2GRAY), 255,
                                  cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 9)
    edges_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
    return cv2.bitwise_and(blurred, edges_colored)


def fish_eye(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    return swirl(img, strength * 3)


def color_halftone(img: np.ndarray, dot_size: int = 8) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    h, w = img_.shape[:2]
    d = max(2, dot_size)
    result = np.ones((h, w, 3), dtype=np.float32)
    angles = [0, 30, 60]
    for c in range(3):
        channel = img_[..., c]
        angle_rad = math.radians(angles[c])
        for by in range(0, h, d):
            for bx in range(0, w, d):
                region = channel[by:by + d, bx:bx + d]
                if region.size == 0:
                    continue
                avg = region.mean()
                r = avg * d / 2
                yy, xx = np.indices(region.shape)
                dist = np.abs((xx - d / 2) * math.cos(angle_rad) - (yy - d / 2) * math.sin(angle_rad))
                circle = (dist < r).astype(np.float32)
                result[by:by + d, bx:bx + d, c] = circle
    return u8(clamp(result * 255))


def white_balance_filter(img: np.ndarray, temperature: float = 0.0, tint: float = 0.0) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    r_gain = 1.0 + temperature * 0.1 + tint * 0.05
    g_gain = 1.0 + tint * 0.05
    b_gain = 1.0 - temperature * 0.1 - tint * 0.05
    gains = np.array([r_gain, g_gain, b_gain], dtype=np.float32)
    result = img_ * gains[None, None, :]
    return u8(clamp(result * 255))


def sharpen_unsharp(img: np.ndarray, strength: float = 1.5) -> np.ndarray:
    return unsharp_mask(img, strength, 1.5)


ALL_FILTERS = {
    "grayscale_standard": ("灰度", grayscale_standard),
    "monochrome": ("单色", monochrome),
    "black_and_white": ("黑白", black_and_white),
    "sepia": ("棕褐色", sepia),
    "vintage": ("复古", vintage),
    "warm": ("暖色", warm),
    "cool": ("冷色", cool),
    "browni": ("棕色调", browni),
    "polaroid": ("宝丽来", polaroid),
    "night_vision": ("夜视", night_vision),
    "retro_yellow": ("复古黄", retro_yellow),
    "coda_chrome": ("柯达彩", coda_chrome),
    "cw_black": ("电影黑", cw_black),
    "gaussian_blur": ("高斯模糊", gaussian_blur),
    "box_blur": ("方框模糊", box_blur),
    "median_blur": ("中值模糊", median_blur),
    "bilateral_blur": ("双边模糊", bilateral_blur),
    "motion_blur": ("运动模糊", motion_blur),
    "zoom_blur": ("缩放模糊", zoom_blur),
    "pixelate": ("像素化", pixelate),
    "enhanced_pixelation": ("强像素化", enhanced_pixelation),
    "circular_pixelation": ("圆形像素", circular_pixelation),
    "edge_detection": ("边缘检测", edge_detection),
    "sketch": ("素描", sketch),
    "sobel_edge": ("Sobel 边缘", sobel_edge),
    "laplacian": ("拉普拉斯", laplacian),
    "emboss": ("浮雕", emboss),
    "emboss_simple": ("简易浮雕", emboss_simple),
    "dehaze": ("去雾", dehaze),
    "haze": ("雾化", haze),
    "invert_colors": ("反色", invert_colors),
    "solarize": ("曝光", solarize),
    "exposure_linear": ("曝光校正", exposure_linear),
    "white_balance_filter": ("白平衡", white_balance_filter),
    "false_color": ("伪彩色", false_color),
    "glitch": ("故障效果", glitch),
    "anaglyph": ("立体红青", anaglyph),
    "noise": ("噪声", noise),
    "film_grain": ("胶片颗粒", film_grain),
    "pixellate_bw": ("黑白像素", pixellate_bw),
    "posterize": ("色调分离", posterize),
    "wave": ("波浪", wave),
    "swirl": ("漩涡", swirl),
    "bulge": ("鼓胀", bulge),
    "pinch": ("收缩", pinch),
    "glass_sphere": ("玻璃球", glass_sphere),
    "twirl": ("扭转", twirl),
    "fish_eye": ("鱼眼", fish_eye),
    "deuteranomaly": ("红绿色弱", deuteranomaly),
    "deuteranopia": ("红绿色盲", deuteranopia),
    "protanopia": ("红色盲", protanopia),
    "tritanopia": ("蓝色盲", tritanopia),
    "dither_bayer": ("Bayer 抖动", dither_bayer),
    "floyd_steinberg": ("Floyd-Steinberg 抖动", floyd_steinberg),
    "sharpen_simple": ("锐化", sharpen_simple),
    "unsharp_mask": ("USM 锐化", unsharp_mask),
    "halftone": ("半色调", halftone),
    "oil_paint": ("油画", oil_paint),
    "water_color": ("水彩", water_color),
    "hdr": ("HDR", hdr),
    "glow": ("光晕", glow),
    "vignette_blur": ("虚化边缘", vignette_blur),
    "toon": ("卡通", toon),
    "smooth_toon": ("平滑卡通", smooth_toon),
    "neon": ("霓虹", neon),
    "old_tv": ("旧电视", old_tv),
    "crt_curvature": ("CRT 曲率", crt_curvature),
    "bloom": ("泛光", bloom),
    "crystallize": ("结晶", crystallize),
    "dust_scratches": ("粉尘划痕", dust_scratches),
    "denoise": ("降噪", denoise),
    "equalize_histogram": ("直方图均衡", equalize_histogram),
    "clahe_apply": ("CLAHE", clahe_apply),
    "mosaic": ("马赛克", mosaic),
    "cartoon": ("卡通化", cartoon),
    "color_halftone": ("彩色半调", color_halftone),
    "sharpen_unsharp": ("USM 锐化2", sharpen_unsharp),
}


def get_filter_names() -> list[str]:
    return [(k, v[0]) for k, v in ALL_FILTERS.items()]


def apply_filter(key: str, img: np.ndarray, **kwargs) -> np.ndarray:
    if key not in ALL_FILTERS:
        raise KeyError(f"未知滤镜: {key}")
    _, func = ALL_FILTERS[key]
    return func(img, **kwargs)
