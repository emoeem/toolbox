import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import numpy as np

from processors.cancellation import CancelToken, CancelledError
from processors.filter_chain import FilterChain, FilterStep, FilterStepError
from processors.filter_chain_task import (
    make_filter_chain_worker,
    run_filter_chain_sync,
    preview_cache_key,
    preview_cache_get,
    preview_cache_set,
    preview_cache_clear,
)
from processors.batch_filter_chain import run_batch_filter_chain, BatchFilterChainResult
from processors.filter_defs import FilterDefRegistry, register_filter, FilterParam, FilterCategory, PARAM_TYPE_INT, PARAM_TYPE_FLOAT


def _simple_blur(img):
    return img.copy()


def _blur_with_strength(img, strength=1.0):
    return (img * strength).clip(0, 255).astype(np.uint8)


def _boom(img):
    raise RuntimeError("boom!")


def _register_test_filters():
    reg = FilterDefRegistry.instance()
    if not reg.has("_test_blur"):
        register_filter(key="_test_blur", display_name="Test Blur", processor=_simple_blur,
                        category=FilterCategory.BLUR, params=[])
    if not reg.has("_test_strength"):
        register_filter(key="_test_strength", display_name="Test Strength", processor=_blur_with_strength,
                        category=FilterCategory.BLUR, params=[
                            FilterParam(name="strength", label="Strength", type=PARAM_TYPE_FLOAT,
                                        default=0.5, minimum=0.0, maximum=2.0, step=0.1),
                        ])
    if not reg.has("_test_boom"):
        register_filter(key="_test_boom", display_name="Test Boom", processor=_boom,
                        category=FilterCategory.STYLIZE, params=[])


_TEST_FILTER_KEYS = ("_test_blur", "_test_strength", "_test_boom")


def tearDownModule():
    """The registry is a process-wide singleton, so the fixtures registered by
    every class here must be removed once this module is done -- otherwise the
    deliberately-failing `_test_boom` leaks into other modules."""
    reg = FilterDefRegistry.instance()
    for key in _TEST_FILTER_KEYS:
        reg.unregister(key)


class TestFilterChainTask(unittest.TestCase):
    def setUp(self):
        _register_test_filters()
        self.img = (np.random.rand(64, 64, 3) * 255).astype(np.uint8)
        preview_cache_clear()

    def test_run_sync_success(self):
        chain = FilterChain()
        chain.add("_test_blur")
        out = run_filter_chain_sync(self.img, chain)
        self.assertEqual(out.shape, self.img.shape)

    def test_run_sync_with_progress(self):
        chain = FilterChain()
        chain.add("_test_strength", params={"strength": 0.8})
        chain.add("_test_blur")
        calls = []
        def prog(i, t):
            calls.append((i, t))
        out = run_filter_chain_sync(self.img, chain, progress_cb=prog)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[-1], (2, 2))
        self.assertEqual(out.shape, self.img.shape)

    def test_run_sync_cancelled(self):
        chain = FilterChain()
        chain.add("_test_strength", params={"strength": 0.5})
        chain.add("_test_blur")
        ct = CancelToken()
        cancel_after_first = [False]
        def prog(i, t):
            if i >= 1:
                cancel_after_first[0] = True
                ct.cancel()
        with self.assertRaises(CancelledError):
            run_filter_chain_sync(self.img, chain, progress_cb=prog, cancel_token=ct)

    def test_run_sync_filter_step_error(self):
        chain = FilterChain()
        chain.add("_test_strength", params={"strength": 0.5})
        chain.add("_test_boom")
        with self.assertRaises(FilterStepError) as ctx:
            run_filter_chain_sync(self.img, chain)
        self.assertEqual(ctx.exception.step_index, 1)
        self.assertEqual(ctx.exception.filter_key, "_test_boom")
        self.assertIn("boom!", str(ctx.exception))

    def test_run_sync_skips_disabled_steps(self):
        chain = FilterChain()
        chain.add("_test_strength", params={"strength": 2.0})
        chain.add("_test_blur")
        chain.disable(1)
        out = run_filter_chain_sync(self.img, chain)
        self.assertEqual(out.shape, self.img.shape)

    def test_run_sync_empty_chain(self):
        chain = FilterChain()
        out = run_filter_chain_sync(self.img, chain)
        np.testing.assert_array_equal(out, self.img)


class TestFilterChainWorker(unittest.TestCase):
    def setUp(self):
        _register_test_filters()
        self.img = (np.random.rand(64, 64, 3) * 255).astype(np.uint8)
        preview_cache_clear()

    def test_worker_success(self):
        chain = FilterChain()
        chain.add("_test_strength", params={"strength": 0.8})
        worker = make_filter_chain_worker(self.img, chain)
        ct = CancelToken()
        progress_vals = []
        out = worker(lambda v: progress_vals.append(v), ct)
        self.assertEqual(out.shape, self.img.shape)
        self.assertGreater(len(progress_vals), 0)
        self.assertTrue(progress_vals[-1] >= 99)

    def test_worker_cancel_after_progress(self):
        chain = FilterChain()
        chain.add("_test_strength", params={"strength": 0.5})
        chain.add("_test_blur")
        chain.add("_test_boom")
        ct = CancelToken()
        cancelled_flag = [False]
        def prog(v):
            if v >= 40 and not cancelled_flag[0]:
                cancelled_flag[0] = True
                ct.cancel()
        worker = make_filter_chain_worker(self.img, chain)
        with self.assertRaises(CancelledError):
            worker(prog, ct)

    def test_worker_filter_step_error(self):
        chain = FilterChain()
        chain.add("_test_boom")
        ct = CancelToken()
        worker = make_filter_chain_worker(self.img, chain)
        with self.assertRaises(FilterStepError) as ctx:
            worker(lambda v: None, ct)
        self.assertEqual(ctx.exception.filter_key, "_test_boom")

    def test_worker_uses_external_cancel_token(self):
        chain = FilterChain()
        chain.add("_test_strength", params={"strength": 0.5})
        ct = CancelToken()
        ct.cancel()
        worker = make_filter_chain_worker(self.img, chain, cancel_token=ct)
        with self.assertRaises(CancelledError):
            worker(lambda v: None, CancelToken())


