from __future__ import annotations

import unittest

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.fonts import apply


class FontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_apply_uses_qt6_style_and_hinting_apis(self):
        settings = QSettings("ToolboxTest", "Fonts")
        info = apply(self.app, settings)
        self.assertIn("family", info)
        self.assertGreater(info["size"], 0)
        self.assertTrue(self.app.font().family())


if __name__ == "__main__":
    unittest.main()
