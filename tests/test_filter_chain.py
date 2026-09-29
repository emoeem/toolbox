from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from processors.cancellation import CancelToken, CancelledError
from processors.filter_defs import FilterDefRegistry
from processors.filter_chain import (
    FilterChain, FilterStep, FilterStepError, SCHEMA_VERSION,
)


def _fake_processor(img, strength=1.0):
    return (img.astype(np.float32) * strength).clip(0, 255).astype(np.uint8)


class FilterStepTests(unittest.TestCase):
    def setUp(self):
        self.img = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
        self.reg = FilterDefRegistry.instance()

    def test_step_create(self):
        s = FilterStep(filter_key="gaussian_blur", params={"ksize": 5})
        self.assertEqual(s.filter_key, "gaussian_blur")
        self.assertEqual(s.enabled, True)

    def test_step_unknown_def(self):
        s = FilterStep(filter_key="no_such_filter_xyz")
        self.assertIsNone(s.filter_def)
        ok, errs = s.validate()
        self.assertFalse(ok)
        self.assertTrue(any("未知" in e for e in errs))

    def test_step_clone_independent(self):
        s1 = FilterStep(filter_key="gaussian_blur", params={"ksize": 7, "sigma": 2.0})
        s2 = s1.clone()
        s2.params["ksize"] = 99
        self.assertEqual(s1.params["ksize"], 7)
        self.assertEqual(s2.params["ksize"], 99)

    def test_step_to_dict_from_dict_roundtrip(self):
        s1 = FilterStep(filter_key="gaussian_blur", params={"ksize": 7, "sigma": 1.5}, enabled=False)
        d = s1.to_dict()
        self.assertEqual(d["filter_key"], "gaussian_blur")
        self.assertEqual(d["params"]["ksize"], 7)
        self.assertEqual(d["enabled"], False)
        s2 = FilterStep.from_dict(d)
        self.assertEqual(s2.filter_key, s1.filter_key)
        self.assertEqual(s2.params, s1.params)
        self.assertEqual(s2.enabled, s1.enabled)

    def test_step_from_dict_requires_key(self):
        with self.assertRaises(ValueError):
            FilterStep.from_dict({"params": {}})

    def test_step_apply_uses_validated_params(self):
        s = FilterStep(filter_key="gaussian_blur", params={"ksize": 5, "sigma": 1.0})
        result = s.apply(self.img.copy())
        self.assertEqual(result.shape, self.img.shape)
        self.assertEqual(result.dtype, np.uint8)

    def test_step_apply_with_bad_params_fails(self):
        s = FilterStep(filter_key="gaussian_blur", params={"ksize": 999})
        with self.assertRaises(FilterStepError) as ctx:
            s.apply(self.img.copy())
        self.assertIn("验证", str(ctx.exception))

    def test_step_apply_unknown_filter_fails(self):
        s = FilterStep(filter_key="no_such_filter_xyz")
        with self.assertRaises(FilterStepError):
            s.apply(self.img.copy())


class FilterChainEmptyTests(unittest.TestCase):
    def setUp(self):
        self.img = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)

    def test_empty_chain_len_zero(self):
        c = FilterChain()
        self.assertEqual(len(c), 0)

    def test_empty_chain_iter(self):
        c = FilterChain()
        self.assertEqual(list(c), [])

    def test_empty_chain_apply_passthrough(self):
        c = FilterChain()
        result = c.apply(self.img.copy())
        np.testing.assert_array_equal(result, self.img)

    def test_empty_chain_to_dict(self):
        c = FilterChain(name="空链")
        d = c.to_dict()
        self.assertEqual(d["schema_version"], SCHEMA_VERSION)
        self.assertEqual(d["name"], "空链")
        self.assertEqual(d["steps"], [])


