"""Regression tests for task-bookkeeping and undo/history bookkeeping.

Covers two bugs found by code review:
  * failed tasks were never released from Task._all_tasks, pinning the
    full-resolution images their closures captured;
  * `_push_history` snapshotted the *new* image, so Undo was a no-op once a
    filter/adjustment had been applied.
"""
import os
import tempfile
import time
import unittest

import numpy as np
from PySide6.QtWidgets import QApplication

from app.workbench import LogWidget, Task, TaskQueueWidget


def _pump(app, seconds=3.0, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)
        if until is not None and until():
            return True
    return until is None


class TestTaskCleanup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        Task._all_tasks.clear()

    def test_failed_tasks_are_released(self):
        q = TaskQueueWidget()
        payload = np.zeros((256, 256, 3), np.uint8)

        def boom(progress):
            progress(10)
            raise RuntimeError("simulated failure")

        def ok(progress):
            progress(10)
            return payload

        for i in range(4):
            q.enqueue(f"fail{i}", boom)
        for i in range(2):
            q.enqueue(f"ok{i}", ok)

        _pump(self.app, 3.0, lambda: len(Task._all_tasks) > 0 and not q.pool.activeThreadCount())
        _pump(self.app, 1.0)
        # Nothing may stay pinned: a failed task used to leak forever together
        # with the image captured by its closure.
        self.assertEqual([t.name for t in Task._all_tasks], [])
        q.shutdown(2000)

    def test_shutdown_cancels_and_drains(self):
        q = TaskQueueWidget()

        def slow(progress, token):
            for i in range(200):
                token.raise_if_cancelled()
                progress(i)
                time.sleep(0.01)
            return None

        q.enqueue("slow", slow)
        self.assertTrue(q.shutdown(5000))


class TestLogWidgetBounded(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_buffer_is_bounded_and_filter_still_works(self):
        w = LogWidget()
        for i in range(LogWidget.MAX_MESSAGES + 500):
            w.log(f"INFO line {i}")
        self.assertEqual(len(w._messages), LogWidget.MAX_MESSAGES)
        self.assertEqual(w.editor.blockCount(), LogWidget.MAX_MESSAGES)
        w.level_filter.setText("INFO")
        self.assertEqual(len(w.filtered_messages()), LogWidget.MAX_MESSAGES)
        self.assertTrue(w.editor.toPlainText().startswith("INFO line 500"))
        w.clear()
        self.assertEqual(w.editor.toPlainText(), "")
        w.close()

    def test_unfiltered_logging_appends(self):
        w = LogWidget()
        w.log("a")
        w.log("b")
        self.assertEqual(w.editor.toPlainText(), "a\nb")
        w.close()


class TestHistoryAndSaving(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        from app.main_window import MainWindow
        w = MainWindow()
        img = np.random.default_rng(0).integers(30, 230, (64, 64, 3), np.uint8)
        w.preview.set_image(img)
        w._applied_image = img.copy()
        w._current_file = None
        return w, img

    def test_undo_returns_to_the_previous_image(self):
        from processors import core as img_core
        w, img = self._window()
        w._commit_image(img_core.invert(w.preview.current_image()), "反色")
        self.assertEqual(len(w._history), 1)
        self.assertFalse(np.array_equal(w.preview.current_image(), img))
        self.assertTrue(np.array_equal(w._applied_image, w.preview.current_image()))
        w.undo()
        self.assertEqual(len(w._history), 0)
        self.assertTrue(np.array_equal(w.preview.current_image(), img))
        self.assertTrue(np.array_equal(w._applied_image, img))
        w.close()

    def test_push_history_snapshots_the_current_image(self):
        # Push must run *before* set_display; snapshotting afterwards recorded
        # the new image and made Undo a no-op.
        from processors import core as img_core
        w, img = self._window()
        w._push_history("快照")
        w.preview.set_display(img_core.invert(img))
        self.assertEqual(len(w._history), 1)
        w.undo()
        self.assertTrue(np.array_equal(w.preview.current_image(), img))
        w.close()

    def test_undo_walks_back_multiple_steps(self):
        from processors import core as img_core
        w, img = self._window()
        inverted = img_core.invert(w.preview.current_image())
        w._commit_image(inverted, "反色")
        w._commit_image(img_core.grayscale(w.preview.current_image()), "灰度")
        w.undo()
        self.assertTrue(np.array_equal(w.preview.current_image(), inverted))
        w.undo()
        self.assertTrue(np.array_equal(w.preview.current_image(), img))
        w.close()

    def test_reset_then_apply_then_undo(self):
        w, img = self._window()
        w.reset_all()
        w._build_adjust_panel()
        control = w._adjust_controls[1]  # contrast
        control["slider"].setValue(int(0.3 / control["step"]))
        w._apply_adjust_full_res()
        _pump(self.app, 10.0, lambda: not w._apply_in_progress)
        self.assertEqual(len(w._history), 1)
        w.undo()
        self.assertTrue(np.array_equal(w.preview.current_image(), img))
        w.close()

    def test_saving_after_an_apply_does_not_raise(self):
        # `self._applied_image or current` raised "truth value of an array is
        # ambiguous" as soon as anything had been applied.
        w, img = self._window()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "out.png")
            w._current_file = path
            w._applied_image = None
            w.save_file()
            self.assertTrue(os.path.exists(path))
            w._applied_image = img.copy()  # what every apply leaves behind
            w.save_file()
            self.assertTrue(os.path.exists(path))
            self.assertIsInstance(w._image_to_save(), np.ndarray)
        w.close()

    def test_history_is_bounded_by_bytes(self):
        w, _ = self._window()
        w._HISTORY_BUDGET_BYTES = 3 * 64 * 64 * 3  # room for ~3 snapshots
        for _ in range(10):
            w._push_history("x")
        self.assertLessEqual(len(w._history), 4)
        self.assertLessEqual(
            sum(a.nbytes for a, _c, _r in w._history), w._HISTORY_BUDGET_BYTES + 64 * 64 * 3)
        w.close()


if __name__ == "__main__":
    unittest.main()
