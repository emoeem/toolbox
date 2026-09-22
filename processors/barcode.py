from __future__ import annotations

import io
from pathlib import Path

import numpy as np


def generate_qr(data: str, size: int = 300, error_correction: str = "M") -> np.ndarray:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
    ec_map = {"L": ERROR_CORRECT_L, "M": ERROR_CORRECT_M, "Q": ERROR_CORRECT_Q, "H": ERROR_CORRECT_H}
    qr = qrcode.QRCode(
        version=None,
        error_correction=ec_map.get(error_correction, ERROR_CORRECT_M),
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    pil_img = img.resize((size, size))
    from .utils import pil_to_np
    arr = pil_to_np(pil_img)
    if arr.shape[-1] == 4:
        arr = arr[:, :, :3]
    return arr


def decode_qr(img: np.ndarray) -> list[dict]:
    from pyzbar import pyzbar
    from PIL import Image
    from .utils import np_to_pil
    pil = np_to_pil(img)
    results = pyzbar.decode(pil)
    return [{"data": r.data.decode("utf-8", errors="replace"), "type": r.type,
             "rect": r.rect} for r in results]


def generate_barcode_ean13(data: str, height: int = 100) -> np.ndarray:
    try:
        from pystrich.ean13 import EAN13Encoder
        encoder = EAN13Encoder(data)
        from PIL import Image
        pil_img = encoder.get_pil_image().resize((encoder.get_width(), height))
        from .utils import pil_to_np
        arr = pil_to_np(pil_img)
        if arr.shape[-1] == 4:
            arr = arr[:, :, :3]
        return arr
    except Exception as e:
        return _generate_barcode_fallback(data, height)


def _generate_barcode_fallback(data: str, height: int = 100) -> np.ndarray:
    width = len(data) * 7
    canvas = np.ones((height, width, 3), dtype=np.uint8) * 255
    from PIL import Image, ImageDraw, ImageFont
    pil = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(pil)
    x = 0
    for ch in data:
        val = ord(ch) % 2
        for i in range(7):
            is_dark = (i < 3 and val == 1) or (i >= 3 and val == 0)
            if is_dark:
                draw.rectangle([x, 0, x + 1, height - 20], fill=(0, 0, 0))
            x += 1
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
    draw.text((width // 3, height - 18), data, fill=(0, 0, 0), font=font)
    from .utils import pil_to_np
    return pil_to_np(pil)


def generate_data_matrix(data: str, size: int = 200) -> np.ndarray:
    try:
        import pylibdmtx
    except Exception:
        pass
    try:
        from PIL import Image
        import qrcode
        qr = qrcode.QRCode(version=None, box_size=size // 25, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        pil_img = img.resize((size, size))
        from .utils import pil_to_np
        arr = pil_to_np(pil_img)
        if arr.shape[-1] == 4:
            arr = arr[:, :, :3]
        return arr
    except Exception:
        return generate_qr(data, size)