class FilterChainBuildTests(unittest.TestCase):
    def setUp(self):
        self.img = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)

    def test_add_single(self):
        c = FilterChain()
        step = c.add("gaussian_blur", {"ksize": 7, "sigma": 2.0})
        self.assertIsInstance(step, FilterStep)
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0].filter_key, "gaussian_blur")

    def test_add_multiple_order_preserved(self):
        c = FilterChain()
        c.add("gaussian_blur")
        c.add("sharpen_simple")
        c.add("sepia")
        keys = [s.filter_key for s in c]
        self.assertEqual(keys, ["gaussian_blur", "sharpen_simple", "sepia"])

    def test_add_unknown_filter_raises(self):
        c = FilterChain()
        with self.assertRaises(KeyError):
            c.add("no_such_filter_xyz")

    def test_add_step_uses_defaults_for_unspecified(self):
        c = FilterChain()
        c.add("gaussian_blur", {"ksize": 5})
        params = c[0].params
        self.assertEqual(params["ksize"], 5)
        self.assertIn("sigma", params)

    def test_add_step_with_no_params(self):
        c = FilterChain()
        c.add("vintage")
        self.assertEqual(c[0].filter_key, "vintage")
        self.assertEqual(c[0].enabled, True)

    def test_add_step_must_exist_in_registry(self):
        c = FilterChain()
        with self.assertRaises(KeyError):
            c.add_step(FilterStep(filter_key="definitely_not_a_filter"))

    def test_remove(self):
        c = FilterChain()
        c.add("gaussian_blur")
        c.add("sharpen_simple")
        removed = c.remove(0)
        self.assertEqual(removed.filter_key, "gaussian_blur")
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0].filter_key, "sharpen_simple")

    def test_clear(self):
        c = FilterChain()
        c.add("gaussian_blur")
        c.add("sharpen_simple")
        c.clear()
        self.assertEqual(len(c), 0)

    def test_move_up(self):
        c = FilterChain()
        c.add("gaussian_blur")
        c.add("sharpen_simple")
        c.add("sepia")
        ok = c.move_up(2)
        self.assertTrue(ok)
        self.assertEqual([s.filter_key for s in c], ["gaussian_blur", "sepia", "sharpen_simple"])

    def test_move_up_first_is_noop(self):
        c = FilterChain()
        c.add("gaussian_blur")
        ok = c.move_up(0)
        self.assertFalse(ok)

    def test_move_down(self):
        c = FilterChain()
        c.add("gaussian_blur")
        c.add("sharpen_simple")
        c.add("sepia")
        ok = c.move_down(0)
        self.assertTrue(ok)
        self.assertEqual([s.filter_key for s in c], ["sharpen_simple", "gaussian_blur", "sepia"])

    def test_move_down_last_is_noop(self):
        c = FilterChain()
        c.add("gaussian_blur")
        c.add("sharpen_simple")
        ok = c.move_down(1)
        self.assertFalse(ok)

    def test_duplicate(self):
        c = FilterChain()
        c.add("gaussian_blur", {"ksize": 7})
        dup = c.duplicate(0)
        self.assertEqual(len(c), 2)
        self.assertEqual(dup.filter_key, "gaussian_blur")
        self.assertEqual([s.params["ksize"] for s in c], [7, 7])
        dup.params["ksize"] = 21
        self.assertEqual(c[0].params["ksize"], 7)
        self.assertEqual(c[1].params["ksize"], 21)

    def test_enable_disable(self):
        c = FilterChain()
        c.add("gaussian_blur")
        c.add("sepia")
        c.disable(0)
        self.assertFalse(c[0].enabled)
        self.assertTrue(c[1].enabled)
        c.enable(0, True)
        self.assertTrue(c[0].enabled)

    def test_set_params_validated(self):
        c = FilterChain()
        c.add("gaussian_blur")
        c.set_params(0, {"ksize": 7, "sigma": 2.5})
        self.assertEqual(c[0].params["ksize"], 7)
        self.assertEqual(c[0].params["sigma"], 2.5)

    def test_set_params_rejects_invalid(self):
        c = FilterChain()
        c.add("gaussian_blur")
        with self.assertRaises(ValueError):
            c.set_params(0, {"ksize": 9999})

    def test_enabled_steps_skips_disabled(self):
        c = FilterChain()
        c.add("gaussian_blur")
        c.add("sepia")
        c.disable(0)
        enabled = [s.filter_key for s in c.enabled_steps()]
        self.assertEqual(enabled, ["sepia"])


class FilterChainValidateTests(unittest.TestCase):
    def test_all_ok(self):
        c = FilterChain()
        c.add("gaussian_blur", {"ksize": 5})
        c.add("sepia", {"strength": 0.5})
        ok, errs = c.validate_all()
        self.assertTrue(ok)
        self.assertEqual(errs, [])

    def test_unknown_filter(self):
        c = FilterChain(steps=[FilterStep(filter_key="not_a_filter")])
        ok, errs = c.validate_all()
        self.assertFalse(ok)
        self.assertTrue(any("未知" in e for e in errs))

    def test_param_out_of_range(self):
        c = FilterChain()
        c.add("gaussian_blur", {"ksize": 999})
        ok, errs = c.validate_all()
        self.assertFalse(ok)
        self.assertTrue(any("核大小" in e or "11" in e or "51" in e for e in errs))

    def test_disabled_step_not_validated(self):
        c = FilterChain()
        s = FilterStep(filter_key="not_a_filter")
        s.enabled = False
        c.steps.append(s)
        ok, errs = c.validate_all()
        self.assertTrue(ok, "disabled step should not be validated")


