from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


SUPPORTED_READ = {
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif",
    ".heic", ".heif", ".avif", ".jxl", ".ico", ".ppm", ".pgm",
}

SUPPORTED_WRITE = {
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif",
    ".heic", ".heif", ".avif", ".jxl", ".ico",
}


def pil_to_np(img: Image.Image) -> np.ndarray:
    arr = np.array(img.convert("RGBA"))
    return arr


def np_to_pil(arr: np.ndarray) -> Image.Image:
    if arr.ndim == 2:
        return Image.fromarray(arr, mode="L")
    if arr.shape[2] == 4:
        return Image.fromarray(arr, mode="RGBA")
    if arr.shape[2] == 3:
        return Image.fromarray(arr, mode="RGB")
    raise ValueError(f"Unsupported shape: {arr.shape}")


def cv2_to_np(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    if img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    if img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
    return img


def np_to_cv2(arr: np.ndarray) -> np.ndarray:
    if arr.ndim == 2:
        return arr
    if arr.shape[2] == 3:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    if arr.shape[2] == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA)
    return arr


def ensure_rgb(arr: np.ndarray) -> np.ndarray:
    if arr.ndim == 2:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
    if arr.shape[2] == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2RGB)
    return arr


def ensure_rgba(arr: np.ndarray) -> np.ndarray:
    if arr.ndim == 2:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2RGBA)
    if arr.shape[2] == 3:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2RGBA)
    return arr


def load_image(path: str | Path) -> np.ndarray:
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".jxl":
        from pillow_jxl_plugin import JxlImagePlugin  # noqa: F401
    if ext in (".heic", ".heif"):
        from pillow_heif import register_heif_opener
        register_heif_opener()
    if ext == ".avif":
        from pillow_avif_plugin import AvifImagePlugin  # noqa: F401

    img = Image.open(path)
    arr = pil_to_np(img)
    return arr


def save_image(arr: np.ndarray, path: str | Path, **kwargs) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()
    pil_img = np_to_pil(arr)

    save_kwargs = {}
    if ext in (".jpg", ".jpeg"):
        save_kwargs.update({"quality": kwargs.get("quality", 92), "optimize": True})
    elif ext == ".webp":
        save_kwargs.update({"quality": kwargs.get("quality", 92), "method": kwargs.get("method", 4)})
    elif ext in (".png",):
        save_kwargs.update({"optimize": True, "compress_level": kwargs.get("compress_level", 6)})
    elif ext == ".tiff" or ext == ".tif":
        save_kwargs.update({"compression": "tiff_lzw"})
    elif ext == ".jxl":
        save_kwargs.update({"quality": kwargs.get("quality", 92)})
    elif ext in (".heic", ".heif"):
        save_kwargs.update({"quality": kwargs.get("quality", 92)})
    elif ext == ".avif":
        save_kwargs.update({"quality": kwargs.get("quality", 92)})

    if ext == ".jxl":
        from pillow_jxl_plugin import JxlImagePlugin  # noqa: F401
    if ext in (".heic", ".heif"):
        from pillow_heif import register_heif_opener
        register_heif_opener()
    if ext == ".avif":
        from pillow_avif_plugin import AvifImagePlugin  # noqa: F401

    pil_img.save(str(path), **save_kwargs)
    return path


def image_to_bytes(arr: np.ndarray, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    np_to_pil(arr).save(buf, format=fmt)
    return buf.getvalue()


def clamp(arr: np.ndarray, lo: int = 0, hi: int = 255) -> np.ndarray:
    return np.clip(arr, lo, hi)


def u8(arr: np.ndarray) -> np.ndarray:
    return np.asarray(arr, dtype=np.uint8)
