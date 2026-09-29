"""Every registered filter must survive degenerate and awkward image geometry.

This sweep is what caught a batch of size-dependent crashes: a missing colon in
`dither_bayer` (`[:h, w]` indexed one column), `old_tv`'s (h, 1) scanline array
failing to broadcast against non-square images, `anaglyph`'s zero shift on narrow
images, and empty-slice handling in kaleidoscope / mirror_reflection /
dual_split / reduce_colors / glitch.
"""
import unittest
import zlib

import numpy as np

from processors.filter_registry import FilterDefRegistry
import processors.filter_registry  # noqa: F401  (import registers the filters)
from processors.filter_chain import FilterChain

# Odd, thin, tiny and square: each of these broke at least one filter.
SIZES = [
    (1, 1), (2, 2), (3, 3), (5, 3), (3, 5), (8, 8), (7, 5),
    (1, 100), (100, 1), (3, 200), (200, 3), (16, 24), (24, 16),
    (32, 40), (33, 77), (64, 64),
]


class TestAllFiltersSurviveGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = FilterDefRegistry.instance()
        cls.keys = sorted(cls.registry.all())

    def test_registry_is_populated(self):
        self.assertGreater(len(self.keys), 100)

    def test_no_filter_raises_for_any_size(self):
        failures = []
        for key in self.keys:
            defn = self.registry.get(key)
            for size in SIZES:
                # zlib.crc32, not hash(): PYTHONHASHSEED randomisation would
                # make the inputs differ on every run and on every machine.
                seed = zlib.crc32(f"{key}:{size}".encode())
                img = np.random.default_rng(seed).integers(0, 255, size + (3,), np.uint8)
                try:
                    out = defn.apply(img.copy(), None)
                except Exception as exc:
                    failures.append(f"{key} {size}: {type(exc).__name__}: {exc}")
                    continue
                if out is None or not isinstance(out, np.ndarray):
                    failures.append(f"{key} {size}: returned {type(out)}")
                elif out.dtype != np.uint8 or out.ndim != 3 or out.shape[2] not in (3, 4):
                    failures.append(f"{key} {size}: bad output dtype={out.dtype} shape={out.shape}")
        self.assertEqual(failures, [], "\n".join(failures[:40]))

    def test_greyscale_input_is_accepted(self):
        failures = []
        for key in self.keys:
            defn = self.registry.get(key)
            img = np.random.default_rng(7).integers(0, 255, (24, 32), np.uint8)
            try:
                out = defn.apply(img, None)
                if out is None or out.dtype != np.uint8:
                    failures.append(f"{key}: bad output {out!r}")
            except Exception as exc:
                failures.append(f"{key}: {type(exc).__name__}: {exc}")
        self.assertEqual(failures, [], "\n".join(failures[:40]))


class TestSpecificGeometryBugs(unittest.TestCase):
    """Targeted assertions so a regression names the actual defect."""

    def test_dither_bayer_uses_a_2d_tile(self):
        from processors import filters as F
        # A missing colon made this index a single column: it crashed for h != w
        # and otherwise dithered with one column broadcast across every row.
        img = np.random.default_rng(0).integers(0, 255, (32, 40, 3), np.uint8)
        out = F.dither_bayer(img, levels=4, order=4)
        self.assertEqual(out.shape, img.shape)
        tiled = F.dither_bayer(np.full((32, 40, 3), 128, np.uint8), levels=4, order=4)
        # A real 4x4 Bayer tile varies both across and down; broadcasting a
        # single column made every row of a tile identical.
        self.assertGreater(len(np.unique(tiled[0, :4, 0])), 1)
        self.assertFalse(np.array_equal(tiled[0, :4, 0], tiled[1, :4, 0]))

    def test_old_tv_handles_non_square(self):
        from processors import filters as F
        for size in [(32, 40), (40, 32), (16, 64)]:
            img = np.full(size + (3,), 200, np.uint8)
            out = F.old_tv(img)
            self.assertEqual(out.shape, img.shape)
            # Every other scanline is attenuated (rows 0, 2, 4 ... are darker).
            self.assertLess(int(out[0].mean()), int(out[1].mean()))

    def test_anaglyph_handles_narrow_images(self):
        from processors import filters as F
        for w in (1, 8, 40, 49, 64, 100):
            img = np.random.default_rng(w).integers(0, 255, (16, w, 3), np.uint8)
            self.assertEqual(F.anaglyph(img).shape, img.shape)

    def test_degenerate_geometry_filters(self):
        from processors import filters as F
        from processors import advanced_filters as A
        tiny = np.random.default_rng(1).integers(0, 255, (1, 1, 3), np.uint8)
        for fn in (A.mirror_reflection, A.dual_split, A.kaleidoscope,
                   A.reduce_colors, F.glitch, F.anaglyph, F.old_tv, F.dither_bayer):
            out = fn(tiny.copy())
            self.assertEqual(out.shape, tiny.shape, fn.__name__)
            self.assertEqual(out.dtype, np.uint8, fn.__name__)
        thin = np.random.default_rng(2).integers(0, 255, (3, 200, 3), np.uint8)
        for fn in (A.kaleidoscope, A.reduce_colors, F.glitch):
            self.assertEqual(fn(thin.copy()).shape, thin.shape, fn.__name__)


class TestChainSurvives(unittest.TestCase):
    def test_chain_of_many_filters_on_an_odd_size(self):
        reg = FilterDefRegistry.instance()
        chain = FilterChain()
        for key in sorted(reg.all())[:25]:
            chain.add(key)
        img = np.random.default_rng(3).integers(0, 255, (24, 32, 3), np.uint8)
        out = chain.apply(img)
        self.assertEqual(out.dtype, np.uint8)
        self.assertEqual(out.ndim, 3)


if __name__ == "__main__":
    unittest.main()
