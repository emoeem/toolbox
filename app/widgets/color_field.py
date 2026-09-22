from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget,QPushButton,QHBoxLayout,QColorDialog
class ColorField(QWidget):
    colorChanged=Signal(QColor)
    def __init__(self,label='Color',color='#ffffff',alpha=True,parent=None):
        super().__init__(parent); self.alpha=alpha; self.button=QPushButton(); self.layout=QHBoxLayout(self); self.layout.setContentsMargins(0,0,0,0); self.layout.addWidget(self.button); self.button.clicked.connect(self._choose); self.setColor(color)
    def setColor(self,color): self._color=QColor(color); self._paint()
    def color(self): return QColor(self._color)
    def _paint(self): self.button.setText(self._color.name(QColor.HexArgb) if self.alpha else self._color.name()); self.button.setStyleSheet(f'QPushButton{{background:{self._color.name(QColor.HexArgb)};}}')
    def _choose(self):
        c=QColorDialog.getColor(self._color,self,'选择颜色',QColorDialog.ShowAlphaChannel if self.alpha else QColorDialog.ColorDialogOption(0))
        if c.isValid(): self.setColor(c); self.colorChanged.emit(c)
