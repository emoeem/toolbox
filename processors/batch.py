from __future__ import annotations

from pathlib import Path

import numpy as np

from .utils import ensure_rgb, u8, clamp
from .core import resize


SOCIAL_PRESETS = {
    "Instagram 方图": (1080, 1080),
    "Instagram 竖图": (1080, 1350),
    "Instagram Story": (1080, 1920),
    "Instagram 轮播": (1080, 1080),
    "Facebook 封面": (820, 312),
    "Facebook 帖子": (1200, 630),
    "Facebook 头像": (170, 170),
    "Twitter X 横幅": (1500, 500),
    "Twitter X 帖子": (1200, 675),
    "Twitter X 头像": (400, 400),
    "YouTube 缩略图": (1280, 720),
    "YouTube 频道封面": (2560, 1440),
    "TikTok": (1080, 1920),
    "Pinterest": (1000, 1500),
    "LinkedIn 横幅": (1584, 396),
    "LinkedIn 帖子": (1200, 627),
    "微信朋友圈": (1080, 1080),
    "微信公众号": (900, 500),
    "小红书": (1080, 1440),
    "B站封面": (1146, 717),
    "壁纸 1920": (1920, 1080),
    "壁纸 2K": (2560, 1440),
    "壁纸 4K": (3840, 2160),
    "移动端壁纸": (1080, 1920),
    "A4 打印": (2480, 3508),
}


def smart_resize_by_size(img: np.ndarray, target_width: int, target_height: int,
                         fit: str = "contain", bg_color=(0, 0, 0)) -> np.ndarray:
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    tw, th = target_width, target_height

    if fit == "cover":
        scale = max(tw / w, th / h)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(img_, (nw, nh))
        result = np.full((th, tw, 3), bg_color, dtype=np.uint8)
        y0 = max(0, (nh - th) // 2)
        x0 = max(0, (nw - tw) // 2)
        result = resized[y0:y0 + th, x0:x0 + tw]
        return result

    elif fit == "contain":
        scale = min(tw / w, th / h)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(img_, (nw, nh))
        result = np.full((th, tw, 3), bg_color, dtype=np.uint8)
        y0 = (th - nh) // 2
        x0 = (tw - nw) // 2
        result[y0:y0 + nh, x0:x0 + nw] = resized
        return result

    elif fit == "fill":
        return cv2.resize(img_, (tw, th))

    else:
        scale = min(tw / w, th / h)
        nw, nh = int(w * scale), int(h * scale)
        return cv2.resize(img_, (nw, nh))


def resize_to_weight(img: np.ndarray, target_bytes: int,
                     format: str = "JPEG", quality: int = 85) -> tuple[bytes, int]:
    from PIL import Image
    import io
    from .utils import np_to_pil
    pil = np_to_pil(img)
    fmt = format.upper()
    lo, hi = 10, 100
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        buf = io.BytesIO()
        pil.save(buf, format=fmt if fmt != "JPG" else "JPEG", quality=mid)
        size = buf.tell()
        if size <= target_bytes:
            best = (buf.getvalue(), mid, size)
            lo = mid + 1
        else:
            hi = mid - 1
    if best is None:
        buf = io.BytesIO()
        pil.save(buf, format=fmt if fmt != "JPG" else "JPEG", quality=10)
        return buf.getvalue(), buf.tell()
    return best[0], best[2]


def batch_rename(files: list[Path], pattern: str = "{name}_{i}{ext}", start: int = 1,
                 padding: int = 3) -> list[tuple[Path, Path]]:
    results = []
    for idx, f in enumerate(sorted(files)):
        name = f.stem
        ext = f.suffix
        i = str(start + idx).zfill(padding)
        new_name = pattern.format(name=name, ext=ext, i=i, index=i)
        results.append((f, f.with_name(new_name)))
    return results


def find_duplicates(files: list[Path], hash_algo: str = "phash") -> dict[str, list[Path]]:
    from .checksum import md5
    groups: dict[str, list[Path]] = {}
    for f in files:
        try:
            data = f.read_bytes()
            key = md5(data)
            groups.setdefault(key, []).append(f)
        except Exception:
            continue
    return {k: v for k, v in groups.items() if len(v) > 1}


def find_similar_images(files: list[Path], threshold: float = 0.95) -> list[tuple[Path, Path, float]]:
    from .utils import load_image
    import cv2
    results = []
    loaded = []
    for f in files:
        try:
            img = load_image(str(f))
            gray = cv2.cvtColor(ensure_rgb(img), cv2.COLOR_RGB2GRAY)
            small = cv2.resize(gray, (32, 32)).astype(np.float32) / 255.0
            loaded.append((f, small))
        except Exception:
            continue
    for i in range(len(loaded)):
        for j in range(i + 1, len(loaded)):
            a = loaded[i][1]
            b = loaded[j][1]
            ncc = float(np.correlate((a - a.mean()).ravel(), (b - b.mean()).ravel())[0] /
                        (a.std() * b.std() * a.size + 1e-9))
            if ncc >= threshold:
                results.append((loaded[i][0], loaded[j][0], ncc))
    return results


try:
    import cv2
except Exception:
    cv2 = None