class FilterChainApplyTests(unittest.TestCase):
    def setUp(self):
        self.img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)

    def test_single_filter(self):
        c = FilterChain()
        c.add("gaussian_blur", {"ksize": 7, "sigma": 1.0})
        result = c.apply(self.img.copy())
        self.assertEqual(result.shape, self.img.shape)
        self.assertEqual(result.dtype, np.uint8)

    def test_multi_filter_order(self):
        c = FilterChain()
        c.add("gaussian_blur", {"ksize": 5})
        c.add("sharpen_simple", {"strength": 1.2})
        c.add("sepia", {"strength": 0.5})
        result = c.apply(self.img.copy())
        self.assertEqual(result.shape, self.img.shape)

    def test_disabled_step_skipped_in_apply(self):
        c = FilterChain()
        c.add("gaussian_blur")
        c.add("sepia")
        c.disable(0)
        result = c.apply(self.img.copy())
        self.assertEqual(result.shape, self.img.shape)

    def test_param_values_reach_processor(self):
        c = FilterChain()
        c.add("sepia", {"strength": 1.0})
        result_full = c.apply(self.img.copy())
        c2 = FilterChain()
        c2.add("sepia", {"strength": 0.0})
        result_none = c2.apply(self.img.copy())
        diff = np.abs(result_full.astype(int) - result_none.astype(int)).mean()
        self.assertGreater(diff, 2, "strength=1.0 vs 0.0 should produce meaningfully different output")

    def test_unknown_filter_raises(self):
        c = FilterChain(steps=[FilterStep(filter_key="not_a_filter")])
        with self.assertRaises(FilterStepError):
            c.apply(self.img.copy())

    def test_validation_failure_before_processor(self):
        c = FilterChain()
        c.add("gaussian_blur", {"ksize": 500})
        with self.assertRaises(FilterStepError):
            c.apply(self.img.copy())


class FilterChainCloneTests(unittest.TestCase):
    def test_clone_independent(self):
        c1 = FilterChain()
        c1.add("gaussian_blur", {"ksize": 5})
        c1.add("sepia", {"strength": 0.5})
        c2 = c1.clone()
        c2[0].params["ksize"] = 99
        c2.add("sharpen_simple")
        self.assertEqual(len(c1), 2)
        self.assertEqual(len(c2), 3)
        self.assertEqual(c1[0].params["ksize"], 5)
        self.assertEqual(c2[0].params["ksize"], 99)

    def test_clone_preserves_names(self):
        c1 = FilterChain(name="测试链")
        c1.add("gaussian_blur")
        c2 = c1.clone()
        self.assertEqual(c2.name, "测试链")


class FilterChainSerializeTests(unittest.TestCase):
    def test_to_dict(self):
        c = FilterChain(name="序列化测试")
        c.add("gaussian_blur", {"ksize": 7, "sigma": 2.0})
        d = c.to_dict()
        self.assertEqual(d["schema_version"], 1)
        self.assertEqual(d["name"], "序列化测试")
        self.assertEqual(len(d["steps"]), 1)
        self.assertEqual(d["steps"][0]["filter_key"], "gaussian_blur")
        self.assertEqual(d["steps"][0]["params"]["ksize"], 7)
        self.assertTrue(d["steps"][0]["enabled"])

    def test_from_dict_roundtrip(self):
        img = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
        c = FilterChain(name="往返")
        c.add("gaussian_blur", {"ksize": 5, "sigma": 1.0})
        c.add("sepia", {"strength": 0.7})
        d = c.to_dict()
        c2 = FilterChain.from_dict(d)
        self.assertEqual(c2.name, c.name)
        self.assertEqual(len(c2), len(c))
        for a, b in zip(c, c2):
            self.assertEqual(a.filter_key, b.filter_key)
            self.assertEqual(a.params, b.params)
            self.assertEqual(a.enabled, b.enabled)
        r1 = c.apply(img.copy())
        r2 = c2.apply(img.copy())
        np.testing.assert_array_equal(r1, r2)

    def test_from_dict_rejects_newer_version(self):
        d = {"schema_version": 999, "name": "fwd", "steps": []}
        with self.assertRaises(ValueError):
            FilterChain.from_dict(d)

    def test_to_json_from_json(self):
        img = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
        c = FilterChain(name="JSON 链")
        c.add("gaussian_blur", {"ksize": 5, "sigma": 1.0})
        js = c.to_json()
        self.assertIn("schema_version", js)
        self.assertIn("gaussian_blur", js)
        c2 = FilterChain.from_json(js)
        self.assertEqual(len(c2), len(c))
        r1 = c.apply(img.copy())
        r2 = c2.apply(img.copy())
        np.testing.assert_array_equal(r1, r2)


