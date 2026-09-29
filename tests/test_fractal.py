import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import numpy as np
from PIL import Image

from processors.cancellation import CancelToken, CancelledError
from processors.filter_defs import FilterDefRegistry, FilterCategory
from processors.filter_registry import register_curated_filters
from processors.filter_chain import FilterChain, FilterStep, FilterStepError
from processors.filter_presets import save_preset, load_preset, list_presets, delete_preset, preset_exists
from processors.fractal import (
    FractalColoring, FractalParams, FractalResult,
    JuliaConstant, PhoenixConstant, Fractal3DCamera,
    DIM_2D, DIM_3D,
    render_fractal, render_mandelbulb,
    formula_keys, formula_info,
    register_fractal_filters,
)


class TestFractalFormulaRegistry(unittest.TestCase):
    def setUp(self):
        self.keys = formula_keys()

    def test_all_formulas_registered(self):
        self.assertGreaterEqual(len(self.keys), 12)
        for expected in ["mandelbrot", "julia", "burning_ship", "tricorn",
                        "multibrot", "multicorn", "celtic", "buffalo",
                        "phoenix", "newton", "nova", "magnet_i",
                        "magnet_ii", "buddhabrot",
                        "perpendicular_burning_ship"]:
            self.assertIn(expected, self.keys)

    def test_formula_info_valid(self):
        for k in self.keys:
            info = formula_info(k)
            self.assertIsNotNone(info)
            self.assertIn("zh_name", info)
            self.assertIn("escape_fn", info)
            self.assertIn("dimension", info)


class TestFractalRendering2D(unittest.TestCase):
    def setUp(self):
        self.params = FractalParams(width=64, height=64, iterations=64)

    def test_default_params_valid(self):
        p = FractalParams()
        p.validate()

    def test_invalid_width(self):
        p = FractalParams(width=0)
        with self.assertRaises(ValueError):
            p.validate()

    def test_invalid_scale(self):
        p = FractalParams(scale=-1.0)
        with self.assertRaises(ValueError):
            p.validate()

    def test_invalid_power(self):
        p = FractalParams(power=0.0)
        with self.assertRaises(ValueError):
            p.validate()

    def test_mandelbrot_64x64(self):
        r = render_fractal(64, 64, "mandelbrot", self.params)
        self.assertIsInstance(r.image, Image.Image)
        self.assertEqual(r.image.size, (64, 64))
        self.assertEqual(r.iterations_array.shape, (64, 64))
        self.assertEqual(r.iterations_array.dtype, np.int32)
        self.assertTrue(r.escaped_mask.dtype == bool)
        self.assertTrue(r.escaped_mask.any())

    def test_julia_uses_constant(self):
        p1 = FractalParams(julia_c=JuliaConstant(-0.8, 0.156))
        p2 = FractalParams(julia_c=JuliaConstant(0.5, 0.5))
        r1 = render_fractal(64, 64, "julia", p1)
        r2 = render_fractal(64, 64, "julia", p2)
        diff = np.abs(np.array(r1.image).astype(float) - np.array(r2.image).astype(float)).mean()
        self.assertGreater(diff, 5.0)

    def test_multibrot_power_changes_output(self):
        p1 = FractalParams(power=2.0, iterations=64)
        p2 = FractalParams(power=4.0, iterations=64)
        r1 = render_fractal(64, 64, "multibrot", p1)
        r2 = render_fractal(64, 64, "multibrot", p2)
        diff = np.abs(np.array(r1.image).astype(float) - np.array(r2.image).astype(float)).mean()
        self.assertGreater(diff, 5.0)

    def test_iterations_change_output(self):
        p1 = FractalParams(iterations=32)
        p2 = FractalParams(iterations=256)
        r1 = render_fractal(64, 64, "mandelbrot", p1)
        r2 = render_fractal(64, 64, "mandelbrot", p2)
        diff = np.abs(np.array(r1.image).astype(float) - np.array(r2.image).astype(float)).mean()
        self.assertGreater(diff, 2.0)

    def test_center_change_output(self):
        p1 = FractalParams(cx=-0.5, cy=0.0, scale=3.0)
        p2 = FractalParams(cx=0.0, cy=0.0, scale=1.5)
        r1 = render_fractal(64, 64, "mandelbrot", p1)
        r2 = render_fractal(64, 64, "mandelbrot", p2)
        diff = np.abs(np.array(r1.image).astype(float) - np.array(r2.image).astype(float)).mean()
        self.assertGreater(diff, 5.0)

    def test_coloring_modes_differ(self):
        ps = []
        for c in [FractalColoring.SMOOTH, FractalColoring.BANDED, FractalColoring.GRAYSCALE]:
            p = FractalParams(coloring=c, iterations=64)
            ps.append(p)
        outs = [np.array(render_fractal(64, 64, "mandelbrot", p).image) for p in ps]
        self.assertGreater(np.abs(outs[0].astype(float) - outs[1].astype(float)).mean(), 3.0)
        self.assertGreater(np.abs(outs[0].astype(float) - outs[2].astype(float)).mean(), 3.0)

    def test_all_formulas_produce_images(self):
        for k in formula_keys():
            p = FractalParams(width=32, height=32, iterations=32)
            r = render_fractal(32, 32, k, p)
            self.assertIsInstance(r.image, Image.Image)
            self.assertEqual(r.image.size, (32, 32))

    def test_buddhabrot_density_visualization(self):
        p = FractalParams(width=64, height=64, iterations=64)
        r = render_fractal(64, 64, "buddhabrot", p)
        self.assertIsInstance(r.image, Image.Image)

    def test_unknown_formula_raises(self):
        with self.assertRaises(ValueError):
            render_fractal(64, 64, "nonexistent", self.params)

    def test_stable_reproducible(self):
        p = FractalParams(iterations=64)
        r1 = np.array(render_fractal(64, 64, "mandelbrot", p).image)
        r2 = np.array(render_fractal(64, 64, "mandelbrot", p).image)
        np.testing.assert_array_equal(r1, r2)


