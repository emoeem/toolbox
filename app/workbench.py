from __future__ import annotations

from time import monotonic
from typing import Callable
from threading import Event

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot, Qt
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
        self.cancel_event = Event()
        self.pause_event = Event(); self.pause_event.set()
        self.setAutoDelete(True)

    def _progress(self, value: int):
        while not self.pause_event.is_set() and not self.cancel_event.is_set():
            self.cancel_event.wait(0.05)
        if self.cancel_event.is_set():
            raise RuntimeError("任务已取消")
        self.signals.progress.emit(int(value))

    def pause(self): self.pause_event.clear()
    def resume(self): self.pause_event.set()
    def cancel(self): self.cancel_event.set(); self.pause_event.set()

    @Slot()
    def run(self):
        started = monotonic()
        try:
            result = self.fn(self._progress)
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
        self.items = QListWidget(); self._tasks = {}
        self.add_button = QPushButton("添加测试任务"); self.clear_button = QPushButton("清空已完成")
        self.add_button.clicked.connect(lambda: self.enqueue("测试任务", self._demo))
        self.clear_button.clicked.connect(self._clear_done)
        controls=QHBoxLayout(); controls.addWidget(self.add_button); controls.addWidget(self.clear_button)
        layout=QVBoxLayout(self); layout.addLayout(controls); layout.addWidget(self.items)

    def _demo(self, progress):
        import time
        for i in range(101): time.sleep(0.01); progress(i)

    def enqueue(self, name: str, fn: Callable[[Callable[[int], None]], object]):
        task=Task(name,fn); row=QWidget(); lay=QHBoxLayout(row); lay.setContentsMargins(6,4,6,4)
        label=QLabel(name); bar=QProgressBar(); bar.setRange(0,100); bar.setValue(0); pause=QPushButton("暂停"); cancel=QPushButton("取消")
        lay.addWidget(label,1); lay.addWidget(bar,2); lay.addWidget(pause); lay.addWidget(cancel)
        item=QListWidgetItem(); item.setSizeHint(row.sizeHint()); self.items.addItem(item); self.items.setItemWidget(item,row)
        self._tasks[id(task)]=(task,item,label,pause,cancel,fn,name)
        def toggle():
            if pause.text()=="暂停": task.pause(); pause.setText("继续")
            else: task.resume(); pause.setText("暂停")
        pause.clicked.connect(toggle); cancel.clicked.connect(task.cancel)
        task.signals.progress.connect(bar.setValue)
        task.signals.status.connect(lambda text: label.setText(f"{name} · {text}"))
        task.signals.failed.connect(lambda err: label.setText(f"{name} · 失败: {err}"))
        task.signals.finished.connect(lambda _result: (pause.setEnabled(False),cancel.setEnabled(False)))
        self.pool.start(task); return task

    def _clear_done(self):
        for row in range(self.items.count()-1,-1,-1):
            item=self.items.item(row); widget=self.items.itemWidget(item)
            label=widget.findChild(QLabel) if widget else None
            if label and any(x in label.text() for x in ("完成","失败","取消")):
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
    dock.setAllowedAreas(Qt.AllDockWidgetAreas)
    return dock
