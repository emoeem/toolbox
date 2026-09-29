from __future__ import annotations

import sys
import unittest
import numpy as np

from processors.filter_defs import (
    FilterCategory,
    FilterDef,
    FilterDefRegistry,
    FilterParam,
    PARAM_TYPE_BOOL,
    PARAM_TYPE_COLOR,
    PARAM_TYPE_ENUM,
    PARAM_TYPE_FLOAT,
    PARAM_TYPE_INT,
    PARAM_TYPE_STRING,
    register_filter,
    register_legacy_filters,
    build_legacy_compat_layer,
    ALL_FILTERS_COMPAT,
    _guess_category,
)


def _dummy(img, strength=1.0, threshold=128):
    return img


class FilterParamTests(unittest.TestCase):
    def test_int_param_defaults(self):
        p = FilterParam(name="k", label="核大小", type=PARAM_TYPE_INT, default=5)
        self.assertEqual(p.default, 5)
        self.assertEqual(p.step, 1)

    def test_float_param_defaults(self):
        p = FilterParam(name="s", label="强度", type=PARAM_TYPE_FLOAT, default=1.0)
        self.assertEqual(p.default, 1.0)

    def test_bool_param_clears_range(self):
        p = FilterParam(name="flag", label="开关", type=PARAM_TYPE_BOOL, default=True)
        self.assertIsNone(p.minimum)
        self.assertIsNone(p.maximum)
        self.assertEqual(p.step, 1)
        self.assertTrue(p.default)

    def test_enum_param_requires_choices(self):
        with self.assertRaises(ValueError):
            FilterParam(name="m", label="模式", type=PARAM_TYPE_ENUM, default="a")

    def test_string_param_clears_range(self):
        p = FilterParam(name="t", label="文本", type=PARAM_TYPE_STRING, default="hi")
        self.assertIsNone(p.minimum)
        self.assertIsNone(p.maximum)
        self.assertEqual(p.step, 1)

    def test_unknown_type_rejected(self):
        with self.assertRaises(ValueError):
            FilterParam(name="x", label="x", type="foobar")


