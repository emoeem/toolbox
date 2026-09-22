from __future__ import annotations

import cv2
import numpy as np

from .utils import clamp, ensure_rgb, ensure_rgba, u8


def brightness(img: np.ndarray, value: float = 0.0) -> np.ndarray:
    img = ensure_rgb(img).astype(np.float32)
    result = img + value * 255
    return u8(clamp(result))


def contrast(img: np.ndarray, value: float = 0.0) -> np.ndarray:
    img = ensure_rgb(img).astype(np.float32)
    f = (259 * (value * 255 + 255)) / (255 * (259 - value * 255))
    result = f * (img - 128) + 128
    return u8(clamp(result))


def saturation(img: np.ndarray, value: float = 0.0) -> np.ndarray:
    img = ensure_rgb(img).astype(np.float32) / 255.0
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    hsv[..., 1] *= (1.0 + value)
    hsv[..., 1] = np.clip(hsv[..., 1], 0, 1)
    result = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    return u8(clamp(result * 255))


def gamma(img: np.ndarray, value: float = 1.0) -> np.ndarray:
    if value <= 0:
        value = 0.01
    inv = 1.0 / value
    lut = np.array([((i / 255.0) ** inv) * 255.0 for i in range(256)], dtype=np.uint8)
    img = ensure_rgb(img)
    return cv2.LUT(img, lut)


def exposure(img: np.ndarray, stops: float = 0.0) -> np.ndarray:
    img = ensure_rgb(img).astype(np.float32)
    factor = 2.0 ** stops
    result = img * factor
    return u8(clamp(result))


def hue_shift(img: np.ndarray, degrees: float = 0.0) -> np.ndarray:
    img = ensure_rgb(img).astype(np.float32) / 255.0
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    hsv[..., 0] = (hsv[..., 0] + degrees) % 180
    result = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    return u8(clamp(result * 255))


def vibrance(img: np.ndarray, amount: float = 0.0) -> np.ndarray:
    img = ensure_rgb(img).astype(np.float32) / 255.0
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    sat = hsv[..., 1]
    mask = sat < 1.0
    factor = 1.0 + amount * (1.0 - sat)
    hsv[..., 1][mask] *= factor[mask]
    hsv[..., 1] = np.clip(hsv[..., 1], 0, 1)
    result = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    return u8(clamp(result * 255))


def highlights_shadows(img: np.ndarray, highlights: float = 0.0, shadows: float = 0.0) -> np.ndarray:
    img = ensure_rgb(img).astype(np.float32)
    lum = cv2.cvtColor(img / 255.0, cv2.COLOR_RGB2GRAY)

    h_mask = np.clip((lum - 0.5) * 2.0, 0, 1)
    s_mask = np.clip((0.5 - lum) * 2.0, 0, 1)

    result = img + h_mask[..., None] * highlights * 255 + s_mask[..., None] * shadows * 255
    return u8(clamp(result))


def white_balance(img: np.ndarray, temperature: float = 0.0, tint: float = 0.0) -> np.ndarray:
    img = ensure_rgb(img).astype(np.float32)

    r_gain = 1.0 + temperature * 0.05
    b_gain = 1.0 - temperature * 0.05
    g_gain = 1.0 + tint * 0.02
    r_gain -= tint * 0.02

    result = img.copy()
    result[..., 0] *= r_gain
    result[..., 1] *= g_gain
    result[..., 2] *= b_gain
    return u8(clamp(result))


