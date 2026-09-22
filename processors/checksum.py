from __future__ import annotations

import hashlib
import zlib
from pathlib import Path

import numpy as np

from .utils import ensure_rgb


def md5(data: bytes | np.ndarray | str) -> str:
    return hashlib.md5(_to_bytes(data)).hexdigest()


def sha1(data: bytes | np.ndarray | str) -> str:
    return hashlib.sha1(_to_bytes(data)).hexdigest()


def sha256(data: bytes | np.ndarray | str) -> str:
    return hashlib.sha256(_to_bytes(data)).hexdigest()


def sha512(data: bytes | np.ndarray | str) -> str:
    return hashlib.sha512(_to_bytes(data)).hexdigest()


def crc32(data: bytes | np.ndarray | str) -> str:
    return format(zlib.crc32(_to_bytes(data)) & 0xFFFFFFFF, "08x")


def blake2b(data: bytes | np.ndarray | str) -> str:
    return hashlib.blake2b(_to_bytes(data)).hexdigest()


def blake2s(data: bytes | np.ndarray | str) -> str:
    return hashlib.blake2s(_to_bytes(data)).hexdigest()


def xxhash(data: bytes | np.ndarray | str) -> str:
    h = 0
    for b in _to_bytes(data):
        h = (h * 31 + b) & 0xFFFFFFFF
    return format(h, "08x")


def _to_bytes(data) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode("utf-8")
    if isinstance(data, np.ndarray):
        return data.tobytes()
    if isinstance(data, Path):
        return data.read_bytes()
    return bytes(data)


def all_hashes(data) -> dict:
    return {
        "md5": md5(data),
        "sha1": sha1(data),
        "sha256": sha256(data),
        "sha512": sha512(data),
        "crc32": crc32(data),
        "blake2b": blake2b(data),
        "blake2s": blake2s(data),
    }


def file_hashes(path: str | Path) -> dict:
    p = Path(path)
    data = p.read_bytes()
    h = all_hashes(data)
    h["size"] = p.stat().st_size
    return h


def verify_hash(data: bytes | str | Path, expected: str, algo: str = "sha256") -> bool:
    if algo == "md5":
        return md5(data).lower() == expected.lower()
    if algo == "sha1":
        return sha1(data).lower() == expected.lower()
    if algo == "sha256":
        return sha256(data).lower() == expected.lower()
    if algo == "sha512":
        return sha512(data).lower() == expected.lower()
    if algo == "crc32":
        return crc32(data).lower() == expected.lower()
    return False


def base64_encode(data: bytes | np.ndarray | str) -> str:
    import base64
    return base64.b64encode(_to_bytes(data)).decode("ascii")


def base64_decode(text: str) -> bytes:
    import base64
    return base64.b64decode(text)


def base64_decode_to_image(text: str) -> np.ndarray:
    from PIL import Image
    import io
    raw = base64_decode(text)
    img = Image.open(io.BytesIO(raw))
    from .utils import pil_to_np
    return pil_to_np(img)