class FilterParamValidationTests(unittest.TestCase):
    def test_int_in_range(self):
        p = FilterParam(name="k", label="核", type=PARAM_TYPE_INT, default=5, minimum=1, maximum=11)
        ok, msg = p.validate(7)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_int_below_min(self):
        p = FilterParam(name="k", label="核", type=PARAM_TYPE_INT, default=5, minimum=1, maximum=11)
        ok, msg = p.validate(0)
        self.assertFalse(ok)
        self.assertIn("1", msg)

    def test_int_above_max(self):
        p = FilterParam(name="k", label="核", type=PARAM_TYPE_INT, default=5, minimum=1, maximum=11)
        ok, msg = p.validate(200)
        self.assertFalse(ok)
        self.assertIn("11", msg)

    def test_int_coerced_from_float(self):
        p = FilterParam(name="k", label="核", type=PARAM_TYPE_INT, default=5, minimum=1, maximum=11)
        ok, _ = p.validate(7.9)
        self.assertTrue(ok)

    def test_float_in_range(self):
        p = FilterParam(name="s", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=0.0, maximum=3.0)
        ok, _ = p.validate(2.5)
        self.assertTrue(ok)

    def test_float_out_of_range(self):
        p = FilterParam(name="s", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=0.0, maximum=3.0)
        ok, msg = p.validate(-1.0)
        self.assertFalse(ok)
        self.assertIn("0", msg)

    def test_enum_valid(self):
        p = FilterParam(name="m", label="模式", type=PARAM_TYPE_ENUM, default="a", choices=["a", "b", "c"])
        ok, _ = p.validate("b")
        self.assertTrue(ok)

    def test_enum_invalid(self):
        p = FilterParam(name="m", label="模式", type=PARAM_TYPE_ENUM, default="a", choices=["a", "b", "c"])
        ok, msg = p.validate("x")
        self.assertFalse(ok)
        self.assertIn("must be one of", msg)

    def test_enum_dict_choices(self):
        p = FilterParam(name="m", label="模式", type=PARAM_TYPE_ENUM, default="fast",
                        choices={"fast": 0, "slow": 1})
        ok, _ = p.validate("fast")
        self.assertTrue(ok)
        ok2, _ = p.validate("slow")
        self.assertTrue(ok2)
        ok3, _ = p.validate("??")
        self.assertFalse(ok3)

    def test_color_tuple_valid(self):
        p = FilterParam(name="c", label="颜色", type=PARAM_TYPE_COLOR, default=(255, 0, 0))
        ok, _ = p.validate((10, 20, 30))
        self.assertTrue(ok)

    def test_color_tuple_out_of_range(self):
        p = FilterParam(name="c", label="颜色", type=PARAM_TYPE_COLOR, default=(255, 0, 0))
        ok, _ = p.validate((300, 20, 30))
        self.assertFalse(ok)

    def test_color_hex_valid(self):
        p = FilterParam(name="c", label="颜色", type=PARAM_TYPE_COLOR, default=(255, 0, 0))
        ok, _ = p.validate("#ffaa00")
        self.assertTrue(ok)

    def test_color_short_hex(self):
        p = FilterParam(name="c", label="颜色", type=PARAM_TYPE_COLOR, default=(255, 0, 0))
        ok, _ = p.validate("#f00")
        self.assertTrue(ok)

    def test_color_invalid(self):
        p = FilterParam(name="c", label="颜色", type=PARAM_TYPE_COLOR, default=(255, 0, 0))
        ok, _ = p.validate("red")
        self.assertFalse(ok)

    def test_bool_accepts_bool(self):
        p = FilterParam(name="f", label="flag", type=PARAM_TYPE_BOOL, default=False)
        ok, _ = p.validate(True)
        self.assertTrue(ok)

    def test_string_requires_string(self):
        p = FilterParam(name="t", label="文本", type=PARAM_TYPE_STRING, default="x")
        ok, _ = p.validate("hello")
        self.assertTrue(ok)
        ok2, _ = p.validate(123)
        self.assertFalse(ok2)


class FilterCategoryGuessTests(unittest.TestCase):
    def test_blur(self):
        self.assertEqual(_guess_category("gaussian_blur", "高斯模糊"), FilterCategory.BLUR)

    def test_color(self):
        self.assertEqual(_guess_category("sepia", "复古棕"), FilterCategory.COLOR)

    def test_noise(self):
        self.assertEqual(_guess_category("noise", "噪声"), FilterCategory.NOISE)

    def test_edge(self):
        self.assertEqual(_guess_category("sketch", "素描"), FilterCategory.EDGE)

    def test_sharpen(self):
        self.assertEqual(_guess_category("sharpen_simple", "锐化"), FilterCategory.SHARPEN)

    def test_distortion(self):
        self.assertEqual(_guess_category("bulge", "鼓胀"), FilterCategory.DISTORTION)

    def test_other_fallback(self):
        self.assertEqual(_guess_category("xyz_whatsit", "什么都不是"), FilterCategory.OTHER)


