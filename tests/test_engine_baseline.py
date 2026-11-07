"""核心图像处理引擎基线对照测试。

目的：在 UI 迁移（Phase 2-6）期间锁定现有 Python 引擎的输出行为，
保证新 UI 接入后处理结果与旧程序一致。

规则：
- 首次运行时若基线不存在，自动生成 tests/baselines/engine_baseline.json，
  并提示提交该文件作为基线。
- 之后每次运行逐项对照 sha256；任何处理器行为变化都会在这里失败。
- 依赖版本或平台更换后（uv.lock 固定依赖），重新生成基线并提交：
      TOOLBOX_REGEN_BASELINE=1 uv run python -m unittest tests.test_engine_baseline
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools'))

import make_test_samples  # noqa: E402

from processors import core as img_core  # noqa: E402
from processors._jit import NUMBA_OK  # noqa: E402
from processors.utils import load_image, save_image  # noqa: E402

SAMPLES_DIR = REPO / 'tests' / 'fixtures' / 'samples'
BASELINE_PATH = REPO / 'tests' / 'baselines' / 'engine_baseline.json'
BASELINE_VERSION = 1

# 在每个样本上执行的核心算子（名称, 调用）。覆盖点运算/色彩/几何/增强四类路径。
OPS = (
    ('brightness+0.1', lambda im: img_core.brightness(im, 0.1)),
    ('contrast+0.2', lambda im: img_core.contrast(im, 0.2)),
    ('saturation+0.5', lambda im: img_core.saturation(im, 0.5)),
    ('gamma1.5', lambda im: img_core.gamma(im, 1.5)),
    ('exposure+0.5', lambda im: img_core.exposure(im, 0.5)),
    ('hue_shift30', lambda im: img_core.hue_shift(im, 30.0)),
    ('vibrance+0.3', lambda im: img_core.vibrance(im, 0.3)),
    ('highlights_shadows', lambda im: img_core.highlights_shadows(im, 0.2, -0.2)),
    ('sharpen1.0', lambda im: img_core.sharpen(im, 1.0)),
    ('grayscale', img_core.grayscale),
    ('invert', img_core.invert),
    ('black_white128', lambda im: img_core.black_white(im, 128)),
    ('histogram_equalize', img_core.histogram_equalize),
    ('clahe', img_core.clahe),
    ('vignette0.5', lambda im: img_core.vignette(im, 0.5)),
    ('flip_h', img_core.flip_h),
    ('flip_v', img_core.flip_v),
    ('rotate90', lambda im: img_core.rotate(im, 90.0)),
    ('rotate33', lambda im: img_core.rotate(im, 33.0)),
    ('scale0.5', lambda im: img_core.scale(im, 0.5)),
    ('center_crop32', lambda im: img_core.center_crop(im, 32, 32)),
)


def _platform_tag() -> str:
    # numba 两条路径数值结果不等价（见 processors/_jit.py），必须纳入基线身份。
    return f'{sys.platform}-py{sys.version_info.major}.{sys.version_info.minor}-numba-{"on" if NUMBA_OK else "off"}'


def _entry(arr: np.ndarray) -> dict:
    return {
        'sha256': hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest(),
        'shape': list(arr.shape),
        'dtype': str(arr.dtype),
    }


def _compute_entries() -> dict:
    entries: dict[str, dict] = {}
    images: dict[str, np.ndarray] = {}
    for name in make_test_samples.SAMPLES:
        path = SAMPLES_DIR / name
        images[name] = load_image(path)
        entries[f'sample:{name}'] = _entry(images[name])
    for sample_name, img in images.items():
        for op_name, fn in OPS:
            entries[f'op:{sample_name}/{op_name}'] = _entry(fn(img))
    # IO 往返确定性：save_image → load_image 的像素级稳定性。
    with tempfile.TemporaryDirectory() as tmp:
        roundtrip = load_image(save_image(images['gradient.png'], Path(tmp) / 'rt.png'))
    entries['io:gradient.png/save+load'] = _entry(roundtrip)
    return entries


class EngineBaselineTest(unittest.TestCase):
    regenerated = False
    images: dict[str, np.ndarray] = {}

    @classmethod
    def setUpClass(cls):
        make_test_samples.generate(SAMPLES_DIR, force=False)
        cls.images = {name: load_image(SAMPLES_DIR / name) for name in make_test_samples.SAMPLES}
        if os.environ.get('TOOLBOX_REGEN_BASELINE') == '1' or not BASELINE_PATH.exists():
            BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = {'version': BASELINE_VERSION, 'platform': _platform_tag(), 'entries': _compute_entries()}
            BASELINE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            cls.regenerated = True

    @classmethod
    def tearDownClass(cls):
        if cls.regenerated:
            print(f'\n[基线] 已生成 {BASELINE_PATH.relative_to(REPO)}，请提交作为迁移对照基线。')

    def _baseline(self) -> dict:
        payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
        self.assertEqual(payload.get('version'), BASELINE_VERSION, '基线版本不符，请重新生成')
        if payload.get('platform') != _platform_tag():
            # 环境不一致（平台/Python/numba 状态）时结果本身不可比，跳过而非误报。
            self.skipTest(f'基线生成于 {payload.get("platform")}，当前为 {_platform_tag()}；'
                          '如需在本环境固定基线，请以 TOOLBOX_REGEN_BASELINE=1 重新生成并提交')
        return payload['entries']

    def _skip_if_regenerated(self):
        if self.regenerated:
            self.skipTest('本次运行重新生成了基线，请提交后再次运行')

    def test_samples_unchanged(self):
        self._skip_if_regenerated()
        baseline = self._baseline()
        for name, img in self.images.items():
            self.assertEqual(_entry(img), baseline[f'sample:{name}'],
                             f'样本 {name} 与基线不符；请确认样本生成代码未被改动')

    def test_ops_match_baseline(self):
        self._skip_if_regenerated()
        baseline = self._baseline()
        mismatches = []
        for sample_name, img in self.images.items():
            for op_name, fn in OPS:
                key = f'op:{sample_name}/{op_name}'
                entry = _entry(fn(img))
                if entry != baseline.get(key):
                    mismatches.append(f'{key}: expected {baseline.get(key)} got {entry}')
        self.assertEqual(mismatches, [], '核心算子输出与基线不一致（Phase 0 要求结果无回退）')

    def test_save_load_roundtrip_deterministic(self):
        self._skip_if_regenerated()
        baseline = self._baseline()
        with tempfile.TemporaryDirectory() as tmp:
            roundtrip = load_image(save_image(self.images['gradient.png'], Path(tmp) / 'rt.png'))
        self.assertEqual(_entry(roundtrip), baseline['io:gradient.png/save+load'],
                         'save_image/load_image 往返与基线不符')


if __name__ == '__main__':
    unittest.main()
