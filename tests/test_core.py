"""Regression tests for processors.core.

This module had no coverage at all, which is how a broken `contrast()` (and a
half-wrapped `hue_shift()`) reached the UI. Everything asserted here is a
behaviour the adjust panel depends on.
"""
import os
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from processors import core as c
from processors.utils import clamp, ensure_rgb, ensure_writable_dir, u8


def _gradient(h=64, w=256):
    """Full 0..255 ramp so every LUT entry is exercised."""
    row = np.arange(w, dtype=np.uint8)
    return np.repeat(np.repeat(row.reshape(1, w, 1), 3, axis=2), h, axis=0)


def _hue360(px) -> float:
    """Read an RGB pixel's hue on OpenCV's float32 0..360 scale."""
    f = px.reshape(1, 1, 3).astype(np.float32) / 255.0
    return float(cv2.cvtColor(f, cv2.COLOR_RGB2HSV)[0, 0, 0])


class TestContrast(unittest.TestCase):
    def test_identity_at_default(self):
        rng = np.random.default_rng(0)
        for img in (_gradient(), rng.integers(0, 256, (40, 50, 3), np.uint8)):
            self.assertTrue(np.array_equal(c.contrast(img, 0.0), img))

    def test_does_not_posterize(self):
        # The 255x-too-strong factor collapsed a full ramp to ~3 output levels.
        grad = _gradient(1, 256)
        for value in (-0.5, -0.2, 0.2, 0.5):
            out = c.contrast(grad, value)
            levels = np.unique(out[..., 0]).size
            self.assertGreater(levels, 32,
                               f"contrast({value}) collapsed a 256-step ramp to {levels} levels")

    def test_matches_reference_formula(self):
        def ref(a, v):
            v = float(np.clip(v, -0.99, 0.99))
            f = (259.0 * (v * 255.0 + 255.0)) / (255.0 * (259.0 - v * 255.0))
            return u8(clamp(f * (ensure_rgb(a).astype(np.float32) - 128.0) + 128.0))

        rng = np.random.default_rng(7)
        img = rng.integers(0, 256, (40, 40, 3), np.uint8)
        for value in (-0.99, -0.5, -0.2, 0.0, 0.2, 0.5, 0.99):
            self.assertTrue(np.array_equal(c.contrast(img, value), ref(img, value)),
                            f"contrast({value}) diverged from the reference curve")

    def test_transfer_curve_is_monotonic(self):
        row = c.contrast(_gradient(1, 256), 0.5)[0, :, 0].astype(int)
        self.assertTrue(np.all(np.diff(row) >= 0))

    def test_value_is_clamped_and_denominator_never_vanishes(self):
        img = _gradient(1, 256)
        for value in (5.0, -5.0, 1000.0):
            out = c.contrast(img, value)
            self.assertEqual(out.shape, img.shape)
            self.assertEqual(out.dtype, np.uint8)


class TestHueShift(unittest.TestCase):
    def _wheel(self):
        hues = np.arange(0, 360, 15, dtype=np.float32)
        hsv = np.zeros((1, len(hues), 3), np.float32)
        hsv[0, :, 0] = hues
        hsv[0, :, 1] = 1.0
        hsv[0, :, 2] = 1.0
        return hues, (cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB) * 255).astype(np.uint8)

    def test_zero_is_identity(self):
        hues, wheel = self._wheel()
        self.assertTrue(np.array_equal(c.hue_shift(wheel, 0), wheel))

    def test_360_is_identity(self):
        _, wheel = self._wheel()
        self.assertTrue(np.array_equal(c.hue_shift(wheel, 360), wheel))

    def test_rotates_the_whole_hue_circle(self):
        # `% 180` folded the circle in half: wrong for hues >= 180-degrees.
        hues, wheel = self._wheel()
        for degrees in (30, 60, 90, 180, -90, 270):
            out = c.hue_shift(wheel, degrees)
            for i, hue in enumerate(hues):
                got = _hue360(out[0, i])
                want = float((hue + degrees) % 360)
                err = abs(((got - want + 180) % 360) - 180)
                self.assertLess(err, 5.0,
                                f"hue {hue} shifted {degrees} gave {got}, want {want}")

    def test_180_actually_inverts_low_hues(self):
        # A 180-degree shift used to be a no-op for every hue below 180.
        red = np.zeros((1, 1, 3), np.uint8)
        red[0, 0] = (255, 0, 0)
        out = c.hue_shift(red, 180)
        self.assertFalse(np.array_equal(out, red))
        self.assertGreater(out[0, 0, 1], 200)  # red -> cyan
        self.assertGreater(out[0, 0, 2], 200)


