from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from processors.filter_defs import (
    FilterDef,
    FilterParam,
    PARAM_TYPE_BOOL,
    PARAM_TYPE_COLOR,
    PARAM_TYPE_ENUM,
    PARAM_TYPE_FLOAT,
    PARAM_TYPE_INT,
    PARAM_TYPE_STRING,
)
from app.widgets.labeled_slider import LabeledSlider
from app.widgets.color_field import ColorField


class FilterParameterWidget(QWidget):
    paramsChanged = Signal(dict)

    def __init__(self, filter_def: FilterDef | None = None, parent=None):
        super().__init__(parent)
        self._filter_def: FilterDef | None = None
        self._controls: dict[str, QWidget] = {}
        self._layout = QFormLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(6)
        self.set_filter_def(filter_def)

    def set_filter_def(self, filter_def: FilterDef | None) -> None:
        self._filter_def = filter_def
        self._clear()
        if filter_def is None or not filter_def.params:
            hint = QLabel("此滤镜无可调参数" if filter_def else "请选择一个滤镜")
            hint.setStyleSheet("color: gray; font-style: italic;")
            hint.setAlignment(Qt.AlignCenter)
            self._layout.addRow(hint)
            self._controls = {}
            return
        for p in filter_def.params:
            self._add_param(p)

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            else:
                sub = item.layout()
                if sub is not None:
                    while sub.count():
                        sub_item = sub.takeAt(0)
                        sub_w = sub_item.widget()
                        if sub_w is not None:
                            sub_w.setParent(None)
                            sub_w.deleteLater()

    def _add_param(self, p: FilterParam) -> None:
        if p.type == PARAM_TYPE_INT:
            ctrl = self._make_int(p)
        elif p.type == PARAM_TYPE_FLOAT:
            ctrl = self._make_float(p)
        elif p.type == PARAM_TYPE_BOOL:
            ctrl = self._make_bool(p)
        elif p.type == PARAM_TYPE_ENUM:
            ctrl = self._make_enum(p)
        elif p.type == PARAM_TYPE_COLOR:
            ctrl = self._make_color(p)
        elif p.type == PARAM_TYPE_STRING:
            ctrl = self._make_string(p)
        else:
            ctrl = QLabel(f"不支持的参数类型: {p.type}")
        self._controls[p.name] = ctrl
        label = QLabel(p.label)
        if p.description:
            label.setToolTip(p.description)
        self._layout.addRow(label, ctrl)

    def _make_int(self, p: FilterParam) -> LabeledSlider:
        lo = int(p.minimum) if p.minimum is not None else 0
        hi = int(p.maximum) if p.maximum is not None else max(255, lo + 255)
        step = int(p.step) if p.step else 1
        ctrl = LabeledSlider(
            label="",
            min_value=lo,
            max_value=hi,
            value=int(p.default),
            step=step,
            decimals=0,
        )
        ctrl.valueChanged.connect(lambda _v, n=p.name: self._on_changed(n))
        return ctrl

    def _make_float(self, p: FilterParam) -> LabeledSlider:
        lo = float(p.minimum) if p.minimum is not None else 0.0
        hi = float(p.maximum) if p.maximum is not None else max(2.0, lo + 2.0)
        step = float(p.step) if p.step else 0.01
        decimals = 2
        if step >= 1.0:
            decimals = 0
        elif step >= 0.1:
            decimals = 1
        ctrl = LabeledSlider(
            label="",
            min_value=lo,
            max_value=hi,
            value=float(p.default),
            step=step,
            decimals=decimals,
        )
        ctrl.valueChanged.connect(lambda _v, n=p.name: self._on_changed(n))
        return ctrl

    def _make_bool(self, p: FilterParam) -> QCheckBox:
        ctrl = QCheckBox()
        ctrl.setChecked(bool(p.default))
        ctrl.toggled.connect(lambda _v, n=p.name: self._on_changed(n))
        return ctrl

    def _make_enum(self, p: FilterParam) -> QComboBox:
        ctrl = QComboBox()
        if isinstance(p.choices, dict):
            for k, v in p.choices.items():
                ctrl.addItem(str(k), v)
            idx = ctrl.findText(str(p.default))
        else:
            for c in p.choices or []:
                ctrl.addItem(str(c))
            idx = ctrl.findText(str(p.default))
        if idx >= 0:
            ctrl.setCurrentIndex(idx)
        ctrl.currentIndexChanged.connect(lambda _i, n=p.name: self._on_changed(n))
        return ctrl

    def _make_color(self, p: FilterParam) -> ColorField:
        default = p.default if p.default else "#ffffff"
        if isinstance(default, (tuple, list)):
            r, g, b = default[0], default[1], default[2]
            default = f"#{int(r):02x}{int(g):02x}{int(b):02x}"
        ctrl = ColorField(color=str(default), alpha=False)
        ctrl.colorChanged.connect(lambda _c, n=p.name: self._on_changed(n))
        return ctrl

    def _make_string(self, p: FilterParam) -> QLineEdit:
        ctrl = QLineEdit(str(p.default) if p.default else "")
        ctrl.textChanged.connect(lambda _t, n=p.name: self._on_changed(n))
        return ctrl

    def _on_changed(self, _name: str) -> None:
        self.paramsChanged.emit(self.current_params())

    def current_params(self) -> dict:
        result: dict[str, object] = {}
        if self._filter_def is None:
            return result
        for p in self._filter_def.params:
            ctrl = self._controls.get(p.name)
            if ctrl is None:
                result[p.name] = p.default
                continue
            if p.type in (PARAM_TYPE_INT, PARAM_TYPE_FLOAT):
                v = ctrl.value()
                if p.type == PARAM_TYPE_INT:
                    v = int(v)
                result[p.name] = v
            elif p.type == PARAM_TYPE_BOOL:
                result[p.name] = bool(ctrl.isChecked())
            elif p.type == PARAM_TYPE_ENUM:
                data = ctrl.currentData()
                if data is not None:
                    result[p.name] = data
                else:
                    result[p.name] = ctrl.currentText()
            elif p.type == PARAM_TYPE_COLOR:
                c = ctrl.color()
                result[p.name] = (c.red(), c.green(), c.blue())
            elif p.type == PARAM_TYPE_STRING:
                result[p.name] = ctrl.text()
            else:
                result[p.name] = p.default
        return result

    def reset_to_defaults(self) -> None:
        if self._filter_def is None:
            return
        for p in self._filter_def.params:
            ctrl = self._controls.get(p.name)
            if ctrl is None:
                continue
            if p.type in (PARAM_TYPE_INT, PARAM_TYPE_FLOAT):
                ctrl.setValue(float(p.default) if p.type == PARAM_TYPE_FLOAT else int(p.default))
            elif p.type == PARAM_TYPE_BOOL:
                ctrl.setChecked(bool(p.default))
            elif p.type == PARAM_TYPE_ENUM:
                idx = ctrl.findText(str(p.default))
                if idx >= 0:
                    ctrl.setCurrentIndex(idx)
            elif p.type == PARAM_TYPE_COLOR:
                default = p.default if p.default else "#ffffff"
                if isinstance(default, (tuple, list)):
                    r, g, b = default[0], default[1], default[2]
                    default = f"#{int(r):02x}{int(g):02x}{int(b):02x}"
                ctrl.setColor(str(default))
            elif p.type == PARAM_TYPE_STRING:
                ctrl.setText(str(p.default) if p.default else "")

    def filter_def(self) -> FilterDef | None:
        return self._filter_def
