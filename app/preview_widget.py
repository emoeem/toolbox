from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap, QWheelEvent, QMouseEvent, QKeyEvent, QDragEnterEvent, QDropEvent, QColor
from PySide6.QtWidgets import QWidget


class ImagePreview(QWidget):
    imageChanged = Signal()
    mouseMoved = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image: np.ndarray | None = None
        self._original: np.ndarray | None = None
        self._pixmap: QPixmap | None = None
        self._scale: float = 1.0
        self._offset: QPoint = QPoint(0, 0)
        self._dragging: bool = False
        self._drag_start: QPoint = QPoint(0, 0)
        self._fit_mode: bool = True
        self._zoom_anim: float = 0.0
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAcceptDrops(True)

    def set_image(self, arr: np.ndarray) -> None:
        self._image = arr.copy()
        self._original = arr.copy()
        self._pixmap = self._numpy_to_pixmap(arr)
        self._fit_mode = True
        self._scale = 1.0
        self._offset = QPoint(0, 0)
        self.imageChanged.emit()
        self.update()

    def update_current(self, arr: np.ndarray) -> None:
        self._image = arr.copy()
        self._pixmap = self._numpy_to_pixmap(arr)
        self.update()

    def reset_to_original(self) -> None:
        if self._original is not None:
            self.set_image(self._original)

    def current_image(self) -> np.ndarray | None:
        return self._image

    def fit_image(self) -> None:
        if self._pixmap is None:
            return
        pw, ph = self._pixmap.width(), self._pixmap.height()
        vw, vh = self.width(), self.height()
        if pw == 0 or ph == 0:
            return
        self._scale = min(vw / pw, vh / ph) * 0.95
        self._offset = QPoint(int((vw - pw * self._scale) / 2), int((vh - ph * self._scale) / 2))
        self._fit_mode = True
        self.update()

    def actual_size(self) -> None:
        self._scale = 1.0
        if self._pixmap:
            vw, vh = self.width(), self.height()
            self._offset = QPoint(int((vw - self._pixmap.width()) / 2), int((vh - self._pixmap.height()) / 2))
        self._fit_mode = False
        self.update()

    def zoom_in(self) -> None:
        self._zoom_by(1.25)

    def zoom_out(self) -> None:
        self._zoom_by(0.8)

    def _zoom_by(self, factor: float, center: QPoint | None = None) -> None:
        if self._pixmap is None:
            return
        old_scale = self._scale
        self._scale = max(0.05, min(32.0, self._scale * factor))
        center = center or QPoint(self.width() // 2, self.height() // 2)
        dx = (center.x() - self._offset.x()) / old_scale
        dy = (center.y() - self._offset.y()) / old_scale
        self._offset = QPoint(int(center.x() - dx * self._scale), int(center.y() - dy * self._scale))
        self._fit_mode = False
        self.update()

    def scale_value(self) -> float:
        return self._scale

    def _numpy_to_pixmap(self, arr: np.ndarray) -> QPixmap:
        if arr.ndim == 2:
            h, w = arr.shape
            qimg = QImage(arr.data, w, h, w, QImage.Format_Grayscale8)
        elif arr.shape[2] == 4:
            h, w = arr.shape[:2]
            qimg = QImage(arr.data, w, h, w * 4, QImage.Format_RGBA8888)
        else:
            h, w = arr.shape[:2]
            qimg = QImage(arr.data, w, h, w * 3, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg.copy())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#11111b"))
        if self._pixmap is None:
            painter.setPen(QColor("#a6adc8"))
            painter.drawText(self.rect(), Qt.AlignCenter, "将图片拖到这里\\n或使用 Ctrl+O 打开文件")
            return
        if self._fit_mode and abs(self._scale - 1.0) < 0.001:
            self.fit_image()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.Antialiasing)
        target_rect = QRect(self._offset, self._pixmap.size() * self._scale)
        painter.drawPixmap(target_rect, self._pixmap)

    def _dark_background(self) -> bool:
        return self._image is not None and self._image.mean() > 128

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self._zoom_by(factor, event.position().toPoint())
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = event.position().toPoint() - self._offset
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._dragging:
            self._offset = pos - self._drag_start
            self.update()
        if self._pixmap:
            pw, ph = self._pixmap.width(), self._pixmap.height()
            img_x = int((pos.x() - self._offset.x()) / self._scale)
            img_y = int((pos.y() - self._offset.y()) / self._scale)
            if 0 <= img_x < pw and 0 <= img_y < ph:
                self.mouseMoved.emit(img_x, img_y)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self.setCursor(Qt.OpenHandCursor)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            self.zoom_in()
        elif event.key() == Qt.Key_Minus:
            self.zoom_out()
        elif event.key() == Qt.Key_0:
            self.fit_image()
        elif event.key() == Qt.Key_1:
            self.actual_size()
        elif event.key() == Qt.Key_Escape:
            self.reset_to_original()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit_mode:
            self.fit_image()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        from .main_window import MainWindow
        mw = self.window()
        if isinstance(mw, MainWindow):
            for url in event.mimeData().urls():
                p = url.toLocalFile()
                if p:
                    mw.load_file(p)
                    break
