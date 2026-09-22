from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget,QHBoxLayout,QLabel,QSlider,QSpinBox,QDoubleSpinBox
class LabeledSlider(QWidget):
    valueChanged=Signal(object)
    def __init__(self,label,min_value=0,max_value=100,value=0,step=1,decimals=0,suffix='',parent=None):
        super().__init__(parent); self._decimals=decimals; self._factor=10**decimals
        lay=QHBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.addWidget(QLabel(label)); self.slider=QSlider(Qt.Horizontal); self.spin=QDoubleSpinBox() if decimals else QSpinBox()
        self.slider.setRange(round(min_value*self._factor),round(max_value*self._factor)); self.slider.setSingleStep(max(1,round(step*self._factor))); self.spin.setRange(min_value,max_value); self.spin.setSingleStep(step);
        if hasattr(self.spin,'setDecimals'): self.spin.setDecimals(decimals)
        self.spin.setSuffix(suffix); lay.addWidget(self.slider,1); lay.addWidget(self.spin)
        self.slider.valueChanged.connect(self._slider_changed); self.spin.valueChanged.connect(self._spin_changed); self.setValue(value)
    def _slider_changed(self,v):
        x=v/self._factor; self.spin.blockSignals(True); self.spin.setValue(x); self.spin.blockSignals(False); self.valueChanged.emit(x if self._decimals else int(x))
    def _spin_changed(self,v):
        self.slider.blockSignals(True); self.slider.setValue(round(float(v)*self._factor)); self.slider.blockSignals(False); self.valueChanged.emit(v if self._decimals else int(v))
    def value(self): return self.spin.value()
    def setValue(self,v): self.spin.setValue(v)
    def setRange(self,a,b): self.spin.setRange(a,b); self.slider.setRange(round(a*self._factor),round(b*self._factor))