class TestPointOps(unittest.TestCase):
    def test_identity_at_defaults(self):
        rng = np.random.default_rng(2)
        img = rng.integers(0, 256, (50, 70, 3), np.uint8)
        self.assertTrue(np.array_equal(c.brightness(img, 0.0), img))
        self.assertTrue(np.array_equal(c.contrast(img, 0.0), img))
        self.assertTrue(np.array_equal(c.exposure(img, 0.0), img))
        self.assertTrue(np.array_equal(c.gamma(img, 1.0), img))
        # HSV round-trip is lossy by at most one level.
        for fn in (c.saturation, c.vibrance):
            self.assertLessEqual(
                int(np.abs(fn(img, 0.0).astype(int) - img.astype(int)).max()), 1)

    def test_lut_path_is_bit_exact_with_float_math(self):
        rng = np.random.default_rng(3)
        img = rng.integers(0, 256, (80, 120, 3), np.uint8)

        def ref_brightness(a, v):
            return u8(clamp(ensure_rgb(a).astype(np.float32) + v * 255))

        def ref_contrast(a, v):
            v = float(np.clip(v, -0.99, 0.99))
            f = 259.0 * (v * 255.0 + 255.0) / (255.0 * (259.0 - v * 255.0))
            return u8(clamp(f * (ensure_rgb(a).astype(np.float32) - 128.0) + 128.0))

        def ref_exposure(a, s):
            return u8(clamp(ensure_rgb(a).astype(np.float32) * (2.0 ** s)))

        for v in (-1.0, -0.3, 0.25, 1.0):
            self.assertTrue(np.array_equal(c.brightness(img, v), ref_brightness(img, v)))
        for v in (-0.9, -0.4, 0.35, 0.99):
            self.assertTrue(np.array_equal(c.contrast(img, v), ref_contrast(img, v)))
        for s in (-3.0, -1.0, 0.75, 3.0):
            self.assertTrue(np.array_equal(c.exposure(img, s), ref_exposure(img, s)))

    def test_float_input_uses_the_float_path(self):
        img = np.full((8, 8, 3), 100.0, np.float32)
        out = c.brightness(img, 0.1)
        self.assertEqual(out.dtype, np.uint8)
        self.assertTrue(np.all(out > 100))

    def test_does_not_mutate_the_input(self):
        rng = np.random.default_rng(4)
        for fn in (c.brightness, c.contrast, c.exposure, c.hue_shift, c.vibrance,
                   c.saturation, c.grayscale, c.invert):
            img = rng.integers(0, 256, (20, 20, 3), np.uint8)
            before = img.copy()
            fn(img, 0.2) if fn not in (c.grayscale, c.invert) else fn(img)
            self.assertTrue(np.array_equal(img, before), f"{fn.__name__} mutated its input")


class TestVignetteAndBorder(unittest.TestCase):
    def test_vignette_darkens_corners(self):
        img = np.full((80, 80, 3), 240, np.uint8)
        out = c.vignette(img, 0.6)
        self.assertEqual(out.shape, img.shape)
        # Corner is attenuated, the exact centre is untouched (mask == 1 there).
        self.assertLess(int(out[0, 0, 0]), int(out[40, 40, 0]))
        self.assertLess(int(out[0, 0, 0]), 240)
        self.assertEqual(int(out[40, 40, 0]), 240)

    def test_vignette_matches_float64_reference(self):
        rng = np.random.default_rng(5)
        img = rng.integers(0, 256, (40, 60, 3), np.uint8)

        def ref(a, strength):
            a = ensure_rgb(a).astype(np.float32)
            h, w = a.shape[:2]
            y, x = np.indices((h, w))
            cx, cy = w / 2.0, h / 2.0
            dist = np.sqrt(((x - cx) ** 2 + (y - cy) ** 2) / (cx ** 2 + cy ** 2))
            return u8(clamp(a * np.clip(1.0 - dist * strength, 0, 1)[..., None]))

        self.assertLessEqual(
            int(np.abs(c.vignette(img, 0.5).astype(int) - ref(img, 0.5).astype(int)).max()), 1)

    def test_border_blur_fill_keeps_the_centre(self):
        img = np.arange(20 * 20 * 3, dtype=np.uint8).reshape(20, 20, 3)
        out = c.border(img, 5, 5, 5, 5, (255, 0, 0), blur_fill=True)
        self.assertEqual(out.shape, (30, 30, 3))
        self.assertTrue(np.array_equal(out[5:25, 5:25], img))
        self.assertTrue(np.array_equal(out[0, 0], np.array([255, 0, 0], np.uint8)))


class TestEnsureWritableDir(unittest.TestCase):
    def test_uses_a_writable_directory(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(ensure_writable_dir(Path(td) / "sub"), Path(td) / "sub")

    @unittest.skipIf(os.geteuid() == 0, "root bypasses directory permissions")
    def test_falls_back_when_the_target_is_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            ro = Path(td) / "ro"
            ro.mkdir()
            ro.chmod(0o500)
            try:
                resolved = ensure_writable_dir(ro, fallback=Path(td) / "fallback")
                self.assertNotEqual(resolved, ro)
                self.assertTrue(os.access(resolved, os.W_OK))
            finally:
                ro.chmod(0o700)

    def test_existing_read_only_dir_is_not_accepted_just_because_mkdir_succeeds(self):
        # mkdir(exist_ok=True) on an existing directory succeeds even when the
        # directory cannot be written to; the probe must catch that.
        with tempfile.TemporaryDirectory() as td:
            ro = Path(td) / "ro2"
            ro.mkdir()
            if os.geteuid() == 0:
                self.skipTest("root bypasses directory permissions")
            ro.chmod(0o500)
            try:
                self.assertNotEqual(ensure_writable_dir(ro), ro)
            finally:
                ro.chmod(0o700)


if __name__ == "__main__":
    unittest.main()