class FilterDefTests(unittest.TestCase):
    def setUp(self):
        self.img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        self.reg = FilterDefRegistry.instance()

    def tearDown(self):
        pass

    def test_create_minimal(self):
        d = FilterDef(key="t1", display_name="测试", processor=_dummy)
        self.assertEqual(d.key, "t1")
        self.assertEqual(d.display_name, "测试")
        self.assertEqual(d.category, FilterCategory.OTHER)
        self.assertEqual(d.params, [])

    def test_default_params(self):
        d = FilterDef(
            key="t2", display_name="测试2", processor=_dummy,
            params=[
                FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=0.5),
                FilterParam(name="threshold", label="阈值", type=PARAM_TYPE_INT, default=100),
            ],
        )
        self.assertEqual(d.default_params(), {"strength": 0.5, "threshold": 100})

    def test_validate_params_ok(self):
        d = FilterDef(
            key="t3", display_name="测试3", processor=_dummy,
            params=[
                FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT,
                            default=1.0, minimum=0.0, maximum=3.0),
            ],
        )
        ok, errs, merged = d.validate_params({"strength": 2.5})
        self.assertTrue(ok)
        self.assertEqual(errs, [])
        self.assertEqual(merged["strength"], 2.5)

    def test_validate_params_merges_defaults(self):
        d = FilterDef(
            key="t4", display_name="测试4", processor=_dummy,
            params=[
                FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT,
                            default=1.0, minimum=0.0, maximum=3.0),
                FilterParam(name="threshold", label="阈值", type=PARAM_TYPE_INT,
                            default=128, minimum=0, maximum=255),
            ],
        )
        ok, errs, merged = d.validate_params({"strength": 0.5})
        self.assertTrue(ok)
        self.assertEqual(merged["threshold"], 128)
        self.assertEqual(merged["strength"], 0.5)

    def test_validate_params_rejects_invalid(self):
        d = FilterDef(
            key="t5", display_name="测试5", processor=_dummy,
            params=[
                FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT,
                            default=1.0, minimum=0.0, maximum=3.0),
            ],
        )
        ok, errs, _ = d.validate_params({"strength": 10.0})
        self.assertFalse(ok)
        self.assertTrue(any("强度" in e for e in errs))

    def test_apply_defaults(self):
        def p(img, strength=1.0):
            return (img.astype(float) * strength).clip(0, 255).astype(np.uint8)

        d = FilterDef(
            key="t6", display_name="测试6", processor=p,
            params=[FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT,
                                default=1.0, minimum=0.0, maximum=3.0)],
        )
        result = d.apply(self.img.copy())
        self.assertEqual(result.shape, self.img.shape)

    def test_apply_with_params(self):
        def p(img, strength=1.0):
            return (img.astype(float) * strength).clip(0, 255).astype(np.uint8)

        d = FilterDef(
            key="t7", display_name="测试7", processor=p,
            params=[FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT,
                                default=1.0, minimum=0.0, maximum=3.0)],
        )
        result = d.apply(self.img.copy(), {"strength": 2.0})
        self.assertEqual(result.shape, self.img.shape)

    def test_apply_rejects_invalid_params(self):
        def p(img, strength=1.0):
            return img

        d = FilterDef(
            key="t8", display_name="测试8", processor=p,
            params=[FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT,
                                default=1.0, minimum=0.0, maximum=3.0)],
        )
        with self.assertRaises(ValueError):
            d.apply(self.img.copy(), {"strength": 99.0})

    def test_param_lookup(self):
        d = FilterDef(
            key="t9", display_name="测试9", processor=_dummy,
            params=[
                FilterParam(name="a", label="A", type=PARAM_TYPE_FLOAT, default=0.5),
                FilterParam(name="b", label="B", type=PARAM_TYPE_INT, default=10),
            ],
        )
        self.assertIsNotNone(d.param("a"))
        self.assertIsNotNone(d.param("b"))
        self.assertIsNone(d.param("nonexistent"))