class FilterStepErrorTests(unittest.TestCase):
    def test_attributes(self):
        exc = FilterStepError(2, "sepia", "bad params")
        self.assertEqual(exc.step_index, 2)
        self.assertEqual(exc.filter_key, "sepia")
        self.assertIn("bad params", str(exc))


class PresetIntegrationTests(unittest.TestCase):
    def test_save_load_roundtrip(self):
        import os, tempfile
        from processors.filter_presets import _preset_store_path
        from PIL import Image as PILImage
        c = FilterChain(name="预设测试")
        c.add("gaussian_blur", {"ksize": 7, "sigma": 2.0})
        c.add("sepia", {"strength": 0.5})
        saved = __import__("processors.filter_presets", fromlist=["save_preset"]).save_preset("unit_test_chain", c, overwrite=True)
        self.assertTrue(saved)
        loaded = __import__("processors.filter_presets", fromlist=["load_preset"]).load_preset("unit_test_chain")
        self.assertEqual(loaded.name, "预设测试")
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].filter_key, "gaussian_blur")
        self.assertEqual(loaded[1].params["strength"], 0.5)
        __import__("processors.filter_presets", fromlist=["delete_preset"]).delete_preset("unit_test_chain")

    def test_preset_overwrite(self):
        from processors.filter_presets import save_preset, load_preset, delete_preset
        c1 = FilterChain(name="v1")
        c1.add("gaussian_blur")
        save_preset("ow_preset", c1, overwrite=True)
        c2 = FilterChain(name="v2")
        c2.add("sepia")
        save_preset("ow_preset", c2, overwrite=True)
        loaded = load_preset("ow_preset")
        self.assertEqual(loaded.name, "v2")
        self.assertEqual(loaded[0].filter_key, "sepia")
        delete_preset("ow_preset")

    def test_preset_no_overwrite_raises(self):
        from processors.filter_presets import save_preset, delete_preset
        c = FilterChain()
        c.add("gaussian_blur")
        save_preset("noow_preset", c, overwrite=True)
        with self.assertRaises(FileExistsError):
            save_preset("noow_preset", c, overwrite=False)
        delete_preset("noow_preset")

    def test_preset_list(self):
        from processors.filter_presets import save_preset, list_presets, delete_preset
        c = FilterChain()
        c.add("gaussian_blur")
        save_preset("lst_a", c, overwrite=True)
        save_preset("lst_b", c, overwrite=True)
        presets = list_presets()
        names = [p["name"] for p in presets]
        self.assertIn("lst_a", names)
        self.assertIn("lst_b", names)
        for n in ("lst_a", "lst_b"):
            delete_preset(n)