def sharpen(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    img = ensure_rgb(img)
    blurred = cv2.GaussianBlur(img, (0, 0), sigmaX=3, sigmaY=3)
    sharpened = cv2.addWeighted(img, 1.0 + strength, blurred, -strength, 0)
    return u8(clamp(sharpened))


def rotate(img: np.ndarray, angle: float) -> np.ndarray:
    img_ = ensure_rgba(img) if img.shape[2] == 4 else ensure_rgb(img)
    h, w = img_.shape[:2]
    center = (w / 2, h / 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos = abs(M[0, 0])
    sin = abs(M[0, 1])
    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]

    if img_.shape[2] == 4:
        result = cv2.warpAffine(img_, M, (new_w, new_h), borderMode=cv2.BORDER_CONSTANT)
    else:
        result = cv2.warpAffine(img_, M, (new_w, new_h), borderMode=cv2.BORDER_REFLECT)
    return result


def flip_h(img: np.ndarray) -> np.ndarray:
    return cv2.flip(img, 1)


def flip_v(img: np.ndarray) -> np.ndarray:
    return cv2.flip(img, 0)


def resize(img: np.ndarray, width: int | None = None, height: int | None = None,
           keep_aspect: bool = True, interpolation: str = "lanczos") -> np.ndarray:
    h, w = img.shape[:2]

    if width is None and height is None:
        return img

    if keep_aspect:
        if width and height is None:
            ratio = width / w
            height = int(h * ratio)
        elif height and width is None:
            ratio = height / h
            width = int(w * ratio)

    interp_map = {
        "nearest": cv2.INTER_NEAREST,
        "bilinear": cv2.INTER_LINEAR,
        "cubic": cv2.INTER_CUBIC,
        "lanczos": cv2.INTER_LANCZOS4,
        "area": cv2.INTER_AREA,
    }
    interp = interp_map.get(interpolation, cv2.INTER_LANCZOS4)
    return cv2.resize(img, (width, height), interpolation=interp)


def scale(img: np.ndarray, scale_factor: float, interpolation: str = "lanczos") -> np.ndarray:
    h, w = img.shape[:2]
    nw = max(1, int(w * scale_factor))
    nh = max(1, int(h * scale_factor))
    return resize(img, nw, nh, keep_aspect=False, interpolation=interpolation)


def crop(img: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    x, y, w, h = int(x), int(y), int(w), int(h)
    x = max(0, min(x, img.shape[1] - 1))
    y = max(0, min(y, img.shape[0] - 1))
    w = max(1, min(w, img.shape[1] - x))
    h = max(1, min(h, img.shape[0] - y))
    return img[y:y + h, x:x + w].copy()


def center_crop(img: np.ndarray, width: int, height: int) -> np.ndarray:
    h, w = img.shape[:2]
    cx, cy = w // 2, h // 2
    x1 = max(0, cx - width // 2)
    y1 = max(0, cy - height // 2)
    return crop(img, x1, y1, width, height)


def aspect_crop(img: np.ndarray, ratio: float) -> np.ndarray:
    h, w = img.shape[:2]
    if w / h > ratio:
        new_w = int(h * ratio)
        return center_crop(img, new_w, h)
    else:
        new_h = int(w / ratio)
        return center_crop(img, w, new_h)


def border(img: np.ndarray, top: int, bottom: int, left: int, right: int,
           color=(0, 0, 0), blur_fill: bool = False) -> np.ndarray:
    img_ = ensure_rgb(img)
    if blur_fill:
        fill = cv2.GaussianBlur(img_, (51, 51), sigmaX=10, sigmaY=10)
        filled = cv2.copyMakeBorder(fill, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
        inner = filled[top:top + img_.shape[0], left:left + img_.shape[1]]
        img_new = cv2.copyMakeBorder(img_, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(0, 0, 0))
        mask = np.zeros_like(img_new)
        mask[top:top + img_.shape[0], left:left + img_.shape[1]] = 1
        result = filled * (1 - mask) + img_new * mask
        return u8(clamp(result))
    else:
        return cv2.copyMakeBorder(img_, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)


def invert(img: np.ndarray) -> np.ndarray:
    return cv2.bitwise_not(img)


def grayscale(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(ensure_rgb(img), cv2.COLOR_RGB2GRAY)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)


def black_white(img: np.ndarray, threshold: int = 128) -> np.ndarray:
    gray = cv2.cvtColor(ensure_rgb(img), cv2.COLOR_RGB2GRAY)
    _, bw = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    return cv2.cvtColor(bw, cv2.COLOR_GRAY2RGB)


def blend(a: np.ndarray, b: np.ndarray, alpha: float = 0.5) -> np.ndarray:
    a_ = ensure_rgba(a).astype(np.float32)
    b_ = ensure_rgba(b).astype(np.float32)
    ah, aw = a_.shape[:2]
    bh, bw = b_.shape[:2]
    if (ah, aw) != (bh, bw):
        b_ = cv2.resize(b_, (aw, ah), interpolation=cv2.INTER_LANCZOS4)
    result = a_ * alpha + b_ * (1 - alpha)
    return u8(clamp(result))


def histogram_equalize(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img)
    ycrcb = cv2.cvtColor(img_, cv2.COLOR_RGB2YCrCb)
    ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
    return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2RGB)


def clahe(img: np.ndarray, clip_limit: float = 2.0, tile_size: int = 8) -> np.ndarray:
    img_ = ensure_rgb(img)
    ycrcb = cv2.cvtColor(img_, cv2.COLOR_RGB2YCrCb)
    clahe_obj = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
    ycrcb[:, :, 0] = clahe_obj.apply(ycrcb[:, :, 0])
    return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2RGB)


def vignette(img: np.ndarray, strength: float = 0.5) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    h, w = img_.shape[:2]
    y, x = np.indices((h, w))
    cx, cy = w / 2.0, h / 2.0
    dist = np.sqrt(((x - cx) ** 2 + (y - cy) ** 2) / (cx ** 2 + cy ** 2))
    mask = 1.0 - dist * strength
    mask = np.clip(mask, 0, 1)
    result = img_ * mask[..., None]
    return u8(clamp(result))


def split_channels(img: np.ndarray) -> list[np.ndarray]:
    img_ = ensure_rgb(img)
    return [img_[..., 0].copy(), img_[..., 1].copy(), img_[..., 2].copy()]


def merge_channels(channels: list[np.ndarray]) -> np.ndarray:
    return np.stack(channels, axis=-1)
