from __future__ import annotations

import numpy as np

from .utils import ensure_rgb


def mean_absolute_error(a: np.ndarray, b: np.ndarray) -> float:
    a_ = ensure_rgb(a).astype(np.float32)
    b_ = ensure_rgb(b).astype(np.float32)
    return float(np.abs(a_ - b_).mean())


def root_mean_squared_error(a: np.ndarray, b: np.ndarray) -> float:
    a_ = ensure_rgb(a).astype(np.float32)
    b_ = ensure_rgb(b).astype(np.float32)
    return float(np.sqrt(((a_ - b_) ** 2).mean()))


def mse(a: np.ndarray, b: np.ndarray) -> float:
    a_ = ensure_rgb(a).astype(np.float32)
    b_ = ensure_rgb(b).astype(np.float32)
    return float(((a_ - b_) ** 2).mean())


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    m = mse(a, b)
    if m == 0:
        return float("inf")
    return 20 * np.log10(255.0 / np.sqrt(m))


def normalized_cross_correlation(a: np.ndarray, b: np.ndarray) -> float:
    a_ = ensure_rgb(a).astype(np.float64)
    b_ = ensure_rgb(b).astype(np.float64)
    a_ = a_.reshape(-1)
    b_ = b_.reshape(-1)
    return float(np.correlate(a_ - a_.mean(), b_ - b_.mean())[0] /
                 (a_.std() * b_.std() * len(a_)))


def structural_similarity(a: np.ndarray, b: np.ndarray,
                          k1: float = 0.01, k2: float = 0.03, L: float = 255.0) -> float:
    import cv2
    a_ = cv2.cvtColor(ensure_rgb(a), cv2.COLOR_RGB2GRAY).astype(np.float64)
    b_ = cv2.cvtColor(ensure_rgb(b), cv2.COLOR_RGB2GRAY).astype(np.float64)
    mu_a = cv2.GaussianBlur(a_, (11, 11), 1.5)
    mu_b = cv2.GaussianBlur(b_, (11, 11), 1.5)
    mu_a_sq = mu_a ** 2
    mu_b_sq = mu_b ** 2
    mu_a_mu_b = mu_a * mu_b
    var_a = cv2.GaussianBlur(a_ ** 2, (11, 11), 1.5) - mu_a_sq
    var_b = cv2.GaussianBlur(b_ ** 2, (11, 11), 1.5) - mu_b_sq
    cov = cv2.GaussianBlur(a_ * b_, (11, 11), 1.5) - mu_a_mu_b
    c1 = (k1 * L) ** 2
    c2 = (k2 * L) ** 2
    numerator = (2 * mu_a_mu_b + c1) * (2 * cov + c2)
    denominator = (mu_a_sq + mu_b_sq + c1) * (var_a + var_b + c2)
    return float((numerator / denominator).mean())


def compare(a: np.ndarray, b: np.ndarray) -> dict:
    from PIL import Image
    from .utils import ensure_rgb, np_to_pil
    a_ = ensure_rgb(a)
    b_ = ensure_rgb(b)
    ha, wa = a_.shape[:2]
    hb, wb = b_.shape[:2]
    if (ha, wa) != (hb, wb):
        from processors.utils import resize
        b_ = resize(b_, wa, ha, keep_aspect=False)
    return {
        "mae": mean_absolute_error(a_, b_),
        "rmse": root_mean_squared_error(a_, b_),
        "mse": mse(a_, b_),
        "psnr": psnr(a_, b_),
        "ncc": normalized_cross_correlation(a_, b_),
        "ssim": structural_similarity(a_, b_),
    }


def difference_image(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_ = ensure_rgb(a).astype(np.float32)
    b_ = ensure_rgb(b).astype(np.float32)
    from processors.utils import resize
    ha, wa = a_.shape[:2]
    hb, wb = b_.shape[:2]
    if (ha, wa) != (hb, wb):
        b_ = resize(b_, wa, ha, keep_aspect=False)
    diff = np.abs(a_ - b_).mean(axis=-1)
    diff = (diff / max(1, diff.max()) * 255).astype(np.uint8)
    return np.stack([diff, diff, diff], axis=-1)