class FilterDefRegistryTests(unittest.TestCase):
    def setUp(self):
        self.reg = FilterDefRegistry.instance()
        # The registry is a process-wide singleton: snapshot it so the fixtures
        # registered below (reg1/reg2/cat_*) do not leak into other test modules.
        self._keys_before = set(self.reg.keys())

    def tearDown(self):
        for key in set(self.reg.keys()) - self._keys_before:
            self.reg.unregister(key)

    def test_singleton(self):
        self.assertIs(FilterDefRegistry.instance(), FilterDefRegistry.instance())

    def test_register_and_get(self):
        d = FilterDef(key="reg1", display_name="R1", processor=_dummy)
        self.reg.register(d)
        self.assertIs(self.reg.get("reg1"), d)
        self.assertTrue(self.reg.has("reg1"))
        self.assertIn("reg1", self.reg)
        self.assertGreaterEqual(len(self.reg), 1)

    def test_register_filter_helper(self):
        d = register_filter(key="reg2", display_name="R2", processor=_dummy,
                            category=FilterCategory.BLUR,
                            params=[FilterParam(name="k", label="K", type=PARAM_TYPE_INT, default=3)])
        self.assertIs(self.reg.get("reg2"), d)
        self.assertEqual(d.category, FilterCategory.BLUR)

    def test_by_category(self):
        initial_blur = len(self.reg.by_category().get(FilterCategory.BLUR, []))
        initial_color = len(self.reg.by_category().get(FilterCategory.COLOR, []))
        self.reg.register(FilterDef(key="cat_a", display_name="A", processor=_dummy, category=FilterCategory.BLUR))
        self.reg.register(FilterDef(key="cat_b", display_name="B", processor=_dummy, category=FilterCategory.BLUR))
        self.reg.register(FilterDef(key="cat_c", display_name="C", processor=_dummy, category=FilterCategory.COLOR))
        grouped = self.reg.by_category()
        self.assertEqual(len(grouped.get(FilterCategory.BLUR, [])), initial_blur + 2)
        self.assertEqual(len(grouped.get(FilterCategory.COLOR, [])), initial_color + 1)


class ALL_FILTERSCompatTests(unittest.TestCase):
    def test_all_filters_still_populated(self):
        from processors import filters as f
        self.assertGreater(len(f.ALL_FILTERS), 100, "ALL_FILTERS should have 100+ entries")

    def test_apply_filter_still_works(self):
        from processors import filters as f
        img = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
        r = f.apply_filter("vintage", img.copy())
        self.assertEqual(r.shape, img.shape)

    def test_apply_filter_with_params_through_compat(self):
        from processors import filters as f
        img = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
        r = f.apply_filter("gaussian_blur", img.copy(), ksize=5, sigma=1.0)
        self.assertEqual(r.shape, img.shape)


class CuratedFilterTests(unittest.TestCase):
    def setUp(self):
        self.reg = FilterDefRegistry.instance()
        self.img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)

    def _check(self, key, expected_min_params=1):
        d = self.reg.get(key)
        self.assertIsNotNone(d, f"FilterDef for '{key}' should exist")
        self.assertIsNotNone(d.processor)
        self.assertGreaterEqual(len(d.params), expected_min_params,
                                f"'{key}' should have >= {expected_min_params} params, got {len(d.params)}")
        result = d.apply(self.img.copy())
        self.assertEqual(result.shape, self.img.shape,
                         f"'{key}' apply should preserve shape")
        return d

    def test_gaussian_blur(self):
        d = self._check("gaussian_blur", 2)
        self.assertIsNotNone(d.param("ksize"))
        self.assertIsNotNone(d.param("sigma"))

    def test_noise(self):
        d = self._check("noise", 1)
        self.assertEqual(d.category, FilterCategory.NOISE)

    def test_pixelate(self):
        d = self._check("pixelate", 1)

    def test_sharpen_simple(self):
        d = self._check("sharpen_simple", 1)

    def test_solarize(self):
        d = self._check("solarize", 1)

    def test_black_and_white(self):
        d = self._check("black_and_white", 1)

    def test_exposure_linear(self):
        d = self._check("exposure_linear", 1)

    def test_glitch(self):
        d = self._check("glitch", 1)

    def test_bloom(self):
        d = self._check("bloom", 2)

    def test_sepia(self):
        d = self._check("sepia", 1)

    def test_false_color_enum(self):
        d = self._check("false_color", 1)
        p = d.param("colormap")
        self.assertEqual(p.type, PARAM_TYPE_ENUM)
        ok, _ = p.validate("jet")
        self.assertTrue(ok)
        ok2, _ = p.validate("invalid_colormap")
        self.assertFalse(ok2)

    def test_threshold_rejected_at_validation_level(self):
        d = self.reg.get("gaussian_blur")
        ok, errs, _ = d.validate_params({"ksize": 500})
        self.assertFalse(ok)
        self.assertTrue(any("核大小" in e for e in errs))

    def test_batch_style_apply(self):
        d = self.reg.get("gaussian_blur")
        result = d.apply(self.img, {"ksize": 7, "sigma": 3.0})
        self.assertEqual(result.shape, self.img.shape)


