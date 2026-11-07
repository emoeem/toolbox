#!/usr/bin/env python3
"""生成确定性的核心图像测试样本。

所有样本由固定参数/固定种子的 numpy 代码生成，不依赖外部图片，
用于 tests/test_engine_baseline.py 的引擎基线对照。

用法：
    uv run python tools/make_test_samples.py [--out tests/fixtures/samples] [--force]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / 'tests' / 'fixtures' / 'samples'

SAMPLES = ('gradient.png', 'checker.png', 'noise.png', 'synthetic.png')


def gradient(w: int = 64, h: int = 64) -> np.ndarray:
    x = np.linspace(0.0, 255.0, w, dtype=np.float32)
    y = np.linspace(0.0, 255.0, h, dtype=np.float32)[:, None]
    r = np.broadcast_to(x, (h, w))
    g = np.broadcast_to(y, (h, w))
    b = (r + g) / 2.0
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


def checker(w: int = 64, h: int = 64, cell: int = 8) -> np.ndarray:
    xx, yy = np.meshgrid(np.arange(w), np.arange(h))
    mask = ((xx // cell + yy // cell) % 2).astype(np.float32)
    img = np.empty((h, w, 3), np.float32)
    img[..., 0] = mask * 255.0
    img[..., 1] = 128.0
    img[..., 2] = (1.0 - mask) * 255.0
    return img.astype(np.uint8)


def noise(w: int = 96, h: int = 96, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def synthetic(w: int = 128, h: int = 128, seed: int = 7) -> np.ndarray:
    """渐变 + 圆形 + 固定种子噪声的合成图，覆盖连续/边缘/纹理三类特征。"""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy, rad = w // 2, h // 2, min(w, h) // 3
    circle = ((xx - cx) ** 2 + (yy - cy) ** 2 <= rad * rad).astype(np.float32)
    img = np.empty((h, w, 3), np.float32)
    img[..., 0] = xx / max(1, w - 1) * 255.0
    img[..., 1] = 255.0 - xx / max(1, w - 1) * 255.0
    img[..., 2] = 128.0 + (yy / max(1, h - 1) - 0.5) * 80.0
    img += circle[..., None] * 40.0
    img += rng.uniform(-8.0, 8.0, size=(h, w, 3))
    return np.clip(img, 0.0, 255.0).astype(np.uint8)


def generate(out_dir: Path | str = DEFAULT_OUT, force: bool = False) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    images = {
        'gradient.png': gradient(),
        'checker.png': checker(),
        'noise.png': noise(),
        'synthetic.png': synthetic(),
    }
    written: list[Path] = []
    for name, arr in images.items():
        path = out / name
        if force or not path.exists():
            Image.fromarray(arr, 'RGB').save(path, format='PNG')
            written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description='生成核心图像测试样本')
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--force', action='store_true', help='覆盖已存在的样本')
    args = parser.parse_args()
    written = generate(args.out, force=args.force)
    for path in written:
        print(f'wrote {path}')
    if not written:
        print('all samples already exist (use --force to overwrite)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
