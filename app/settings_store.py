from __future__ import annotations

from PySide6.QtCore import QSettings


class DesktopSettings:
    """Small persistence boundary for desktop-wide QSettings state."""

    ORGANIZATION = "Emo"
    APPLICATION = "Toolbox"

    def __init__(self) -> None:
        self._settings = QSettings(self.ORGANIZATION, self.APPLICATION)

    def value(self, key: str, default=None, **kwargs):
        return self._settings.value(key, default, **kwargs)

    def setValue(self, key: str, value) -> None:
        self._settings.setValue(key, value)

    def remove(self, key: str) -> None:
        self._settings.remove(key)

    def sync(self) -> None:
        self._settings.sync()
