from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QSettings

from app.settings_store import DesktopSettings


class SettingsStoreTests(unittest.TestCase):
    def test_persistence_boundary_uses_expected_namespace(self):
        self.assertEqual(DesktopSettings.ORGANIZATION, "Emo")
        self.assertEqual(DesktopSettings.APPLICATION, "Toolbox")

    def test_values_round_trip_with_qsettings_backend(self):
        with tempfile.TemporaryDirectory() as td:
            QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, td)
            settings = DesktopSettings()
            settings.setValue("test/value", "ok")
            settings.sync()
            reopened = DesktopSettings()
            self.assertEqual(reopened.value("test/value"), "ok")
            reopened.remove("test/value")
            reopened.sync()
            self.assertIsNone(reopened.value("test/value", None))


if __name__ == "__main__":
    unittest.main()
