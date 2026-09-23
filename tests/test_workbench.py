import json
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.workbench import LogWidget, Task
from processors.cancellation import CancelToken, CancelledError


class TestLogWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_cancel_token_stops_processor_before_output(self):
        token=CancelToken(); token.cancel()
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"fractal.png"
            from processors import parity
            with self.assertRaises(CancelledError):
                parity.generate_fractal(str(out),512,512,80,cancel_token=token)
            self.assertFalse(out.exists())

    def test_task_reports_cancelled_state(self):
        seen=[]
        def work(progress, token):
            token.raise_if_cancelled()
        task=Task("cancel",work)
        task.signals.cancelled.connect(lambda: seen.append(True))
        task.cancel()
        task.run()
        self.assertEqual(seen,[True])

    def test_filter_clear_and_export(self):
        w = LogWidget()
        w.log("INFO alpha")
        w.log("ERROR beta")
        w.log("INFO gamma")
        w.filter_input.setText("alpha")
        self.assertEqual(w.filtered_messages(), ["INFO alpha"])
        w.filter_input.clear()
        w.level_filter.setText("ERROR")
        self.assertEqual(w.filtered_messages(), ["ERROR beta"])
        with tempfile.TemporaryDirectory() as td:
            txt = w.export("txt", str(Path(td) / "log.txt"))
            data = w.export("json", str(Path(td) / "log.json"))
            self.assertIn("ERROR beta", Path(txt).read_text())
            self.assertEqual(json.loads(Path(data).read_text()), ["INFO alpha", "ERROR beta", "INFO gamma"])
        w.clear()
        self.assertEqual(w.filtered_messages(), [])
        w.close()
