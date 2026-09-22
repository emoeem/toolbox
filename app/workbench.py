from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtWidgets import QDockWidget, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QProgressBar, QVBoxLayout, QWidget


class TaskSignals(QObject):
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(object)
    failed = Signal(str)


class Task(QRunnable):
    def __init__(self, name: str, fn: Callable[[Callable[[int], None]], object]):
        super().__init__()
        self.name = name
        self.fn = fn
        self.signals = TaskSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        started = monotonic()
        try:
            result = self.fn(self.signals.progress.emit)
            self.signals.finished.emit(result)
            self.signals.status.emit(f"完成 · {monotonic() - started:.1f}s")
        except Exception as exc:
            self.signals.failed.emit(str(exc))
            self.signals.status.emit(f"失败 · {monotonic() - started:.1f}s")


class TaskQueueWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(max(1, min(4, self.pool.maxThreadCount())))
        self.items = QListWidget()
        self.add_button = QPushButton("添加示例任务")
        self.clear_button = QPushButton("清空已完成")
        self.add_button.clicked.connect(lambda: self.enqueue("测试任务", lambda p: self._demo(p)))
        self.clear_button.clicked.connect(self._clear_done)
        controls = QHBoxLayout(); controls.addWidget(self.add_button); controls.addWidget(self.clear_button)
        layout = QVBoxLayout(self); layout.addLayout(controls); layout.addWidget(self.items)

    def _demo(self, progress):
        import time
        for i in range(101):
            time.sleep(0.01); progress(i)
        return None

    def enqueue(self, name: str, fn: Callable[[Callable[[int], None]], object]):
        item = QListWidgetItem(name); bar = QProgressBar(); bar.setRange(0, 100); bar.setValue(0)
        self.items.addItem(item); self.items.setItemWidget(item, bar)
        task = Task(name, fn)
        task.signals.progress.connect(bar.setValue)
        task.signals.status.connect(lambda text, it=item: it.setText(f"{name} · {text}"))
        task.signals.failed.connect(lambda err, it=item: it.setText(f"{name} · 失败: {err}"))
        self.pool.start(task)
        return task

    def _clear_done(self):
        for row in range(self.items.count() - 1, -1, -1):
            text = self.items.item(row).text()
            if "完成" in text or "失败" in text:
                self.items.takeItem(row)


class LogWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editor = QPlainTextEdit(); self.editor.setReadOnly(True)
        self.filter = QLabel("运行日志")
        clear = QPushButton("清空"); clear.clicked.connect(self.editor.clear)
        top = QHBoxLayout(); top.addWidget(self.filter); top.addStretch(); top.addWidget(clear)
        layout = QVBoxLayout(self); layout.addLayout(top); layout.addWidget(self.editor)

    def log(self, message: str):
        self.editor.appendPlainText(message)


def make_dock(title: str, widget: QWidget, parent: QWidget) -> QDockWidget:
    dock = QDockWidget(title, parent)
    dock.setObjectName(title.replace(" ", "_") + "Dock")
    dock.setWidget(widget)
    dock.setAllowedAreas(0xF)
    return dock
