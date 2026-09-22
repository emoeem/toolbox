from __future__ import annotations

import numpy as np

from .utils import ensure_rgb, u8, clamp


def ascii_art(img: np.ndarray, cols: int = 100, chars: str = " .:-=+*#%@",
              invert: bool = False) -> str:
    img_ = ensure_rgb(img)
    gray = cv2.cvtColor(img_, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    aspect = 0.5
    rows = max(1, int(h / w * cols * aspect))
    small = cv2.resize(gray, (cols, rows))
    normalized = small / 255.0
    if invert:
        normalized = 1 - normalized
    indices = (normalized * (len(chars) - 1)).astype(int)
    lines = []
    for row in indices:
        lines.append("".join(chars[i] for i in row))
    return "\n".join(lines)


def ascii_image(img: np.ndarray, cols: int = 100, cell_w: int = 6, cell_h: int = 10,
               chars: str = " .:-=+*#%@", invert: bool = False,
               color: tuple = (0, 255, 255)) -> np.ndarray:
    from PIL import Image, ImageDraw, ImageFont
    text = ascii_art(img, cols, chars, invert)
    lines = text.split("\n")
    rows_count = len(lines)
    h = rows_count * cell_h
    w = cols * cell_w
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", cell_h)
    except Exception:
        font = ImageFont.load_default()
    for y, line in enumerate(lines):
        for x, ch in enumerate(line):
            draw.text((x * cell_w, y * cell_h), ch, fill=color, font=font)
    from .utils import pil_to_np
    return pil_to_np(canvas)


try:
    import cv2
except Exception:
    cv2 = None


def code_preview(code: str, language: str = "python", bg_color=(25, 25, 35),
                 text_color=(220, 220, 240), title: str | None = None,
                 width: int = 1000, font_size: int = 16) -> np.ndarray:
    from PIL import Image, ImageDraw, ImageFont
    import textwrap

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    lines = code.split("\n")
    padding = 40
    line_h = font_size + 6
    number_w = len(str(len(lines))) * font_size + padding
    content_w = width - padding * 3 - number_w
    wrapped = []
    for line in lines:
        sublines = textwrap.wrap(line, width=content_w // (font_size // 2) if font_size >= 2 else 80) or [""]
        wrapped.extend(sublines)

    h = padding * 2 + len(wrapped) * line_h + (40 if title else 0)
    canvas = Image.new("RGB", (width, h), bg_color)
    draw = ImageDraw.Draw(canvas)

    y = padding + (40 if title else 0)
    start_line = 1
    current_line = 0
    for wrapped_line in wrapped:
        if current_line % max(1, (len(wrapped) // max(len(lines), 1) + 1)) == 0 and start_line <= len(lines):
            line_num_text = str(start_line)
            start_line += 1
        else:
            line_num_text = ""
        current_line += 1
        draw.text((padding, y), line_num_text, fill=(100, 100, 120), font=font)
        draw.text((padding + number_w, y), wrapped_line, fill=text_color, font=font)
        y += line_h

    if title:
        draw.rounded_rectangle([padding, padding, width - padding, padding + 30], 8, fill=(40, 40, 55))
        draw.text((padding + 10, padding + 7), title, fill=(180, 180, 200), font=font)
        draw.ellipse([padding + 10, padding + 10, padding + 22, padding + 22], fill=(255, 95, 86))
        draw.ellipse([padding + 28, padding + 10, padding + 40, padding + 22], fill=(255, 189, 46))
        draw.ellipse([padding + 46, padding + 10, padding + 58, padding + 22], fill=(39, 201, 63))

    from .utils import pil_to_np
    return pil_to_np(canvas)
