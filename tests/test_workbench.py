import json
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.workbench import LogWidget


class TestLogWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

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