class TestPreviewCache(unittest.TestCase):
    def setUp(self):
        _register_test_filters()
        self.img = (np.random.rand(64, 64, 3) * 255).astype(np.uint8)
        preview_cache_clear()

    def test_cache_key_changes_with_chain(self):
        c1 = FilterChain()
        c1.add("_test_strength", params={"strength": 0.5})
        c2 = FilterChain()
        c2.add("_test_strength", params={"strength": 0.8})
        k1 = preview_cache_key(self.img, c1)
        k2 = preview_cache_key(self.img, c2)
        self.assertNotEqual(k1, k2)

    def test_cache_key_changes_with_image(self):
        chain = FilterChain()
        chain.add("_test_blur")
        k1 = preview_cache_key(self.img, chain)
        img2 = self.img.copy()
        img2[0, 0, 0] = 255
        k2 = preview_cache_key(img2, chain)
        self.assertNotEqual(k1, k2)

    def test_cache_hit_and_miss(self):
        chain = FilterChain()
        chain.add("_test_blur")
        key = preview_cache_key(self.img, chain)
        self.assertIsNone(preview_cache_get(key))
        fake = np.zeros_like(self.img)
        preview_cache_set(key, fake)
        got = preview_cache_get(key)
        self.assertIs(got, fake)

    def test_cache_clear(self):
        chain = FilterChain()
        chain.add("_test_blur")
        key = preview_cache_key(self.img, chain)
        preview_cache_set(key, np.zeros_like(self.img))
        preview_cache_clear()
        self.assertIsNone(preview_cache_get(key))

    def test_chain_disable_changes_key(self):
        c1 = FilterChain()
        c1.add("_test_blur")
        c2 = FilterChain()
        c2.add("_test_blur")
        c2.disable(0)
        self.assertNotEqual(preview_cache_key(self.img, c1), preview_cache_key(self.img, c2))


class TestBatchFilterChainWithTaskQueue(unittest.TestCase):
    def setUp(self):
        _register_test_filters()
        self.img = (np.random.rand(64, 64, 3) * 255).astype(np.uint8)
        preview_cache_clear()

    def test_batch_success(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            paths = []
            for i in range(3):
                f = p / f"img_{i}.png"
                from processors.utils import save_image
                save_image(self.img, str(f))
                paths.append(f)
            chain = FilterChain()
            chain.add("_test_blur")
            out_dir = p / "out"
            r = run_batch_filter_chain(paths, chain, output_dir=out_dir, output_format="PNG")
            self.assertEqual(r.total, 3)
            self.assertEqual(r.succeeded, 3)
            self.assertEqual(r.failed, 0)
            self.assertTrue(out_dir.exists())

    def test_batch_with_one_failure_continues(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            paths = []
            for i in range(3):
                f = p / f"img_{i}.png"
                from processors.utils import save_image
                save_image(self.img, str(f))
                paths.append(f)
            chain = FilterChain()
            chain.add("_test_strength", params={"strength": 0.5})
            chain.add("_test_boom")
            out_dir = p / "out"
            r = run_batch_filter_chain(paths, chain, output_dir=out_dir, output_format="PNG")
            self.assertEqual(r.total, 3)
            self.assertEqual(r.failed, 3)
            for item in r.items:
                self.assertEqual(item.status.value, "failed")

    def test_batch_cancel_stops(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            paths = []
            for i in range(5):
                f = p / f"img_{i}.png"
                from processors.utils import save_image
                save_image(self.img, str(f))
                paths.append(f)
            chain = FilterChain()
            chain.add("_test_blur")
            ct = CancelToken()
            progress_calls = []
            def prog(i, t, status):
                progress_calls.append((i, t, status))
                if i >= 2:
                    ct.cancel()
            r = run_batch_filter_chain(paths, chain, cancel_token=ct, progress_cb=prog)
            self.assertEqual(r.cancelled, 3)
            self.assertEqual(r.succeeded, 2)

    def test_batch_overwrite_false(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            f = p / "img.png"
            from processors.utils import save_image
            save_image(self.img, str(f))
            chain = FilterChain()
            chain.add("_test_blur")
            out_dir = p / "out"
            run_batch_filter_chain([f], chain, output_dir=out_dir, output_format="PNG")
            r = run_batch_filter_chain([f], chain, output_dir=out_dir, output_format="PNG", overwrite=False)
            self.assertEqual(r.failed, 1)

    def test_batch_progress_cb(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            paths = []
            for i in range(3):
                f = p / f"img_{i}.png"
                from processors.utils import save_image
                save_image(self.img, str(f))
                paths.append(f)
            chain = FilterChain()
            chain.add("_test_blur")
            calls = []
            def prog(i, t, status):
                calls.append((i, t, status))
            run_batch_filter_chain(paths, chain, progress_cb=prog)
            self.assertEqual(len(calls), 3)
            self.assertEqual(calls[0][0], 1)
            self.assertEqual(calls[-1][0], 3)


if __name__ == "__main__":
    unittest.main()
