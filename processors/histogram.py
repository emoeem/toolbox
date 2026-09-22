from __future__ import annotations

import numpy as np

from .utils import ensure_rgb, u8


def histogram_rgb(img: np.ndarray) -> dict:
    img_ = ensure_rgb(img)
    result = {}
    channels = ["R", "G", "B"]
    for i, c in enumerate(channels):
        hist, _ = np.histogram(img_[..., i].ravel(), bins=256, range=(0, 256))
        result[c] = hist.astype(int).tolist()
    return result


def histogram_luma(img: np.ndarray) -> list:
    img_ = ensure_rgb(img).astype(np.float32)
    luma = img_[..., 0] * 0.299 + img_[..., 1] * 0.587 + img_[..., 2] * 0.114
    hist, _ = np.histogram(luma.ravel(), bins=256, range=(0, 256))
    return hist.astype(int).tolist()


def histogram_hsv(img: np.ndarray) -> dict:
    import cv2
    img_ = ensure_rgb(img)
    hsv = cv2.cvtColor(img_, cv2.COLOR_RGB2HSV)
    h_hist, _ = np.histogram(hsv[..., 0].ravel(), bins=180, range=(0, 180))
    s_hist, _ = np.histogram(hsv[..., 1].ravel(), bins=256, range=(0, 256))
    v_hist, _ = np.histogram(hsv[..., 2].ravel(), bins=256, range=(0, 256))
    return {"H": h_hist.astype(int).tolist(),
            "S": s_hist.astype(int).tolist(),
            "V": v_hist.astype(int).tolist()}


def equalize_histogram_manual(img: np.ndarray) -> np.ndarray:
    import cv2
    img_ = ensure_rgb(img)
    ycrcb = cv2.cvtColor(img_, cv2.COLOR_RGB2YCrCb)
    y = ycrcb[:, :, 0]
    hist, bins = np.histogram(y.ravel(), 256, [0, 256])
    cdf = hist.cumsum()
    cdf_masked = np.ma.masked_equal(cdf, 0)
    cdf_eq = (cdf_masked - cdf_masked.min()) * 255 / (cdf_masked.max() - cdf_masked.min())
    cdf_final = np.ma.filled(cdf_eq, 0).astype("uint8")
    y_eq = cdf_final[y]
    ycrcb[:, :, 0] = y_eq
    result = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2RGB)
    return u8(result)


def auto_contrast(img: np.ndarray, low: float = 1.0, high: float = 1.0) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    lo = np.percentile(img_, low)
    hi = np.percentile(img_, 100 - high)
    if hi == lo:
        return u8(clamp(img_))
    result = (img_ - lo) / (hi - lo) * 255
    return u8(clamp(result))


def auto_levels(img: np.ndarray) -> np.ndarray:
    return auto_contrast(img, 0.5, 0.5)


def curve(img: np.ndarray, points: list[tuple] | np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img)
    pts = np.array(points, dtype=np.float32)
    if pts.ndim == 2:
        xs = pts[:, 0]
        ys = pts[:, 1]
    else:
        xs = pts
        ys = pts
    lut = np.interp(np.arange(256), xs, ys, left=ys[0], right=ys[-1])
    lut = np.clip(lut, 0, 255).astype(np.uint8)
    return cv2.LUT(img_, lut)


def levels(img: np.ndarray, input_lo: int = 0, input_hi: int = 255,
           output_lo: int = 0, output_hi: int = 255,
           gamma: float = 1.0) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    img_ = (img_ - input_lo) / (input_hi - input_lo)
    img_ = np.clip(img_, 0, 1)
    img_ = np.power(img_, 1.0 / max(0.01, gamma))
    img_ = img_ * (output_hi - output_lo) + output_lo
    return u8(clamp(img_))


try:
    import cv2
except Exception:
    cv2 = None