class TestFractalCancel(unittest.TestCase):
    def test_cancel_token_interrupts(self):
        ct = CancelToken()
        progress_vals = []
        def prog(i):
            progress_vals.append(i)
            if i > 20:
                ct.cancel()
        with self.assertRaises(CancelledError):
            render_fractal(512, 512, "mandelbrot",
                           FractalParams(iterations=512),
                           cancel_token=ct, progress_cb=prog)
        self.assertTrue(len(progress_vals) > 0)

    def test_progress_is_monotonic(self):
        progress_vals = []
        def prog(i):
            progress_vals.append(i)
        render_fractal(128, 128, "mandelbrot",
                       FractalParams(iterations=64),
                       progress_cb=prog)
        self.assertTrue(progress_vals[-1] >= 99)
        for i in range(1, len(progress_vals)):
            self.assertGreaterEqual(progress_vals[i], progress_vals[i - 1])


class TestFractal3D(unittest.TestCase):
    def test_mandelbulb_smoke(self):
        r = render_mandelbulb(32, 32, power=8.0, iterations=16)
        self.assertIsInstance(r.image, Image.Image)
        self.assertEqual(r.image.size, (32, 32))

    def test_mandelbulb_power_changes_output(self):
        r1 = np.array(render_mandelbulb(32, 32, power=5.0, iterations=16).image)
        r2 = np.array(render_mandelbulb(32, 32, power=12.0, iterations=16).image)
        diff = np.abs(r1.astype(float) - r2.astype(float)).mean()
        self.assertGreater(diff, 2.0)


class TestFractalFilterDef(unittest.TestCase):
    def setUp(self):
        register_curated_filters()
        self.reg = FilterDefRegistry.instance()

    def test_fractal_filters_registered(self):
        fractal_keys = [k for k in self.reg.keys() if k.startswith("fractal_")]
        self.assertGreaterEqual(len(fractal_keys), 12)

    def test_filterdef_category_fractal(self):
        fd = self.reg.get("fractal_mandelbrot")
        self.assertEqual(fd.category, FilterCategory.FRACTAL)

    def test_mandelbrot_apply(self):
        import numpy as np
        img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        fd = self.reg.get("fractal_mandelbrot")
        out = fd.apply(img, {"iterations": 64})
        self.assertEqual(out.shape, (64, 64, 3))
        self.assertEqual(out.dtype, np.uint8)

    def test_julia_filter_has_julia_params(self):
        fd = self.reg.get("fractal_julia")
        pnames = [p.name for p in fd.params]
        self.assertIn("julia_c_x", pnames)
        self.assertIn("julia_c_y", pnames)

    def test_mandelbrot_filter_no_julia_params(self):
        fd = self.reg.get("fractal_mandelbrot")
        pnames = [p.name for p in fd.params]
        self.assertNotIn("julia_c_x", pnames)

    def test_phoenix_has_phoenix_params(self):
        fd = self.reg.get("fractal_phoenix")
        pnames = [p.name for p in fd.params]
        self.assertIn("phoenix_c_x", pnames)
        self.assertIn("phoenix_c_y", pnames)

    def test_nova_has_relaxation_param(self):
        fd = self.reg.get("fractal_nova")
        pnames = [p.name for p in fd.params]
        self.assertIn("nova_relaxation", pnames)

    def test_filterchain_includes_fractal(self):
        import numpy as np
        img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        chain = FilterChain()
        chain.add("fractal_mandelbrot", params={"cx": -0.5, "iterations": 64})
        chain.add("fractal_julia", params={"julia_c_x": -0.7, "julia_c_y": 0.1, "iterations": 64})
        out = chain.apply(img.copy())
        self.assertEqual(out.shape, (64, 64, 3))

    def test_filterpreset_fractal_roundtrip(self):
        chain = FilterChain()
        chain.add("fractal_julia", params={
            "cx": 0.1, "cy": 0.2, "scale": 2.5,
            "iterations": 100, "coloring": "banded",
            "julia_c_x": -0.7, "julia_c_y": 0.1,
        })
        name = "_test_fractal_preset"
        save_preset(name, chain, overwrite=True)
        self.assertTrue(preset_exists(name))
        loaded = load_preset(name)
        self.assertEqual(loaded.steps[0].filter_key, "fractal_julia")
        self.assertEqual(loaded.steps[0].params.get("julia_c_x"), -0.7)
        self.assertEqual(loaded.steps[0].params.get("iterations"), 100)
        delete_preset(name)


if __name__ == "__main__":
    unittest.main()