class LegacyAutoMigrationTests(unittest.TestCase):
    def test_legacy_functions_registered(self):
        self.reg = FilterDefRegistry.instance()
        from processors import filters as f
        for key, (zh, _fn) in f.ALL_FILTERS.items():
            self.assertTrue(self.reg.has(key), f"Legacy filter '{key}' should be auto-migrated to FilterDefRegistry")

    def test_vintage_has_no_params(self):
        self.reg = FilterDefRegistry.instance()
        d = self.reg.get("vintage")
        self.assertIsNotNone(d)
        self.assertEqual(len(d.params), 0, "vintage has no native params; should be 0")


class FilterDefMetaTests(unittest.TestCase):
    def test_batch_supported_default_true(self):
        d = FilterDef(key="m1", display_name="M1", processor=_dummy)
        self.assertTrue(d.batch_supported)

    def test_preview_supported_default_true(self):
        d = FilterDef(key="m2", display_name="M2", processor=_dummy)
        self.assertTrue(d.preview_supported)

    def test_category_labels_exist(self):
        from processors.filter_defs import CATEGORY_LABELS
        for cat in FilterCategory:
            self.assertIn(cat, CATEGORY_LABELS)


class UILayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_widget_creates_controls_for_int(self):
        from app.widgets.filter_parameter_widget import FilterParameterWidget
        self.reg = FilterDefRegistry.instance()
        d = self.reg.get("gaussian_blur")
        w = FilterParameterWidget(d)
        self.assertIsNotNone(w.filter_def())
        self.assertEqual(w.filter_def().key, "gaussian_blur")
        params = w.current_params()
        self.assertIn("ksize", params)
        self.assertIn("sigma", params)
        self.assertIsInstance(params["ksize"], int)
        self.assertIsInstance(params["sigma"], float)

    def test_widget_resets_to_defaults(self):
        from app.widgets.filter_parameter_widget import FilterParameterWidget
        self.reg = FilterDefRegistry.instance()
        d = self.reg.get("noise")
        w = FilterParameterWidget(d)
        w.reset_to_defaults()
        params = w.current_params()
        self.assertAlmostEqual(params["std"], 20.0, places=3)

    def test_widget_handles_no_params(self):
        from app.widgets.filter_parameter_widget import FilterParameterWidget
        self.reg = FilterDefRegistry.instance()
        d = self.reg.get("vintage")
        w = FilterParameterWidget(d)
        self.assertEqual(w.current_params(), {})

    def test_widget_handles_none_filter(self):
        from app.widgets.filter_parameter_widget import FilterParameterWidget
        w = FilterParameterWidget(None)
        self.assertIsNone(w.filter_def())
        self.assertEqual(w.current_params(), {})

    def test_widget_handles_enum_param(self):
        from app.widgets.filter_parameter_widget import FilterParameterWidget
        self.reg = FilterDefRegistry.instance()
        d = self.reg.get("false_color")
        w = FilterParameterWidget(d)
        params = w.current_params()
        self.assertIn("colormap", params)

    def test_execute_via_widget_and_filterdef(self):
        from app.widgets.filter_parameter_widget import FilterParameterWidget
        self.reg = FilterDefRegistry.instance()
        d = self.reg.get("gaussian_blur")
        w = FilterParameterWidget(d)
        params = w.current_params()
        self.img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        result = d.apply(self.img.copy(), params)
        self.assertEqual(result.shape, self.img.shape)
        self.assertIsInstance(result, np.ndarray)


if __name__ == "__main__":
    unittest.main()