class BatchFilterChainTests(unittest.TestCase):
    def setUp(self):
        self.img = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
        self.chain = FilterChain()
        self.chain.add("gaussian_blur", {"ksize": 5, "sigma": 1.0})
        self.chain.add("sepia", {"strength": 0.5})

    def test_batch_succeeded(self):
        from processors.batch_filter_chain import run_batch_filter_chain
        from PIL import Image as PILImage
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "out"
            files = []
            for i in range(3):
                f = Path(td) / f"img_{i}.png"
                PILImage.fromarray(self.img).save(str(f))
                files.append(f)
            result = run_batch_filter_chain(files, self.chain, output_dir=out_dir)
            self.assertEqual(result.total, 3)
            self.assertEqual(result.succeeded, 3)
            self.assertEqual(result.failed, 0)
            self.assertEqual(result.cancelled, 0)
            for it in result.items:
                self.assertEqual(it.status.value, "succeeded")
                self.assertIsNotNone(it.output)
                self.assertTrue(Path(str(it.output)).exists())
                self.assertGreater(it.elapsed_ms, 0)

    def test_batch_cancelled(self):
        from processors.batch_filter_chain import run_batch_filter_chain
        ct = CancelToken()
        ct.cancel()
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "out"
            files = []
            for i in range(3):
                f = Path(td) / f"img_{i}.png"
                from PIL import Image as PILImage
                PILImage.fromarray(self.img).save(str(f))
                files.append(f)
            result = run_batch_filter_chain(files, self.chain, output_dir=out_dir, cancel_token=ct)
            self.assertEqual(result.cancelled, 3)
            self.assertEqual(result.succeeded, 0)

    def test_batch_one_failure_does_not_break_others(self):
        from processors.batch_filter_chain import run_batch_filter_chain
        bad_chain = FilterChain()
        bad_chain.add("gaussian_blur", {"ksize": 999})
        from PIL import Image as PILImage
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "out"
            files = []
            for i in range(3):
                f = Path(td) / f"img_{i}.png"
                PILImage.fromarray(self.img).save(str(f))
                files.append(f)
            result = run_batch_filter_chain(files, bad_chain, output_dir=out_dir)
            self.assertEqual(result.failed, 3)
            for it in result.items:
                self.assertEqual(it.status.value, "failed")
                self.assertTrue(it.error)

    def test_batch_progress_callback(self):
        from processors.batch_filter_chain import run_batch_filter_chain
        from PIL import Image as PILImage
        calls = []

        def cb(i, total, status):
            calls.append((i, total, status))

        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "out"
            files = []
            for i in range(3):
                f = Path(td) / f"img_{i}.png"
                PILImage.fromarray(self.img).save(str(f))
                files.append(f)
            run_batch_filter_chain(files, self.chain, output_dir=out_dir, progress_cb=cb)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][1], 3)
        self.assertEqual(calls[-1][0], 3)
        self.assertEqual(calls[-1][2], "succeeded")

    def test_batch_overwrite_false(self):
        from processors.batch_filter_chain import run_batch_filter_chain
        from PIL import Image as PILImage
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "out"
            files = []
            f1 = Path(td) / "img_0.png"
            PILImage.fromarray(self.img).save(str(f1))
            files.append(f1)
            out_dir.mkdir(parents=True, exist_ok=True)
            pre_existing = out_dir / "img_0.png"
            PILImage.fromarray(np.zeros((10, 10, 3), dtype=np.uint8)).save(str(pre_existing))
            result = run_batch_filter_chain(files, self.chain, output_dir=out_dir, overwrite=False)
            self.assertEqual(result.failed, 1)
            self.assertIn("overwrite", result.items[0].error.lower())

    def test_batch_invalid_file(self):
        from processors.batch_filter_chain import run_batch_filter_chain
        result = run_batch_filter_chain([Path("/tmp/definitely_not_a_real_file_xyz_12345.png")], self.chain)
        self.assertEqual(result.total, 1)
        self.assertEqual(result.failed, 1)
        self.assertTrue(result.items[0].error)


class FilterChainCancelTokenTests(unittest.TestCase):
    def test_cancel_before_apply_raises(self):
        from processors.filter_defs import FilterDef
        from processors.cancellation import CancelToken
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        defn = FilterDef(key="ct_test", display_name="CT", processor=_fake_processor)
        ct = CancelToken()
        ct.cancel()
        with self.assertRaises(CancelledError):
            defn.apply(img, cancel_token=ct)

    def test_chain_cancel_before_step_2(self):
        from processors.cancellation import CancelToken
        img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        c = FilterChain()
        c.add("gaussian_blur", {"ksize": 5})
        c.add("sepia", {"strength": 0.5})
        ct = CancelToken()
        ct.cancel()
        with self.assertRaises((FilterStepError, CancelledError)):
            c.apply(img.copy(), cancel_token=ct)


class SmokeFilterChainOrderTests(unittest.TestCase):
    def test_blur_sharpen_sepia_shape(self):
        img = np.random.randint(0, 255, (48, 48, 3), dtype=np.uint8)
        c = FilterChain()
        c.add("gaussian_blur", {"ksize": 5, "sigma": 1.0})
        c.add("sharpen_simple", {"strength": 1.0})
        c.add("sepia", {"strength": 0.8})
        result = c.apply(img.copy())
        self.assertEqual(result.shape, img.shape)
        self.assertEqual(result.dtype, np.uint8)

    def test_gaussian_blur_params_reach_processor(self):
        img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        c1 = FilterChain()
        c1.add("gaussian_blur", {"ksize": 3, "sigma": 0.5})
        c2 = FilterChain()
        c2.add("gaussian_blur", {"ksize": 21, "sigma": 5.0})
        r1 = c1.apply(img.copy())
        r2 = c2.apply(img.copy())
        diff = np.abs(r1.astype(float) - r2.astype(float)).mean()
        self.assertGreater(diff, 1, "different params should yield different images")


if __name__ == "__main__":
    unittest.main()
