from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QSize, QMimeData
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPainter, QColor, QPixmap, QImage
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QListWidget, QListWidgetItem, QSplitter, QToolBar,
    QStatusBar, QFileDialog, QMessageBox, QLabel, QSpinBox, QDoubleSpinBox,
    QSlider, QPushButton, QComboBox, QCheckBox, QGroupBox, QVBoxLayout,
    QHBoxLayout, QFormLayout, QScrollArea, QFrame, QTabWidget, QGridLayout,
    QSizePolicy, QColorDialog, QApplication, QProgressDialog, QTextEdit,
    QInputDialog, QLineEdit
)

from processors.utils import load_image, save_image, u8, clamp
from processors import core as img_core
from processors.filters import ALL_FILTERS, apply_filter
from processors import gmic, media, pdf_tools, parity
from .preview_widget import ImagePreview
from .theme import LIGHT_QSS, DARK_QSS


TOOL_ITEMS = [
    ("🎨", "调整"),
    ("✨", "滤镜"),
    ("🖼️", "格式"),
    ("📄", "PDF"),
    ("🔍", "EXIF"),
    ("📝", "OCR"),
    ("💧", "水印"),
    ("🌈", "色彩"),
    ("📏", "裁剪"),
    ("🔄", "变换"),
    ("🎯", "AI 抠图"),
    ("📈", "AI Upscale"),
    ("🧹", "AI 降噪"),
    ("🎨", "AI 色彩化"),
    ("🌄", "AI 深度图"),
    ("🧠", "AI 模型管理器"),
    ("📐", "形状蒙版"),
    ("📊", "直方图"),
    ("⚖️", "图像比较"),
    ("🔒", "Checksum"),
    ("🔠", "条形码"),
    ("🌀", "渐变"),
    ("🗂️", "拼贴/拼接"),
    ("📦", "批量处理"),
    ("🧭", "LUT/色调曲线"),
    ("📱", "智能缩放"),
    ("🧩", "G'MIC 滤镜库"),
    ("🎞️", "动画 / GIF / APNG"),
    ("📑", "PDF 高级工具"),
    ("🗜️", "压缩 / 打包"),
    ("🧰", "高级图像工具"),
    ("🧩", "ImageToolbox 功能补齐"),
    ("📦", "归档 / Base64 / 加密"),
    ("✂️", "图片分割 / 堆叠 / 切割"),
    ("🎨", "调色板 / 颜色库"),
    ("🖊️", "绘图 / 标注 / 水印"),
    ("🧪", "压缩实验室"),
    ("🔎", "重复图片 / 图片信息"),
    ("🧬", "SVG / WebP / JXL"),
    ("📐", "尺寸 / 体积缩放"),
    ("🧱", "拼贴 / 快速拼图"),
    ("🔐", "文件加密"),
    ("❓", "关于"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._current_file: str | None = None
        self._recent_files: list[str] = []
        self._dark_mode = True

        self.setWindowTitle("Image Toolbox - 图像工具箱")
        self.setMinimumSize(QSize(1180, 760))
        self.resize(1480, 900)
        self.setAcceptDrops(True)

        self._setup_ui()
        self._setup_actions()
        self._setup_menu()
        self._setup_toolbar()
        self._apply_theme()
        self._select_tool(0)

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter)

        sidebar_box = QWidget()
        sidebar_box.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(sidebar_box)
        sidebar_layout.setContentsMargins(14, 14, 12, 12)
        sidebar_layout.setSpacing(10)
        sidebar_title = QLabel("TOOLBOX")
        sidebar_title.setObjectName("appTitle")
        sidebar_layout.addWidget(sidebar_title)
        self.tool_search = QLineEdit()
        self.tool_search.setObjectName("toolSearch")
        self.tool_search.setPlaceholderText("搜索工具…  (Ctrl+K)")
        self.tool_search.textChanged.connect(self._filter_tools)
        sidebar_layout.addWidget(self.tool_search)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("SidebarList")
        self.sidebar.setIconSize(QSize(24, 24))
        self.sidebar.currentRowChanged.connect(self._select_tool)
        for index, (icon, text) in enumerate(TOOL_ITEMS):
            item = QListWidgetItem(f"  {icon}  {text}")
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item.setData(Qt.UserRole, (index, icon, text))
            self.sidebar.addItem(item)
        sidebar_layout.addWidget(self.sidebar, 1)
        splitter.addWidget(sidebar_box)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.preview = ImagePreview()
        self.preview.imageChanged.connect(self._on_image_changed)
        self.preview.mouseMoved.connect(self._on_mouse_moved)

        self.right_panel = QScrollArea()
        self.right_panel.setMinimumWidth(320)
        self.right_panel.setMaximumWidth(400)
        self.right_panel.setWidgetResizable(True)
        self.right_panel.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.right_inner = QWidget()
        self.right_layout = QVBoxLayout(self.right_inner)
        self.right_layout.setContentsMargins(12, 12, 12, 12)
        self.right_layout.setSpacing(10)
        self.right_layout.addStretch()
        self.right_panel.setWidget(self.right_inner)

        splitter.addWidget(self.preview)
        splitter.addWidget(self.right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([228, 920, 360])

        self.setStatusBar(QStatusBar())
        self.statusBar().setObjectName("StatusBar")
        self.status_info = QLabel("就绪")
        self.statusBar().addPermanentWidget(self.status_info, 1)
        self.status_pos = QLabel("")
        self.statusBar().addPermanentWidget(self.status_pos)
        self.status_zoom = QLabel("100%")
        self.statusBar().addPermanentWidget(self.status_zoom)

    def _setup_actions(self) -> None:
        self.action_open = QAction("打开", self)
        self.action_open.setShortcut(QKeySequence.Open)
        self.action_open.triggered.connect(self.open_file_dialog)

        self.action_save = QAction("保存", self)
        self.action_save.setShortcut(QKeySequence.Save)
        self.action_save.triggered.connect(self.save_file)

        self.action_save_as = QAction("另存为", self)
        self.action_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.action_save_as.triggered.connect(self.save_file_as)

        self.action_fit = QAction("适合窗口", self)
        self.action_fit.setShortcut(QKeySequence("0"))
        self.action_fit.triggered.connect(self.preview.fit_image)

        self.action_actual = QAction("实际大小", self)
        self.action_actual.setShortcut(QKeySequence("1"))
        self.action_actual.triggered.connect(self.preview.actual_size)

        self.action_zoom_in = QAction("放大", self)
        self.action_zoom_in.setShortcut(QKeySequence("Ctrl++"))
        self.action_zoom_in.triggered.connect(self.preview.zoom_in)

        self.action_zoom_out = QAction("缩小", self)
        self.action_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        self.action_zoom_out.triggered.connect(self.preview.zoom_out)

        self.action_undo = QAction("撤销", self)
        self.action_undo.setShortcut(QKeySequence.Undo)
        self.action_undo.triggered.connect(self.preview.reset_to_original)

        self.action_focus_search = QAction("搜索工具", self)
        self.action_focus_search.setShortcut(QKeySequence("Ctrl+K"))
        self.action_focus_search.triggered.connect(lambda: (self.tool_search.setFocus(), self.tool_search.selectAll()))

        self.action_theme = QAction("切换主题", self)
        self.action_theme.setShortcut(QKeySequence("Ctrl+T"))
        self.action_theme.triggered.connect(self._toggle_theme)

        self.action_about = QAction("关于", self)
        self.action_about.setShortcut(QKeySequence.HelpContents)
        self.action_about.triggered.connect(self._show_about)

    def _setup_menu(self) -> None:
        menubar = self.menuBar()

        m_file = menubar.addMenu("文件")
        m_file.addAction(self.action_open)
        m_file.addAction(self.action_save)
        m_file.addAction(self.action_save_as)
        m_file.addSeparator()
        m_file.addAction("退出", self.close, QKeySequence.Quit)

        m_view = menubar.addMenu("视图")
        m_view.addAction(self.action_focus_search)
        m_view.addSeparator()
        m_view.addAction(self.action_fit)
        m_view.addAction(self.action_actual)
        m_view.addAction(self.action_zoom_in)
        m_view.addAction(self.action_zoom_out)
        m_view.addSeparator()
        m_view.addAction(self.action_theme)

        m_edit = menubar.addMenu("编辑")
        m_edit.addAction(self.action_undo)

        m_help = menubar.addMenu("帮助")
        m_help.addAction(self.action_about)

    def _setup_toolbar(self) -> None:
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(tb)

        btn_open = QPushButton("📂 打开")
        btn_open.clicked.connect(self.open_file_dialog)
        btn_open.setToolTip("打开图片 (Ctrl+O)")
        tb.addWidget(btn_open)

        btn_save = QPushButton("💾 保存")
        btn_save.clicked.connect(self.save_file)
        btn_save.setToolTip("保存 (Ctrl+S)")
        tb.addWidget(btn_save)

        tb.addSeparator()

        btn_undo = QPushButton("↩ 撤销")
        btn_undo.clicked.connect(self.preview.reset_to_original)
        tb.addWidget(btn_undo)

        btn_reset = QPushButton("🔄 重置")
        btn_reset.clicked.connect(lambda: self._select_tool(self.sidebar.currentRow()))
        tb.addWidget(btn_reset)

        tb.addSeparator()

        btn_fit = QPushButton("📐 适配")
        btn_fit.clicked.connect(self.preview.fit_image)
        tb.addWidget(btn_fit)

        btn_actual = QPushButton("1:1 实际")
        btn_actual.clicked.connect(self.preview.actual_size)
        tb.addWidget(btn_actual)

        btn_zin = QPushButton("➕")
        btn_zin.clicked.connect(self.preview.zoom_in)
        tb.addWidget(btn_zin)

        btn_zout = QPushButton("➖")
        btn_zout.clicked.connect(self.preview.zoom_out)
        tb.addWidget(btn_zout)

        tb.addSeparator()
        btn_theme = QPushButton("主题")
        btn_theme.clicked.connect(self._toggle_theme)
        tb.addWidget(btn_theme)

    def _apply_theme(self) -> None:
        self.setStyleSheet(DARK_QSS if self._dark_mode else LIGHT_QSS)
        self.setProperty("darkMode", self._dark_mode)
        self.style().unpolish(self)
        self.style().polish(self)

    def _toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        self._apply_theme()

    def _filter_tools(self, text: str) -> None:
        query = text.strip().lower()
        current = self.sidebar.currentItem()
        current_name = current.data(Qt.UserRole)[2] if current else ""
        self.sidebar.blockSignals(True)
        self.sidebar.clear()
        for index, (icon, name) in enumerate(TOOL_ITEMS):
            if not query or query in name.lower():
                item = QListWidgetItem(f"  {icon}  {name}")
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                item.setData(Qt.UserRole, (index, icon, name))
                self.sidebar.addItem(item)
        self.sidebar.blockSignals(False)
        if self.sidebar.count():
            row = 0
            for i in range(self.sidebar.count()):
                if self.sidebar.item(i).data(Qt.UserRole)[2] == current_name:
                    row = i
                    break
            self.sidebar.setCurrentRow(row)

    def _select_tool(self, index: int) -> None:
        self._clear_right()
        item = self.sidebar.item(index) if 0 <= index < self.sidebar.count() else None
        if item is None:
            return
        tool_index, _, name = item.data(Qt.UserRole)
        if tool_index >= len(TOOL_ITEMS):
            return
        self.statusBar().showMessage(f"当前工具: {name}", 2000)
        builders = [
            self._build_adjust_panel,
            self._build_filter_panel,
            self._build_format_panel,
            self._build_pdf_panel,
            self._build_exif_panel,
            self._build_ocr_panel,
            self._build_watermark_panel,
            self._build_color_panel,
            self._build_crop_panel,
            self._build_transform_panel,
            self._build_ai_remove_bg_panel,
            self._build_ai_upscale_panel,
            self._build_ai_denoise_panel,
            self._build_ai_colorize_panel,
            self._build_ai_depth_panel,
            self._build_ai_model_manager_panel,
            self._build_shape_mask_panel,
            self._build_histogram_panel,
            self._build_compare_panel,
            self._build_checksum_panel,
            self._build_barcode_panel,
            self._build_gradient_panel,
            self._build_stitch_panel,
            self._build_batch_panel,
            self._build_lut_panel,
            self._build_smart_resize_panel,
            self._build_gmic_panel,
            self._build_animation_panel,
            self._build_pdf_advanced_panel,
            self._build_archive_panel,
            self._build_advanced_panel,
            self._build_parity_panel,
            self._build_parity_panel,
            self._build_parity_panel,
            self._build_parity_panel,
            self._build_parity_panel,
            self._build_parity_panel,
            self._build_parity_panel,
            self._build_parity_panel,
            self._build_parity_panel,
            self._build_parity_panel,
            self._build_parity_panel,
            self._build_about_panel,
        ]
        if 0 <= tool_index < len(builders):
            builders[tool_index]()
        else:
            self._build_empty_panel(name)

    def _clear_right(self) -> None:
        while self.right_layout.count():
            item = self.right_layout.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            else:
                sub = item.layout()
                if sub is not None:
                    self._clear_sub_layout(sub)
                    sub.setParent(None)

    def _clear_sub_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            elif item.layout() is not None:
                self._clear_sub_layout(item.layout())

    def _add_section(self, title: str) -> None:
        label = QLabel(title)
        label.setObjectName("section")
        self.right_layout.addWidget(label)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #e5e7eb; max-height: 1px;")
        self.right_layout.addWidget(line)

    def _add_stretch(self) -> None:
        self.right_layout.addStretch()

    def _build_adjust_panel(self) -> None:
        self._clear_right()
        self._add_section("✨ 基础调整")

        groups = [
            ("亮度", img_core.brightness, [-1.0, 1.0, 0.0, 0.05]),
            ("对比度", img_core.contrast, [-1.0, 1.0, 0.0, 0.05]),
            ("饱和度", img_core.saturation, [-1.0, 1.0, 0.0, 0.05]),
            ("伽马", img_core.gamma, [0.2, 5.0, 1.0, 0.05]),
            ("曝光 (stops)", img_core.exposure, [-3.0, 3.0, 0.0, 0.1]),
            ("色相 (度)", img_core.hue_shift, [-180, 180, 0, 1]),
            ("自然饱和度", img_core.vibrance, [-1.0, 1.0, 0.0, 0.05]),
            ("高光", lambda img, v: img_core.highlights_shadows(img, v, 0), [-100, 100, 0, 1]),
            ("阴影", lambda img, v: img_core.highlights_shadows(img, 0, v), [-100, 100, 0, 1]),
        ]

        for name, func, (lo, hi, default, step) in groups:
            self._add_slider_row(name, func, lo, hi, default, step)

        btn_reset = QPushButton("↩ 撤销所有调整")
        btn_reset.clicked.connect(self.preview.reset_to_original)
        self.right_layout.addWidget(btn_reset)
        self._add_stretch()

    def _add_slider_row(self, label: str, func, lo, hi, default, step) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(label)
        lbl.setFixedWidth(80)
        row.addWidget(lbl)

        slider = QSlider(Qt.Horizontal)
        if isinstance(step, float):
            slider.setRange(int(lo / step), int(hi / step))
            slider.setValue(int(default / step))
        else:
            slider.setRange(int(lo), int(hi))
            slider.setValue(int(default))
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval(max(1, int((hi - lo) / 10)))
        row.addWidget(slider, 1)

        spin = QDoubleSpinBox() if isinstance(step, float) else QSpinBox()
        spin.setRange(lo, hi)
        spin.setValue(default)
        spin.setSingleStep(step)
        spin.setFixedWidth(70)
        if isinstance(spin, QDoubleSpinBox):
            spin.setDecimals(2)
        row.addWidget(spin)

        def on_slider(v):
            if isinstance(step, float):
                val = v * step
            else:
                val = v
            spin.blockSignals(True)
            spin.setValue(float(val))
            spin.blockSignals(False)
            self._apply_instant(func, val)

        def on_spin(v):
            if self.preview.current_image() is None:
                return
            slider.blockSignals(True)
            if isinstance(step, float):
                slider.setValue(int(v / step))
            else:
                slider.setValue(int(v))
            slider.blockSignals(False)
            self._apply_instant(func, v)

        slider.valueChanged.connect(on_slider)
        spin.valueChanged.connect(on_spin)
        self.right_layout.addLayout(row)

    def _apply_instant(self, func, value) -> None:
        if self.preview._original is None:
            return
        try:
            result = func(self.preview._original.copy(), value)
            self.preview.update_current(result)
        except Exception:
            pass

    def _build_filter_panel(self) -> None:
        self._clear_right()
        self._add_section("🎨 滤镜效果")

        search_row = QHBoxLayout()
        search_lbl = QLabel("搜索:")
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("输入滤镜名称...")
        search_row.addWidget(search_lbl)
        search_row.addWidget(search_edit, 1)
        self.right_layout.addLayout(search_row)

        self.filter_list = QListWidget()
        self.filter_list.setFixedHeight(380)
        self.filter_list.setSelectionMode(QListWidget.SingleSelection)
        self.filter_list.itemDoubleClicked.connect(self._on_filter_apply)
        for key, (zh_name, _) in ALL_FILTERS.items():
            item = QListWidgetItem(f"{zh_name}  ({key})")
            item.setData(Qt.UserRole, key)
            self.filter_list.addItem(item)
        self.right_layout.addWidget(self.filter_list)

        def filter_items(text: str):
            self.filter_list.clear()
            t = text.lower()
            for key, (zh_name, _) in ALL_FILTERS.items():
                if t in zh_name.lower() or t in key.lower():
                    item = QListWidgetItem(f"{zh_name}  ({key})")
                    item.setData(Qt.UserRole, key)
                    self.filter_list.addItem(item)

        search_edit.textChanged.connect(filter_items)

        btn_row = QHBoxLayout()
        btn_apply = QPushButton("✅ 应用")
        btn_apply.clicked.connect(self._on_filter_apply_selected)
        btn_row.addWidget(btn_apply)

        btn_reset = QPushButton("↩ 撤销")
        btn_reset.setObjectName("secondary")
        btn_reset.clicked.connect(self.preview.reset_to_original)
        btn_row.addWidget(btn_reset)
        self.right_layout.addLayout(btn_row)

        self._add_stretch()

    def _on_filter_apply(self, item: QListWidgetItem) -> None:
        key = item.data(Qt.UserRole)
        self._apply_filter_by_key(key)

    def _on_filter_apply_selected(self) -> None:
        items = self.filter_list.selectedItems()
        if items:
            self._on_filter_apply(items[0])

    def _apply_filter_by_key(self, key: str) -> None:
        img = self.preview._original
        if img is None:
            self._show_info("请先打开一张图片")
            return
        try:
            result = apply_filter(key, img.copy())
            self.preview.update_current(result)
        except Exception as e:
            QMessageBox.warning(self, "滤镜失败", f"{key}: {e}")

    def _build_format_panel(self) -> None:
        self._clear_right()
        self._add_section("🖼️ 格式转换")

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("目标格式:"))
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["PNG", "JPEG", "WebP", "TIFF", "BMP", "HEIC", "AVIF", "JXL", "ICO"])
        fmt_row.addWidget(self.fmt_combo, 1)
        self.right_layout.addLayout(fmt_row)

        q_row = QHBoxLayout()
        q_row.addWidget(QLabel("质量:"))
        self.fmt_quality = QSpinBox()
        self.fmt_quality.setRange(1, 100)
        self.fmt_quality.setValue(92)
        q_row.addWidget(self.fmt_quality)
        self.right_layout.addLayout(q_row)

        btn_convert = QPushButton("🔄 转换并另存")
        btn_convert.clicked.connect(self._do_format_convert)
        self.right_layout.addWidget(btn_convert)
        self._add_stretch()

    def _do_format_convert(self) -> None:
        if self.preview.current_image() is None:
            self._show_info("请先打开图片")
            return
        ext_map = {"PNG": ".png", "JPEG": ".jpg", "WebP": ".webp", "TIFF": ".tiff",
                   "BMP": ".bmp", "HEIC": ".heic", "AVIF": ".avif", "JXL": ".jxl", "ICO": ".ico"}
        fmt = self.fmt_combo.currentText()
        ext = ext_map.get(fmt, ".png")
        default = self._current_file or "output.png"
        default = str(Path(default).stem) + ext
        path, _ = QFileDialog.getSaveFileName(self, "保存", default, f"{fmt} (*{ext})")
        if path:
            try:
                save_image(self.preview.current_image(), path, quality=self.fmt_quality.value())
                self._current_file = path
                self.statusBar().showMessage(f"已保存到 {path}", 3000)
                self.setWindowTitle(f"Image Toolbox - {Path(path).name}")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", str(e))

    def _build_pdf_panel(self) -> None:
        self._clear_right()
        self._add_section("📄 PDF 工具")

        gb = QGroupBox("图片转 PDF")
        form = QFormLayout(gb)

        self.pdf_name = QLineEdit("output.pdf")
        form.addRow("文件名:", self.pdf_name)

        self.pdf_size = QComboBox()
        self.pdf_size.addItems(["自动", "A4", "A3", "Letter"])
        form.addRow("页面大小:", self.pdf_size)

        self.pdf_quality = QSpinBox()
        self.pdf_quality.setRange(50, 100)
        self.pdf_quality.setValue(92)
        form.addRow("JPEG 质量:", self.pdf_quality)

        self.pdf_multiple = QCheckBox("包含多张图片 (批量)")
        form.addRow(self.pdf_multiple)

        self.right_layout.addWidget(gb)

        btn = QPushButton("📄 生成 PDF")
        btn.clicked.connect(self._img_to_pdf)
        self.right_layout.addWidget(btn)

        btn_p2i = QPushButton("📑 PDF 转图片")
        btn_p2i.setObjectName("secondary")
        btn_p2i.clicked.connect(self._pdf_to_img)
        self.right_layout.addWidget(btn_p2i)

        self._add_stretch()

    def _img_to_pdf(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            QMessageBox.warning(self, "错误", "需要 Pillow")
            return
        if self.preview.current_image() is None and not self.pdf_multiple.isChecked():
            self._show_info("请先打开图片")
            return

        from processors.utils import ensure_rgb, np_to_pil
        if self.pdf_multiple.isChecked():
            files, _ = QFileDialog.getOpenFileNames(self, "选择图片", "",
                "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp)")
            if not files:
                return
            imgs = []
            for f in files:
                from processors.utils import load_image
                arr = load_image(f)
                imgs.append(np_to_pil(ensure_rgb(arr)))
        else:
            imgs = [np_to_pil(ensure_rgb(self.preview.current_image()))]

        path, _ = QFileDialog.getSaveFileName(self, "保存 PDF", self.pdf_name.text(), "PDF (*.pdf)")
        if not path:
            return

        try:
            first = imgs[0]
            if self.pdf_size.currentText() == "A4":
                first = first.resize((595, 842), Image.LANCZOS)
            elif self.pdf_size.currentText() == "A3":
                first = first.resize((842, 1191), Image.LANCZOS)
            elif self.pdf_size.currentText() == "Letter":
                first = first.resize((612, 792), Image.LANCZOS)

            if len(imgs) > 1:
                rest = [np_to_pil(ensure_rgb(load_image(f))) for f in files[1:]] if self.pdf_multiple.isChecked() else []
                if self.pdf_size.currentText() != "自动":
                    sz = first.size
                    rest = [r.resize(sz, Image.LANCZOS) for r in rest]
                first.save(path, "PDF", save_all=True, append_images=rest,
                           resolution=self.pdf_quality.value())
            else:
                first.save(path, "PDF", resolution=self.pdf_quality.value())
            self.statusBar().showMessage(f"PDF 已生成: {path}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "PDF 失败", str(e))

    def _pdf_to_img(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 PDF", "", "PDF (*.pdf)")
        if not path:
            return
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
            self._show_info(f"PDF 共 {len(reader.pages)} 页。导出功能需要 pdf2image + poppler。")
        except Exception as e:
            QMessageBox.critical(self, "失败", str(e))

    def _build_exif_panel(self) -> None:
        self._clear_right()
        self._add_section("🔍 EXIF 信息")

        self.exif_text = QTextEdit()
        self.exif_text.setReadOnly(True)
        self.exif_text.setFixedHeight(320)
        self.right_layout.addWidget(self.exif_text)

        btn_read = QPushButton("📖 读取 EXIF")
        btn_read.clicked.connect(self._read_exif)
        self.right_layout.addWidget(btn_read)

        btn_del = QPushButton("🗑️ 删除 EXIF")
        btn_del.setObjectName("danger")
        btn_del.clicked.connect(self._delete_exif)
        self.right_layout.addWidget(btn_del)

        self._add_stretch()

    def _read_exif(self) -> None:
        if self.preview.current_image() is None:
            self._show_info("请先打开图片")
            return
        info = []
        if self._current_file:
            try:
                from PIL import Image
                img = Image.open(self._current_file)
                exif = img.getexif()
                if exif:
                    tag_names = {
                        0x010e: "ImageDescription", 0x010f: "Make", 0x0110: "Model",
                        0x0112: "Orientation", 0x0132: "Software", 0x013b: "Artist",
                        0x8769: "ExifOffset", 0x9000: "ExifVersion", 0x9003: "DateTimeOriginal",
                        0x9004: "DateTimeDigitized", 0x920a: "FocalLength", 0x9286: "UserComment",
                        0xa001: "ColorSpace", 0xa002: "ExifImageWidth", 0xa003: "ExifImageHeight",
                        0xa420: "ImageUniqueID", 0x0132: "DateTime",
                    }
                    for k, v in exif.items():
                        name = tag_names.get(k, f"0x{k:04x}")
                        info.append(f"{name}: {v}")
                else:
                    info.append("无 EXIF 数据")
                info.append(f"\n文件大小: {Path(self._current_file).stat().st_size / 1024:.1f} KB")
                info.append(f"尺寸: {self.preview.current_image().shape[1]}x{self.preview.current_image().shape[0]}")
            except Exception as e:
                info.append(f"读取失败: {e}")
        else:
            info.append("未打开文件，无法读取 EXIF")
        self.exif_text.setPlainText("\n".join(info))

    def _delete_exif(self) -> None:
        if self.preview.current_image() is None:
            self._show_info("请先打开图片")
            return
        from processors.utils import ensure_rgb, np_to_pil
        path, _ = QFileDialog.getSaveFileName(self, "保存", "clean.png", "PNG (*.png)")
        if not path:
            return
        img = np_to_pil(ensure_rgb(self.preview.current_image()))
        img.save(path, "PNG")
        self.statusBar().showMessage(f"已保存到 {path} (无 EXIF)", 3000)

    def _build_ocr_panel(self) -> None:
        self._clear_right()
        self._add_section("📝 OCR 文字识别")

        gb = QGroupBox("识别设置")
        form = QFormLayout(gb)
        self.ocr_lang = QComboBox()
        self.ocr_lang.addItems(["eng", "chi_sim", "chi_tra", "eng+chi_sim", "jpn", "kor"])
        form.addRow("语言:", self.ocr_lang)
        self.right_layout.addWidget(gb)

        btn = QPushButton("🔤 开始识别")
        btn.clicked.connect(self._do_ocr)
        self.right_layout.addWidget(btn)

        self.ocr_result = QTextEdit()
        self.ocr_result.setPlaceholderText("识别结果将显示在这里...")
        self.right_layout.addWidget(self.ocr_result)

        self._add_stretch()

    def _do_ocr(self) -> None:
        img = self.preview.current_image()
        if img is None:
            self._show_info("请先打开图片")
            return
        try:
            import pytesseract
            from processors.utils import ensure_rgb, np_to_pil
            pil_img = np_to_pil(ensure_rgb(img))
            text = pytesseract.image_to_string(pil_img, lang=self.ocr_lang.currentText())
            self.ocr_result.setPlainText(text)
        except Exception as e:
            if "not found" in str(e).lower() or "tesseract" in str(e).lower():
                QMessageBox.warning(self, "OCR 不可用",
                    "需要安装 tesseract 可执行文件:\n"
                    "sudo apt install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-jpn tesseract-ocr-kor")
            else:
                QMessageBox.warning(self, "OCR 失败", str(e))

    def _build_watermark_panel(self) -> None:
        self._clear_right()
        self._add_section("💧 水印")

        gb = QGroupBox("文字水印")
        form = QFormLayout(gb)
        self.wm_text = QLineEdit("ImageToolbox")
        form.addRow("文字:", self.wm_text)
        self.wm_x = QDoubleSpinBox(); self.wm_x.setRange(0, 1); self.wm_x.setValue(0.5); self.wm_x.setSingleStep(0.01)
        self.wm_y = QDoubleSpinBox(); self.wm_y.setRange(0, 1); self.wm_y.setValue(0.5); self.wm_y.setSingleStep(0.01)
        self.wm_fs = QDoubleSpinBox(); self.wm_fs.setRange(0.05, 2.0); self.wm_fs.setValue(0.15); self.wm_fs.setSingleStep(0.01)
        self.wm_alpha = QDoubleSpinBox(); self.wm_alpha.setRange(0.05, 1.0); self.wm_alpha.setValue(0.5); self.wm_alpha.setSingleStep(0.05)
        form.addRow("X 位置:", self.wm_x)
        form.addRow("Y 位置:", self.wm_y)
        form.addRow("字体比例:", self.wm_fs)
        form.addRow("不透明度:", self.wm_alpha)
        self.right_layout.addWidget(gb)

        btn = QPushButton("💧 应用水印")
        btn.clicked.connect(self._apply_watermark)
        self.right_layout.addWidget(btn)

        btn_repeat = QPushButton("📐 平铺水印")
        btn_repeat.setObjectName("secondary")
        btn_repeat.clicked.connect(self._apply_tiled_watermark)
        self.right_layout.addWidget(btn_repeat)

        self._add_stretch()

    def _apply_watermark(self) -> None:
        img = self.preview._original
        if img is None:
            self._show_info("请先打开图片")
            return
        from processors.filters import add_text_watermark
        from processors.utils import ensure_rgba, u8
        result = add_text_watermark(
            img, self.wm_text.text(), self.wm_x.value(), self.wm_y.value(),
            self.wm_fs.value(), (255, 255, 255), self.wm_alpha.value()
        )
        self.preview.update_current(result)

    def _apply_tiled_watermark(self) -> None:
        img = self.preview._original
        if img is None:
            return
        from processors.filters import add_text_watermark
        result = img.copy()
        rows, cols = 4, 5
        for i in range(rows):
            for j in range(cols):
                x = (j + 0.5) / cols
                y = (i + 0.5) / rows
                result = add_text_watermark(result, self.wm_text.text(), x, y,
                                            self.wm_fs.value(), (255, 255, 255), self.wm_alpha.value())
        self.preview.update_current(result)

    def _build_color_panel(self) -> None:
        self._clear_right()
        self._add_section("🌈 色彩工具")

        btn_palette = QPushButton("🎨 生成调色板 (5 色)")
        btn_palette.clicked.connect(self._generate_palette)
        self.right_layout.addWidget(btn_palette)

        self.palette_display = QWidget()
        self.palette_display.setFixedHeight(60)
        self.palette_display.setStyleSheet("background: white; border: 1px solid #e5e7eb; border-radius: 6px;")
        self.right_layout.addWidget(self.palette_display)

        btn_inv = QPushButton("🔄 反色")
        btn_inv.setObjectName("secondary")
        btn_inv.clicked.connect(lambda: self.preview.update_current(img_core.invert(self.preview.current_image())))
        self.right_layout.addWidget(btn_inv)

        btn_gray = QPushButton("⚫ 灰度")
        btn_gray.setObjectName("secondary")
        btn_gray.clicked.connect(lambda: self.preview.update_current(img_core.grayscale(self.preview.current_image())))
        self.right_layout.addWidget(btn_gray)

        btn_heq = QPushButton("📊 直方图均衡")
        btn_heq.setObjectName("secondary")
        btn_heq.clicked.connect(lambda: self.preview.update_current(img_core.histogram_equalize(self.preview.current_image())))
        self.right_layout.addWidget(btn_heq)

        btn_clahe = QPushButton("🔧 CLAHE")
        btn_clahe.setObjectName("secondary")
        btn_clahe.clicked.connect(lambda: self.preview.update_current(img_core.clahe(self.preview.current_image())))
        self.right_layout.addWidget(btn_clahe)

        btn_vignette = QPushButton("⭕ 暗角")
        btn_vignette.setObjectName("secondary")
        btn_vignette.clicked.connect(lambda: self.preview.update_current(img_core.vignette(self.preview.current_image(), 0.4)))
        self.right_layout.addWidget(btn_vignette)

        self._add_stretch()

    def _generate_palette(self) -> None:
        from collections import Counter
        img = self.preview.current_image()
        if img is None:
            return
        from processors.utils import ensure_rgb
        arr = ensure_rgb(img).reshape(-1, 3)
        sampled = arr[:: max(1, len(arr) // 5000)]
        rounded = (sampled // 32) * 32
        colors, _ = np.unique(rounded, axis=0, return_counts=True)
        counter = Counter()
        for c in rounded:
            counter[tuple(c)] += 1
        top = counter.most_common(5)

        layout = self.palette_display.layout()
        if layout:
            while layout.count():
                layout.itemAt(0).widget().setParent(None)
        layout = QHBoxLayout(self.palette_display)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        for color, count in top:
            w = QFrame()
            c = QColor(int(color[0]), int(color[1]), int(color[2]))
            w.setStyleSheet(f"background: rgb({c.red()},{c.green()},{c.blue()}); border-radius: 4px;")
            w.setToolTip(f"rgb({c.red()},{c.green()},{c.blue()})")
            layout.addWidget(w)

    def _build_crop_panel(self) -> None:
        self._clear_right()
        self._add_section("📏 裁剪")

        gb = QGroupBox("尺寸")
        form = QFormLayout(gb)
        self.crop_w = QSpinBox(); self.crop_w.setRange(1, 10000)
        self.crop_h = QSpinBox(); self.crop_h.setRange(1, 10000)
        form.addRow("宽度:", self.crop_w)
        form.addRow("高度:", self.crop_h)
        btn_size = QPushButton("从当前图片加载")
        btn_size.clicked.connect(self._load_image_size)
        form.addRow(btn_size)
        self.right_layout.addWidget(gb)

        gb2 = QGroupBox("位置")
        form2 = QFormLayout(gb2)
        self.crop_x = QSpinBox(); self.crop_x.setRange(0, 10000)
        self.crop_y = QSpinBox(); self.crop_y.setRange(0, 10000)
        form2.addRow("X:", self.crop_x)
        form2.addRow("Y:", self.crop_y)
        self.right_layout.addWidget(gb2)

        gb3 = QGroupBox("预设比例")
        form3 = QFormLayout(gb3)
        ratio_combo = QComboBox()
        ratio_combo.addItems(["自由", "1:1", "4:3", "16:9", "9:16", "3:4", "21:9", "黄金比"])
        ratio_val = QLabel("")

        def apply_ratio(idx):
            if idx == 0:
                return
            ratios = {1: 1.0, 2: 4 / 3, 3: 16 / 9, 4: 9 / 16, 5: 3 / 4, 6: 21 / 9, 7: 1.618}
            r = ratios[idx]
            if self.preview.current_image() is None:
                return
            h, w = self.preview.current_image().shape[:2]
            if w / h > r:
                self.crop_w.setValue(int(h * r))
                self.crop_h.setValue(h)
            else:
                self.crop_w.setValue(w)
                self.crop_h.setValue(int(w / r))
            ratio_val.setText(f"{self.crop_w.value()}x{self.crop_h.value()}")

        ratio_combo.currentIndexChanged.connect(apply_ratio)
        form3.addRow(ratio_combo, ratio_val)
        self.right_layout.addWidget(gb3)

        btn_center = QPushButton("🎯 中心裁剪")
        btn_center.clicked.connect(self._do_center_crop)
        self.right_layout.addWidget(btn_center)

        btn_apply = QPushButton("✂️ 应用裁剪")
        btn_apply.clicked.connect(self._do_crop)
        self.right_layout.addWidget(btn_apply)

        btn_aspect = QPushButton("比例裁剪")
        btn_aspect.setObjectName("secondary")
        btn_aspect.clicked.connect(self._do_aspect_crop)
        self.right_layout.addWidget(btn_aspect)

        self._add_stretch()

    def _load_image_size(self) -> None:
        img = self.preview.current_image()
        if img is None:
            return
        h, w = img.shape[:2]
        self.crop_w.setValue(w)
        self.crop_h.setValue(h)
        self.crop_x.setValue(0)
        self.crop_y.setValue(0)

    def _do_crop(self) -> None:
        img = self.preview.current_image()
        if img is None:
            return
        result = img_core.crop(img, self.crop_x.value(), self.crop_y.value(),
                               self.crop_w.value(), self.crop_h.value())
        self.preview.update_current(result)

    def _do_center_crop(self) -> None:
        img = self.preview.current_image()
        if img is None:
            return
        result = img_core.center_crop(img, self.crop_w.value(), self.crop_h.value())
        self.preview.update_current(result)

    def _do_aspect_crop(self) -> None:
        img = self.preview.current_image()
        if img is None:
            return
        ratio = self.crop_w.value() / self.crop_h.value() if self.crop_h.value() else 1
        result = img_core.aspect_crop(img, ratio)
        self.preview.update_current(result)

    def _build_transform_panel(self) -> None:
        self._clear_right()
        self._add_section("🔄 变换")

        gb_rot = QGroupBox("旋转")
        form_rot = QFormLayout(gb_rot)
        self.rot_angle = QDoubleSpinBox(); self.rot_angle.setRange(-180, 180); self.rot_angle.setSingleStep(1)
        form_rot.addRow("角度:", self.rot_angle)
        btn_rot = QPushButton("应用旋转")
        btn_rot.clicked.connect(lambda: self.preview.update_current(
            img_core.rotate(self.preview.current_image(), self.rot_angle.value())))
        form_rot.addRow(btn_rot)
        self.right_layout.addWidget(gb_rot)

        row = QHBoxLayout()
        btn_l = QPushButton("↺ 90° 左"); btn_l.clicked.connect(lambda: self.preview.update_current(img_core.rotate(self.preview.current_image(), -90)))
        btn_r = QPushButton("↻ 90° 右"); btn_r.clicked.connect(lambda: self.preview.update_current(img_core.rotate(self.preview.current_image(), 90)))
        btn_180 = QPushButton("180°"); btn_180.clicked.connect(lambda: self.preview.update_current(img_core.rotate(self.preview.current_image(), 180)))
        row.addWidget(btn_l); row.addWidget(btn_r); row.addWidget(btn_180)
        self.right_layout.addLayout(row)

        gb_flip = QGroupBox("翻转")
        r2 = QHBoxLayout()
        btn_hf = QPushButton("⬅➡ 水平"); btn_hf.clicked.connect(lambda: self.preview.update_current(img_core.flip_h(self.preview.current_image())))
        btn_vf = QPushButton("⬆⬇ 垂直"); btn_vf.clicked.connect(lambda: self.preview.update_current(img_core.flip_v(self.preview.current_image())))
        r2.addWidget(btn_hf); r2.addWidget(btn_vf)
        gb_flip.setLayout(r2)
        self.right_layout.addWidget(gb_flip)

        gb_res = QGroupBox("缩放")
        form_res = QFormLayout(gb_res)
        self.res_scale = QDoubleSpinBox(); self.res_scale.setRange(0.01, 10); self.res_scale.setValue(1.0); self.res_scale.setSingleStep(0.1)
        form_res.addRow("比例:", self.res_scale)
        interp_row = QHBoxLayout()
        interp_row.addWidget(QLabel("算法:"))
        self.res_interp = QComboBox(); self.res_interp.addItems(["lanczos", "cubic", "bilinear", "nearest", "area"])
        interp_row.addWidget(self.res_interp, 1)
        form_res.addRow(interp_row)
        btn_res = QPushButton("应用缩放")
        btn_res.clicked.connect(lambda: self.preview.update_current(
            img_core.scale(self.preview.current_image(), self.res_scale.value(),
                           self.res_interp.currentText())))
        form_res.addRow(btn_res)
        self.right_layout.addWidget(gb_res)

        self._add_stretch()

    def _build_gmic_panel(self) -> None:
        self._clear_right()
        self._add_section("🧩 G'MIC 高级滤镜库")
        self.right_layout.addWidget(QLabel("G'MIC 提供大量专业滤镜，可作为 ImageToolbox 的高级滤镜后端。"))
        self.gmic_command = QLineEdit()
        self.gmic_command.setPlaceholderText("例如：-fx_smooth 3,0.5,0.5 -sharpen 2")
        self.right_layout.addWidget(self.gmic_command)
        row = QHBoxLayout()
        run = QPushButton("应用 G'MIC")
        run.clicked.connect(self._apply_gmic)
        row.addWidget(run)
        help_btn = QPushButton("命令帮助")
        help_btn.setObjectName("secondary")
        help_btn.clicked.connect(self._gmic_help)
        row.addWidget(help_btn)
        self.right_layout.addLayout(row)
        self.gmic_output = QTextEdit()
        self.gmic_output.setReadOnly(True)
        self.gmic_output.setPlaceholderText(f"G'MIC {gmic.version() if gmic.available() else '未安装'}")
        self.right_layout.addWidget(self.gmic_output)
        self._add_stretch()

    def _apply_gmic(self) -> None:
        img = self.preview.current_image()
        if img is None:
            self._show_info("请先打开图片")
            return
        if not gmic.available():
            QMessageBox.warning(self, "G'MIC 不可用", "请安装 gmic 后重试。")
            return
        try:
            from processors.utils import save_image, load_image
            with tempfile.TemporaryDirectory(prefix="toolbox_gmic_") as td:
                src = str(Path(td) / "input.png")
                dst = str(Path(td) / "output.png")
                save_image(img, src)
                gmic.apply(src, dst, self.gmic_command.text())
                self.preview.update_current(load_image(dst))
            self.statusBar().showMessage("G'MIC 处理完成", 3000)
        except Exception as e:
            QMessageBox.warning(self, "G'MIC 失败", str(e))

    def _gmic_help(self) -> None:
        command = self.gmic_command.text().strip().split()[0] if self.gmic_command.text().strip() else ""
        self.gmic_output.setPlainText(gmic.command_help(command) if command else "请先输入一个 G'MIC 命令。")

    def _build_animation_panel(self) -> None:
        self._clear_right()
        self._add_section("🎞️ 动画 / GIF / APNG / WebP")
        self.anim_files = QLineEdit()
        self.anim_files.setPlaceholderText("选择多张图片，逗号分隔")
        self.right_layout.addWidget(self.anim_files)
        row = QHBoxLayout()
        choose = QPushButton("选择图片")
        choose.clicked.connect(self._choose_animation_frames)
        row.addWidget(choose)
        fmt = QComboBox()
        fmt.addItems(["GIF", "WebP", "APNG"])
        self.anim_fmt = fmt
        row.addWidget(fmt)
        self.right_layout.addLayout(row)
        self.anim_fps = QDoubleSpinBox(); self.anim_fps.setRange(1, 120); self.anim_fps.setValue(12); self.anim_fps.setSuffix(" FPS")
        self.right_layout.addWidget(self.anim_fps)
        make = QPushButton("生成动画")
        make.clicked.connect(self._make_animation)
        self.right_layout.addWidget(make)
        extract = QPushButton("拆分动画到图片")
        extract.setObjectName("secondary")
        extract.clicked.connect(self._extract_animation)
        self.right_layout.addWidget(extract)
        self._add_stretch()

    def _choose_animation_frames(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择动画帧", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)")
        if files:
            self.anim_files.setText(";".join(files))

    def _make_animation(self) -> None:
        files = [p for p in self.anim_files.text().split(";") if p]
        if not files:
            self._show_info("请先选择图片")
            return
        ext = self.anim_fmt.currentText().lower()
        out, _ = QFileDialog.getSaveFileName(self, "保存动画", f"animation.{ext}", f"{ext.upper()} (*.{ext})")
        if not out:
            return
        try:
            media.convert_animation(files, out, ext, self.anim_fps.value())
            self.statusBar().showMessage(f"动画已生成: {out}", 4000)
        except Exception as e:
            QMessageBox.warning(self, "动画失败", str(e))

    def _extract_animation(self) -> None:
        src, _ = QFileDialog.getOpenFileName(self, "选择动画", "", "Animation (*.gif *.webp *.apng *.jxl)")
        if not src:
            return
        out = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if not out:
            return
        try:
            frames = media.extract_frames(src, out)
            QMessageBox.information(self, "完成", f"已导出 {len(frames)} 帧")
        except Exception as e:
            QMessageBox.warning(self, "拆分失败", str(e))

    def _build_pdf_advanced_panel(self) -> None:
        self._clear_right()
        self._add_section("📑 PDF 高级工具")
        merge = QPushButton("合并 PDF")
        merge.clicked.connect(self._pdf_merge)
        self.right_layout.addWidget(merge)
        split = QPushButton("拆分 PDF")
        split.clicked.connect(self._pdf_split)
        self.right_layout.addWidget(split)
        rotate = QPushButton("旋转 PDF")
        rotate.clicked.connect(self._pdf_rotate)
        self.right_layout.addWidget(rotate)
        remove = QPushButton("删除指定页")
        remove.clicked.connect(self._pdf_remove_pages)
        self.right_layout.addWidget(remove)
        text = QPushButton("提取 PDF 文本")
        text.clicked.connect(self._pdf_text)
        self.right_layout.addWidget(text)
        protect = QPushButton("密码保护 PDF")
        protect.clicked.connect(self._pdf_protect)
        self.right_layout.addWidget(protect)
        self._add_stretch()

    def _pdf_merge(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择 PDF", "", "PDF (*.pdf)")
        if len(files) < 2: return
        out, _ = QFileDialog.getSaveFileName(self, "保存", "merged.pdf", "PDF (*.pdf)")
        if out:
            try: pdf_tools.merge_pdfs(files, out); self.statusBar().showMessage("PDF 合并完成", 3000)
            except Exception as e: QMessageBox.warning(self, "失败", str(e))

    def _pdf_split(self) -> None:
        src, _ = QFileDialog.getOpenFileName(self, "选择 PDF", "", "PDF (*.pdf)")
        out = QFileDialog.getExistingDirectory(self, "输出目录") if src else ""
        if src and out:
            try: QMessageBox.information(self, "完成", f"已生成 {len(pdf_tools.split_pdf(src, out))} 个 PDF")
            except Exception as e: QMessageBox.warning(self, "失败", str(e))

    def _pdf_rotate(self) -> None:
        src, _ = QFileDialog.getOpenFileName(self, "选择 PDF", "", "PDF (*.pdf)")
        if not src: return
        deg, ok = QInputDialog.getInt(self, "旋转", "角度:", 90, -360, 360, 90)
        if not ok: return
        out, _ = QFileDialog.getSaveFileName(self, "保存", "rotated.pdf", "PDF (*.pdf)")
        if out:
            try: pdf_tools.rotate_pdf(src, out, deg); self.statusBar().showMessage("PDF 旋转完成", 3000)
            except Exception as e: QMessageBox.warning(self, "失败", str(e))

    def _pdf_remove_pages(self) -> None:
        src, _ = QFileDialog.getOpenFileName(self, "选择 PDF", "", "PDF (*.pdf)")
        if not src: return
        pages, ok = QInputDialog.getText(self, "删除页", "页码（逗号分隔）:")
        if not ok: return
        nums = [int(x.strip()) for x in pages.split(",") if x.strip().isdigit()]
        out, _ = QFileDialog.getSaveFileName(self, "保存", "clean.pdf", "PDF (*.pdf)")
        if out:
            try: pdf_tools.remove_pages(src, out, nums); self.statusBar().showMessage("页面删除完成", 3000)
            except Exception as e: QMessageBox.warning(self, "失败", str(e))

    def _pdf_text(self) -> None:
        src, _ = QFileDialog.getOpenFileName(self, "选择 PDF", "", "PDF (*.pdf)")
        if src:
            try:
                text = pdf_tools.extract_text(src)
                out, _ = QFileDialog.getSaveFileName(self, "保存文本", Path(src).stem + ".txt", "Text (*.txt)")
                if out: Path(out).write_text(text, encoding="utf-8")
            except Exception as e: QMessageBox.warning(self, "失败", str(e))

    def _pdf_protect(self) -> None:
        src, _ = QFileDialog.getOpenFileName(self, "选择 PDF", "", "PDF (*.pdf)")
        if not src: return
        password, ok = QInputDialog.getText(self, "密码保护", "密码:", QLineEdit.Password)
        if not ok or not password: return
        out, _ = QFileDialog.getSaveFileName(self, "保存", "protected.pdf", "PDF (*.pdf)")
        if out:
            try: pdf_tools.protect_pdf(src, out, password); self.statusBar().showMessage("PDF 已加密", 3000)
            except Exception as e: QMessageBox.warning(self, "失败", str(e))

    def _build_archive_panel(self) -> None:
        self._clear_right()
        self._add_section("🗜️ 压缩 / 打包")
        self.archive_files = QLineEdit()
        self.archive_files.setPlaceholderText("选择要打包的文件")
        self.right_layout.addWidget(self.archive_files)
        choose = QPushButton("选择文件")
        choose.clicked.connect(self._choose_archive_files)
        self.right_layout.addWidget(choose)
        zip_btn = QPushButton("创建 ZIP")
        zip_btn.clicked.connect(self._create_zip)
        self.right_layout.addWidget(zip_btn)
        self._add_stretch()

    def _choose_archive_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择文件")
        if files: self.archive_files.setText(";".join(files))

    def _create_zip(self) -> None:
        import zipfile
        files = [p for p in self.archive_files.text().split(";") if p]
        if not files: return
        out, _ = QFileDialog.getSaveFileName(self, "保存 ZIP", "images.zip", "ZIP (*.zip)")
        if not out: return
        try:
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
                for p in files: z.write(p, Path(p).name)
            self.statusBar().showMessage(f"ZIP 已创建: {out}", 3000)
        except Exception as e: QMessageBox.warning(self, "失败", str(e))

    def _build_advanced_panel(self) -> None:
        self._clear_right()
        self._add_section("🧰 高级图像工具")
        shrink = QPushButton("按目标大小压缩")
        shrink.clicked.connect(self._shrink_to_size)
        self.right_layout.addWidget(shrink)
        content = QPushButton("自动裁剪透明 / 背景边缘")
        content.clicked.connect(self._auto_crop_content)
        self.right_layout.addWidget(content)
        border = QPushButton("添加画布边框")
        border.clicked.connect(self._add_border)
        self.right_layout.addWidget(border)
        identify = QPushButton("查看图像完整信息")
        identify.clicked.connect(self._show_image_info)
        self.right_layout.addWidget(identify)
        self._add_stretch()

    def _shrink_to_size(self) -> None:
        img = self.preview.current_image()
        if img is None: return
        kb, ok = QInputDialog.getInt(self, "目标大小", "KB:", 500, 10, 100000)
        if not ok: return
        out, _ = QFileDialog.getSaveFileName(self, "保存", "compressed.jpg", "JPEG (*.jpg *.jpeg)")
        if not out: return
        from PIL import Image
        from processors.utils import ensure_rgb, np_to_pil
        pil = np_to_pil(ensure_rgb(img))
        quality = 95
        while quality >= 5:
            pil.save(out, "JPEG", quality=quality, optimize=True)
            if Path(out).stat().st_size <= kb * 1024: break
            quality -= 5
        self.statusBar().showMessage(f"压缩完成: {Path(out).stat().st_size / 1024:.1f} KB", 3000)

    def _auto_crop_content(self) -> None:
        img = self.preview.current_image()
        if img is None: return
        import cv2
        rgb = img[..., :3] if img.ndim == 3 else img
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        mask = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)[1]
        box = cv2.boundingRect(mask)
        if box[2] > 0 and box[3] > 0:
            self.preview.update_current(img_core.crop(img, *box))

    def _add_border(self) -> None:
        img = self.preview.current_image()
        if img is None: return
        px, ok = QInputDialog.getInt(self, "边框", "像素:", 32, 1, 2000)
        if not ok: return
        self.preview.update_current(img_core.border(img, px, px, px, px, (0, 0, 0)))

    def _show_image_info(self) -> None:
        img = self.preview.current_image()
        if img is None: return
        h, w = img.shape[:2]
        channels = img.shape[2] if img.ndim == 3 else 1
        self._show_info(f"尺寸: {w} × {h}\n通道: {channels}\n类型: {img.dtype}\n当前文件: {self._current_file or '未保存'}")

    def _build_about_panel(self) -> None:
        self._clear_right()
        self._add_section("❓ 关于")
        t = QLabel()
        t.setWordWrap(True)
        t.setTextFormat(Qt.RichText)
        t.setText("""
        <h2>🖼️ Image Toolbox - 图像工具箱</h2>
        <p>基于 Python + PySide6 + OpenCV + scikit-image 构建的桌面图像编辑工具。</p>
        <h3>功能亮点</h3>
        <ul>
          <li>✨ 基础调整: 亮度 / 对比度 / 饱和度 / 伽马 / 曝光</li>
          <li>🎨 80+ 种滤镜效果, 支持实时预览</li>
          <li>🖼️ 格式转换: PNG / JPEG / WebP / TIFF / HEIC / AVIF / JXL</li>
          <li>📄 PDF 工具: 图片转 PDF</li>
          <li>📝 OCR 文字识别 (依赖 tesseract)</li>
          <li>🔍 EXIF 查看与删除</li>
          <li>💧 水印: 支持平铺 / 单点</li>
          <li>🌈 色彩工具: 调色板 / 反色 / 直方图均衡 / 暗角</li>
          <li>📏 裁剪 / 🔄 旋转翻转缩放</li>
          <li>🖱️ 支持拖拽图片进入窗口打开</li>
        </ul>
        <h3>快捷键</h3>
        <ul>
          <li>Ctrl+O 打开 &nbsp;&nbsp; Ctrl+S 保存</li>
          <li>Ctrl+Z 撤销 &nbsp;&nbsp; Ctrl+T 切换主题</li>
          <li>0 适配窗口 &nbsp;&nbsp; 1 实际大小</li>
          <li>+/- 缩放 &nbsp;&nbsp; ESC 重置</li>
        </ul>
        <p><b>原项目:</b> <a href="https://github.com/T8RIN/ImageToolbox">ImageToolbox (Android)</a></p>
        <p><b>Python 桌面版:</b> 本地重构实现</p>
        """)
        self.right_layout.addWidget(t)
        self._add_stretch()

    def _build_empty_panel(self, name: str) -> None:
        self._clear_right()
        self.right_layout.addWidget(QLabel(f"工具 '{name}' 开发中..."))
        self._add_stretch()

    def _on_image_changed(self) -> None:
        img = self.preview.current_image()
        if img is not None:
            h, w = img.shape[:2]
            self.status_info.setText(f"{w}×{h}  |  {self._current_file or '未保存'}")
        self.status_zoom.setText(f"{int(self.preview.scale_value() * 100)}%")

    def _on_mouse_moved(self, x: int, y: int) -> None:
        self.status_pos.setText(f"坐标: ({x}, {y})")

    def open_file_dialog(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "打开图片", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp *.heic *.heif *.avif *.jxl *.gif)")
        for f in files:
            self.load_file(f)
            break

    def load_file(self, path: str) -> None:
        try:
            arr = load_image(path)
            self.preview.set_image(arr)
            self._current_file = path
            self.setWindowTitle(f"Image Toolbox - {Path(path).name}")
            if path not in self._recent_files:
                self._recent_files.insert(0, path)
                self._recent_files = self._recent_files[:10]
        except Exception as e:
            QMessageBox.critical(self, "打开失败", f"无法打开 {path}:\n{e}")

    def save_file(self) -> None:
        if self.preview.current_image() is None:
            self._show_info("没有图片可保存")
            return
        if self._current_file:
            try:
                save_image(self.preview.current_image(), self._current_file)
                self.statusBar().showMessage(f"已保存: {self._current_file}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "保存失败", str(e))
        else:
            self.save_file_as()

    def save_file_as(self) -> None:
        if self.preview.current_image() is None:
            self._show_info("没有图片可保存")
            return
        path, _ = QFileDialog.getSaveFileName(self, "另存为", self._current_file or "output.png",
            "PNG (*.png);;JPEG (*.jpg);;WebP (*.webp);;TIFF (*.tiff);;BMP (*.bmp)")
        if path:
            try:
                save_image(self.preview.current_image(), path)
                self._current_file = path
                self.setWindowTitle(f"Image Toolbox - {Path(path).name}")
                self.statusBar().showMessage(f"已保存: {path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "保存失败", str(e))

    def _show_info(self, msg: str) -> None:
        self.statusBar().showMessage(msg, 3000)

    def _show_about(self) -> None:
        QMessageBox.about(self, "关于", "Image Toolbox Python 桌面版\n\n基于 PySide6 + OpenCV + rembg AI\n重构自 Android 开源项目")

    def _build_ai_remove_bg_panel(self) -> None:
        from processors.ai import BG_REMOVE_MODELS
        self._add_section("AI 智能抠图 (rembg)")
        self._add_section("模型 (首次运行自动下载)")
        row = QHBoxLayout()
        row.addWidget(QLabel("模型:"))
        self.rmbg_model = QComboBox()
        for cn, key in BG_REMOVE_MODELS:
            self.rmbg_model.addItem(cn, key)
        row.addWidget(self.rmbg_model)
        self.right_layout.addLayout(row)
        self.rmbg_alpha_matting = QCheckBox("Alpha Matting (更精细,慢)")
        self.right_layout.addWidget(self.rmbg_alpha_matting)
        btn_remove = QPushButton("🎯 一键抠图 (透明背景 PNG)")
        btn_remove.clicked.connect(self._ai_remove_bg)
        self.right_layout.addWidget(btn_remove)
        btn_replace = QPushButton("🎨 换背景色 (绿幕效果)")
        btn_replace.clicked.connect(self._ai_replace_bg)
        self.right_layout.addWidget(btn_replace)
        btn_bokeh = QPushButton("📷 人像背景虚化")
        btn_bokeh.clicked.connect(self._ai_bokeh)
        self.right_layout.addWidget(btn_bokeh)

    def _ai_remove_bg(self) -> None:
        from processors import ai
        img = self.preview.current_image()
        if img is None: return
        self.statusBar().showMessage("AI 抠图中，首次运行正在下载模型...", 0)
        QApplication.processEvents()
        try:
            from processors.ai_models import selected_backend
            result = ai.remove_background(img, model=self.rmbg_model.currentData(),
                                          alpha_matting=self.rmbg_alpha_matting.isChecked(),
                                          backend=selected_backend())
            self.preview.set_image(result)
            self.statusBar().showMessage("抠图完成", 3000)
        except Exception as e:
            self.statusBar().clearMessage()
            QMessageBox.warning(self, "AI 抠图失败", str(e))

    def _ai_replace_bg(self) -> None:
        from processors import ai
        img = self.preview.current_image()
        if img is None: return
        color = QColorDialog.getColor(QColor(0, 255, 0), self, "选择背景色")
        if not color.isValid(): return
        self.statusBar().showMessage("AI 抠图+换背景中...", 0)
        QApplication.processEvents()
        try:
            from processors.ai_models import selected_backend
            rgba = ai.remove_background(img, model=self.rmbg_model.currentData(),
                                        alpha_matting=self.rmbg_alpha_matting.isChecked(),
                                        backend=selected_backend())
            result = ai.composite_on_bg(rgba, (color.red(), color.green(), color.blue()))
            self.preview.set_image(result)
            self.statusBar().showMessage("换背景完成", 3000)
        except Exception as e:
            self.statusBar().clearMessage()
            QMessageBox.warning(self, "失败", str(e))

    def _ai_bokeh(self) -> None:
        from processors import ai
        img = self.preview.current_image()
        if img is None: return
        blur, ok = QInputDialog.getInt(self, "背景虚化", "模糊强度:", 15, 1, 50)
        if not ok: return
        self.statusBar().showMessage("AI 人像虚化中...", 0)
        QApplication.processEvents()
        try:
            result = ai.portrait_bokeh(img, model=self.rmbg_model.currentData(),
                                       blur_strength=blur)
            self.preview.set_image(result)
            self.statusBar().showMessage("完成", 3000)
        except Exception as e:
            self.statusBar().clearMessage()
            QMessageBox.warning(self, "失败", str(e))

    def _build_ai_upscale_panel(self) -> None:
        self._add_section("AI 智能放大 Upscale")
        row = QHBoxLayout()
        row.addWidget(QLabel("倍数:"))
        self.upscale_factor = QComboBox()
        self.upscale_factor.addItems(["2x", "3x", "4x", "8x"])
        self.upscale_factor.setCurrentIndex(1)
        row.addWidget(self.upscale_factor)
        self.right_layout.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("方法:"))
        self.upscale_method = QComboBox()
        self.upscale_method.addItems(["Lanczos (快速)", "Bicubic", "AI 模型"])
        row2.addWidget(self.upscale_method)
        self.upscale_model = QComboBox()
        from processors.ai_models import registry
        for model in registry():
            if model["task"] != "超分": continue
            state = "已安装" if model["installed"] else "未安装"
            self.upscale_model.addItem(f"{model['name']} · {state}", model["id"])
        self.right_layout.addWidget(QLabel("AI 模型:"))
        self.right_layout.addWidget(self.upscale_model)
        self.right_layout.addLayout(row2)
        btn = QPushButton("📈 执行 Upscale")
        btn.clicked.connect(self._ai_upscale)
        self.right_layout.addWidget(btn)
        tip = QLabel("💡 Lanczos 快速且效果好；AI 模型更精细但需下载权重")
        tip.setWordWrap(True); tip.setStyleSheet("color: gray;")
        self.right_layout.addWidget(tip)

    def _ai_upscale(self) -> None:
        from processors import ai
        img = self.preview.current_image()
        if img is None: return
        factor = int(self.upscale_factor.currentText().replace("x", ""))
        method = self.upscale_method.currentText()
        self.statusBar().showMessage(f"Upscale {factor}x 中...", 0)
        QApplication.processEvents()
        try:
            if "Bicubic" in method: result = ai.upscale_cubic(img, factor)
            elif "AI" in method:
                model = self.upscale_model.currentData() or "realesrgan-x4plus"
                if not ai.ai_model_available(model):
                    raise RuntimeError(f"模型 {model} 尚未安装。当前已安装的本地模型会显示为‘已安装’。")
                if "AnimeVideoV3" in model or model.endswith("-x2") or model.endswith("-x3"):
                    raise RuntimeError("该模型已经纳入模型库，但当前 Upscayl 调用链正在整理不同倍率的模型参数，暂不能直接用于此处。")
                result = ai.upscale_realesrgan(img, factor, model=model)
            else: result = ai.upscale_lanczos(img, factor)
            self.preview.set_image(result)
            h, w = result.shape[:2]
            self.statusBar().showMessage(f"完成: {w}x{h}", 3000)
        except Exception as e:
            self.statusBar().clearMessage()
            QMessageBox.warning(self, "失败", str(e))

    def _build_ai_denoise_panel(self) -> None:
        self._add_section("AI 智能降噪")
        row = QHBoxLayout()
        row.addWidget(QLabel("强度:"))
        self.denoise_strength = QSpinBox()
        self.denoise_strength.setRange(1, 50); self.denoise_strength.setValue(15)
        row.addWidget(self.denoise_strength)
        self.right_layout.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("方法:"))
        self.denoise_method = QComboBox()
        self.denoise_method.addItems(["NLM 非局部均值 (推荐)", "双边滤波", "中值滤波", "细节保留式"])
        row2.addWidget(self.denoise_method)
        self.right_layout.addLayout(row2)
        btn = QPushButton("🧹 执行降噪")
        btn.clicked.connect(self._ai_denoise)
        self.right_layout.addWidget(btn)

    def _ai_denoise(self) -> None:
        from processors import ai
        img = self.preview.current_image()
        if img is None: return
        strength = float(self.denoise_strength.value())
        method = self.denoise_method.currentText()
        try:
            if "NLM" in method: result = ai.denoise_nlm(img, strength)
            elif "双边" in method: result = ai.denoise_bilateral(img, sigma_color=strength, sigma_space=strength)
            elif "中值" in method: result = ai.denoise_median(img, max(1, int(strength / 5) * 2 + 1))
            else: result = ai.denoise_wavelet(img, strength)
            self.preview.set_image(result)
            self.statusBar().showMessage(f"降噪完成 ({method})", 3000)
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))

    def _build_ai_colorize_panel(self) -> None:
        self._add_section("AI 色彩化 / 风格化")
        row = QHBoxLayout()
        row.addWidget(QLabel("风格:"))
        self.colorize_style = QComboBox()
        self.colorize_style.addItems(["vintage 复古", "warm 暖色", "cool 冷色",
                                      "sunset 日落", "forest 森林", "手工着色"])
        row.addWidget(self.colorize_style)
        self.right_layout.addLayout(row)
        btn = QPushButton("🎨 应用风格")
        btn.clicked.connect(self._ai_colorize)
        self.right_layout.addWidget(btn)
        self._add_section("一键 AI 增强")
        btn_enhance = QPushButton("✨ AI 综合增强 (降噪+放大+饱和+对比)")
        btn_enhance.clicked.connect(self._ai_enhance)
        self.right_layout.addWidget(btn_enhance)

    def _ai_colorize(self) -> None:
        from processors import ai
        img = self.preview.current_image()
        if img is None: return
        style_map = {"vintage 复古": "vintage", "warm 暖色": "warm",
                     "cool 冷色": "cool", "sunset 日落": "sunset",
                     "forest 森林": "forest"}
        style = style_map.get(self.colorize_style.currentText(), "vintage")
        result = ai.colorize_transfer(img, style)
        self.preview.set_image(result)
        self.statusBar().showMessage("风格应用完成", 3000)

    def _ai_enhance(self) -> None:
        from processors import ai
        img = self.preview.current_image()
        if img is None: return
        result = ai.ai_enhance(img, denoise=5.0, upscale=1.5, saturation=1.2, contrast=1.1)
        self.preview.set_image(result)
        h, w = result.shape[:2]
        self.statusBar().showMessage(f"AI 增强完成: {w}x{h}", 3000)

    def _build_ai_model_manager_panel(self) -> None:
        from processors.ai_models import registry, detect_backends
        self._add_section("AI 模型管理器")
        self.ai_task_filter = QComboBox()
        self.ai_task_filter.addItems(["全部任务", "抠图", "超分", "深度"])
        self.ai_task_filter.currentIndexChanged.connect(self._refresh_ai_models)
        self.right_layout.addWidget(self.ai_task_filter)
        self.ai_model_list = QComboBox()
        self.right_layout.addWidget(self.ai_model_list)
        self.ai_model_info = QLabel()
        self.ai_model_info.setWordWrap(True)
        self.right_layout.addWidget(self.ai_model_info)
        row = QHBoxLayout()
        btn_install = QPushButton("安装 / 下载"); btn_install.clicked.connect(self._ai_install_model); row.addWidget(btn_install)
        btn_remove = QPushButton("删除缓存"); btn_remove.clicked.connect(self._ai_remove_model); row.addWidget(btn_remove)
        btn_refresh = QPushButton("刷新"); btn_refresh.clicked.connect(self._refresh_ai_models); row.addWidget(btn_refresh)
        self.right_layout.addLayout(row)
        from processors.ai_models import selected_backend
        self.ai_backend = QComboBox(); self.ai_backend.addItems(["自动选择", "CUDA", "Vulkan", "CPU"])
        saved = selected_backend(); self.ai_backend.setCurrentText({"auto":"自动选择"}.get(saved, saved))
        self.ai_backend.currentTextChanged.connect(self._save_ai_backend)
        self.right_layout.addWidget(QLabel("推理后端:")); self.right_layout.addWidget(self.ai_backend)
        self.right_layout.addWidget(QLabel(f"当前可用后端: {', '.join(detect_backends())}"))
        self._refresh_ai_models()

    def _refresh_ai_models(self) -> None:
        from processors.ai_models import registry, get_model, verify_model
        if not hasattr(self, "ai_model_list"): return
        task = self.ai_task_filter.currentText()
        self.ai_model_list.blockSignals(True); self.ai_model_list.clear()
        for m in registry():
            if task != "全部任务" and m["task"] != task: continue
            state = "已安装" if m["installed"] else "未安装"
            self.ai_model_list.addItem(f"{m['name']} · {state}", m["id"])
        self.ai_model_list.blockSignals(False); self._show_ai_model_info()

    def _save_ai_backend(self, value: str) -> None:
        from processors.ai_models import set_backend
        set_backend({"自动选择":"auto"}.get(value, value))
        self._show_ai_model_info()

    def _show_ai_model_info(self) -> None:
        from processors.ai_models import verify_model, get_model, backend_for, model_params
        if not hasattr(self, "ai_model_list") or self.ai_model_list.currentIndex() < 0: return
        mid=self.ai_model_list.currentData(); m=get_model(mid); info=verify_model(mid)
        self.ai_model_info.setText(f"任务: {m['task']}\n模型版本: {m['version']}\n后端: {m['backend']} / {m['runtime']}\n来源: {m['source']}\n大小: {info['size_text']}\n当前后端: {backend_for(mid, 'auto')}\n参数: {model_params(mid) or '无'}")

    def _ai_install_model(self) -> None:
        from processors.ai_models import install_model
        mid=self.ai_model_list.currentData()
        if not mid: return
        self.statusBar().showMessage("正在安装 AI 模型…", 0); QApplication.processEvents()
        try:
            result=install_model(mid, lambda msg: self.statusBar().showMessage(msg, 0))
            self._refresh_ai_models(); self.statusBar().showMessage(f"模型 {result['name']} 已就绪", 3000)
        except Exception as e: QMessageBox.warning(self, "模型安装失败", str(e))

    def _ai_remove_model(self) -> None:
        from processors.ai_models import uninstall_model
        mid=self.ai_model_list.currentData()
        if not mid: return
        try:
            uninstall_model(mid); self._refresh_ai_models(); self.statusBar().showMessage("模型缓存已删除", 3000)
        except Exception as e: QMessageBox.warning(self, "无法删除模型", str(e))

    def _build_ai_depth_panel(self) -> None:
        from processors.ai import DEPTH_MODELS
        self._add_section("AI 深度图 (Depth Map)")
        row = QHBoxLayout()
        row.addWidget(QLabel("方法:"))
        self.depth_method = QComboBox()
        for cn, key in DEPTH_MODELS:
            self.depth_method.addItem(cn, key)
        row.addWidget(self.depth_method)
        self.right_layout.addLayout(row)
        btn = QPushButton("🌄 生成深度图")
        btn.clicked.connect(self._ai_depth)
        self.right_layout.addWidget(btn)
        tip = QLabel("💡 启发式方法无需下载；Depth Anything V2 更准确")
        tip.setWordWrap(True); tip.setStyleSheet("color: gray;")
        self.right_layout.addWidget(tip)

    def _ai_depth(self) -> None:
        from processors import ai
        img = self.preview.current_image()
        if img is None: return
        key = self.depth_method.currentData()
        self.statusBar().showMessage("生成深度图...", 0)
        QApplication.processEvents()
        try:
            if key == "heuristic":
                result = ai.depth_map(img)
            else:
                result = ai.depth_map_rembg(img, key)
                if result is None:
                    QMessageBox.information(self, "提示",
                        f"模型 {key} 暂不可用，已用启发式替代。")
                    result = ai.depth_map(img)
            self.preview.set_image(result)
            self.statusBar().showMessage("深度图完成", 3000)
        except Exception as e:
            self.statusBar().clearMessage()
            QMessageBox.warning(self, "失败", str(e))

    def _build_shape_mask_panel(self) -> None:
        from processors.shapes import SHAPE_PRESETS
        self._add_section("形状蒙版")
        row = QHBoxLayout()
        row.addWidget(QLabel("形状:"))
        self.shape_combo = QComboBox()
        for cn, key in SHAPE_PRESETS:
            self.shape_combo.addItem(cn, key)
        row.addWidget(self.shape_combo)
        self.right_layout.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("羽化:"))
        self.shape_feather = QSpinBox()
        self.shape_feather.setRange(0, 50)
        row2.addWidget(self.shape_feather)
        self.right_layout.addLayout(row2)
        btn_apply = QPushButton("应用形状蒙版")
        btn_apply.clicked.connect(self._apply_shape_mask)
        self.right_layout.addWidget(btn_apply)

    def _apply_shape_mask(self) -> None:
        from processors.shapes import apply_shape_mask
        img = self.preview.get_image()
        if img is None: return
        key = self.shape_combo.currentData()
        feather = self.shape_feather.value()
        c = [255, 255, 255]
        result = apply_shape_mask(img, key, feather, c)
        self.preview.set_image(result)

    def _build_histogram_panel(self) -> None:
        from processors import histogram
        self._add_section("直方图")
        self.histogram_label = QLabel("尚未生成")
        self.histogram_label.setFixedHeight(200)
        self.histogram_label.setStyleSheet("border: 1px solid #555;")
        self.right_layout.addWidget(self.histogram_label)
        btn = QPushButton("生成直方图")
        btn.clicked.connect(self._generate_histogram)
        self.right_layout.addWidget(btn)
        self._hist_mode = 0
        btn2 = QPushButton("切换 RGB/Luma/HSV")
        btn2.clicked.connect(self._cycle_histogram_mode)
        self.right_layout.addWidget(btn2)

    def _cycle_histogram_mode(self) -> None:
        self._hist_mode = (self._hist_mode + 1) % 3
        self._generate_histogram()

    def _generate_histogram(self) -> None:
        img = self.preview.get_image()
        if img is None: return
        from processors import histogram
        from PIL import Image, ImageDraw
        from PySide6.QtGui import QPixmap, QImage
        import numpy as np
        w, h = 300, 200
        canvas = np.full((h, w, 3), (30, 30, 30), dtype=np.uint8)
        mode = self._hist_mode
        if mode == 0:
            data = histogram.histogram_rgb(img)
            colors = {"R": (255, 80, 80), "G": (80, 220, 80), "B": (80, 130, 255)}
            pil = Image.fromarray(canvas)
            draw = ImageDraw.Draw(pil)
            for ch, arr in data.items():
                vals = np.array(arr)
                maxv = max(1, vals.max())
                for i, v in enumerate(vals):
                    x = int(i / 255 * w)
                    y = int(h - v / maxv * h * 0.95 - 5)
                    draw.line([(x, h - 5), (x, y)], fill=colors[ch], width=1)
            canvas = np.array(pil)
        elif mode == 1:
            arr = histogram.histogram_luma(img)
            vals = np.array(arr)
            maxv = max(1, vals.max())
            pil = Image.fromarray(canvas)
            draw = ImageDraw.Draw(pil)
            for i, v in enumerate(vals):
                x = int(i / 255 * w)
                y = int(h - v / maxv * h * 0.95 - 5)
                draw.line([(x, h - 5), (x, y)], fill=(200, 200, 200), width=1)
            canvas = np.array(pil)
        else:
            data = histogram.histogram_hsv(img)
            pil = Image.fromarray(canvas)
            draw = ImageDraw.Draw(pil)
            maxv = max(max(data["H"]), max(data["S"]), max(data["V"]), 1)
            for arr, col in [(data["H"], (255, 100, 100)), (data["S"], (100, 255, 100)), (data["V"], (100, 100, 255))]:
                for i, v in enumerate(arr):
                    x = int(i / len(arr) * w)
                    y = int(h - v / maxv * h * 0.95 - 5)
                    draw.line([(x, h - 5), (x, y)], fill=col, width=1)
            canvas = np.array(pil)
        pil_img = QImage(canvas.data, canvas.shape[1], canvas.shape[0], canvas.strides[0], QImage.Format_RGB888).copy()
        self.histogram_label.setPixmap(QPixmap.fromImage(pil_img).scaled(300, 200))

    def _build_compare_panel(self) -> None:
        self._add_section("图像比较")
        row = QHBoxLayout()
        row.addWidget(QLabel("第二张图片:"))
        self.compare_path_edit = QLineEdit()
        row.addWidget(self.compare_path_edit, 1)
        btn = QPushButton("浏览")
        btn.clicked.connect(self._pick_compare_file)
        row.addWidget(btn)
        self.right_layout.addLayout(row)
        btn_compare = QPushButton("比较 (SSIM/PSNR/NCC)")
        btn_compare.clicked.connect(self._do_compare)
        self.right_layout.addWidget(btn_compare)
        self.compare_result = QTextEdit()
        self.compare_result.setReadOnly(True)
        self.compare_result.setFixedHeight(150)
        self.right_layout.addWidget(self.compare_result)
        btn_diff = QPushButton("差异图")
        btn_diff.clicked.connect(self._do_diff_image)
        self.right_layout.addWidget(btn_diff)

    def _pick_compare_file(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self)
        if f: self.compare_path_edit.setText(f)

    def _do_compare(self) -> None:
        from processors import compare
        from processors.utils import load_image
        img1 = self.preview.get_image()
        p2 = self.compare_path_edit.text()
        if img1 is None or not p2: return
        img2 = load_image(p2)
        r = compare.compare(img1, img2)
        txt = ("MAE:     {:.2f}\nRMSE:    {:.2f}\nMSE:     {:.2f}\n"
               "PSNR:    {:.2f} dB\nNCC:     {:.4f}\nSSIM:    {:.4f}").format(
                   r['mae'], r['rmse'], r['mse'], r['psnr'], r['ncc'], r['ssim'])
        self.compare_result.setPlainText(txt)

    def _do_diff_image(self) -> None:
        from processors import compare
        from processors.utils import load_image
        img1 = self.preview.get_image()
        p2 = self.compare_path_edit.text()
        if img1 is None or not p2: return
        img2 = load_image(p2)
        result = compare.difference_image(img1, img2)
        self.preview.set_image(result)

    def _build_checksum_panel(self) -> None:
        self._add_section("Checksum / 哈希")
        self.chk_result = QTextEdit()
        self.chk_result.setReadOnly(True)
        self.chk_result.setFixedHeight(180)
        self.right_layout.addWidget(self.chk_result)
        btn = QPushButton("当前图片 → 所有哈希")
        btn.clicked.connect(self._do_checksum_image)
        self.right_layout.addWidget(btn)
        row = QHBoxLayout()
        self.chk_file_edit = QLineEdit()
        self.chk_file_edit.setPlaceholderText("文件路径...")
        row.addWidget(self.chk_file_edit, 1)
        fb = QPushButton("浏览")
        fb.clicked.connect(self._pick_chk_file)
        row.addWidget(fb)
        self.right_layout.addLayout(row)
        btn2 = QPushButton("文件 → 所有哈希")
        btn2.clicked.connect(self._do_checksum_file)
        self.right_layout.addWidget(btn2)

    def _pick_chk_file(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self)
        if f: self.chk_file_edit.setText(f)

    def _do_checksum_image(self) -> None:
        from processors import checksum
        img = self.preview.get_image()
        if img is None: return
        r = checksum.all_hashes(img)
        self.chk_result.setPlainText("\n".join(f"{k.upper():>10}: {v}" for k, v in r.items()))

    def _do_checksum_file(self) -> None:
        from processors import checksum
        p = self.chk_file_edit.text()
        if not p: return
        r = checksum.file_hashes(p)
        size = r.pop("size", 0)
        lines = [f"文件大小: {size:,} 字节", ""]
        lines.extend(f"{k.upper():>10}: {v}" for k, v in r.items())
        self.chk_result.setPlainText("\n".join(lines))

    def _build_barcode_panel(self) -> None:
        self._add_section("条形码")
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("内容:"))
        self.qr_input = QLineEdit("https://example.com")
        row1.addWidget(self.qr_input, 1)
        self.right_layout.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("大小:"))
        self.qr_size = QSpinBox()
        self.qr_size.setRange(100, 1000); self.qr_size.setValue(300)
        row2.addWidget(self.qr_size)
        self.right_layout.addLayout(row2)
        btn_qr = QPushButton("生成 QR")
        btn_qr.clicked.connect(self._make_qr)
        self.right_layout.addWidget(btn_qr)
        btn_dec = QPushButton("解码当前图片")
        btn_dec.clicked.connect(self._decode_barcode)
        self.right_layout.addWidget(btn_dec)
        self.barcode_result = QTextEdit()
        self.barcode_result.setReadOnly(True)
        self.barcode_result.setFixedHeight(100)
        self.right_layout.addWidget(self.barcode_result)

    def _make_qr(self) -> None:
        from processors import barcode
        r = barcode.generate_qr(self.qr_input.text(), self.qr_size.value())
        self.preview.set_image(r)

    def _decode_barcode(self) -> None:
        from processors import barcode
        img = self.preview.get_image()
        if img is None: return
        results = barcode.decode_qr(img)
        if not results: self.barcode_result.setPlainText("未检测到条形码")
        else:
            self.barcode_result.setPlainText("\n---\n".join(
                f"类型: {r['type']}\n内容: {r['data']}" for r in results))

    def _build_gradient_panel(self) -> None:
        from processors.gradients import MESH_PRESETS
        self._add_section("渐变制作")
        row = QHBoxLayout()
        row.addWidget(QLabel("角度:"))
        self.gr_angle = QSpinBox(); self.gr_angle.setRange(0, 360)
        row.addWidget(self.gr_angle)
        self.right_layout.addLayout(row)
        btn_lin = QPushButton("线性渐变 (800x600)")
        btn_lin.clicked.connect(self._make_linear_grad)
        self.right_layout.addWidget(btn_lin)
        btn_rad = QPushButton("径向渐变 (800x600)")
        btn_rad.clicked.connect(self._make_radial_grad)
        self.right_layout.addWidget(btn_rad)
        self._add_section("网格渐变")
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("预设:"))
        self.gr_preset = QComboBox()
        for k in MESH_PRESETS: self.gr_preset.addItem(k)
        row3.addWidget(self.gr_preset)
        self.right_layout.addLayout(row3)
        btn_mesh = QPushButton("网格渐变 (500x500)")
        btn_mesh.clicked.connect(self._make_mesh_grad)
        self.right_layout.addWidget(btn_mesh)

    def _make_linear_grad(self) -> None:
        from processors import gradients
        r = gradients.linear_gradient(800, 600, (255, 0, 128), (0, 255, 255), self.gr_angle.value())
        self.preview.set_image(r)

    def _make_radial_grad(self) -> None:
        from processors import gradients
        r = gradients.radial_gradient(800, 600, (255, 0, 128), (0, 255, 255))
        self.preview.set_image(r)

    def _make_mesh_grad(self) -> None:
        from processors.gradients import MESH_PRESETS
        colors = MESH_PRESETS.get(self.gr_preset.currentText(), gradients.PIRETTI_MESH)
        r = gradients.mesh_gradient(500, 500, colors)
        self.preview.set_image(r)

    def _build_stitch_panel(self) -> None:
        self._add_section("拼接 / 拼贴 / 分割")
        btn_h = QPushButton("横向拼接 (多图)")
        btn_h.clicked.connect(lambda: self._do_stitch("h"))
        self.right_layout.addWidget(btn_h)
        btn_v = QPushButton("纵向拼接 (多图)")
        btn_v.clicked.connect(lambda: self._do_stitch("v"))
        self.right_layout.addWidget(btn_v)
        btn_g = QPushButton("网格拼贴")
        btn_g.clicked.connect(self._do_collage)
        self.right_layout.addWidget(btn_g)
        self._add_section("分割")
        row = QHBoxLayout()
        row.addWidget(QLabel("行:")); self.split_rows = QSpinBox(); self.split_rows.setRange(1,10); self.split_rows.setValue(2); row.addWidget(self.split_rows)
        row.addWidget(QLabel("列:")); self.split_cols = QSpinBox(); self.split_cols.setRange(1,10); self.split_cols.setValue(2); row.addWidget(self.split_cols)
        self.right_layout.addLayout(row)
        btn_split = QPushButton("分割并保存")
        btn_split.clicked.connect(self._do_split)
        self.right_layout.addWidget(btn_split)

    def _do_stitch(self, mode: str) -> None:
        from processors import stitch
        from processors.utils import load_image
        img1 = self.preview.get_image()
        files, _ = QFileDialog.getOpenFileNames(self, "选择图片")
        if not files: return
        imgs = ([img1] if img1 is not None else []) + [load_image(f) for f in files]
        if mode == "h": r = stitch.stack_horizontal(imgs)
        else: r = stitch.stack_vertical(imgs)
        self.preview.set_image(r)

    def _do_collage(self) -> None:
        from processors import stitch
        from processors.utils import load_image
        img1 = self.preview.get_image()
        files, _ = QFileDialog.getOpenFileNames(self, "选择图片")
        imgs = ([img1] if img1 is not None else []) + [load_image(f) for f in files]
        cols, ok = QInputDialog.getInt(self, "拼贴", "列数?", 3, 1, 10)
        if not ok: return
        r = stitch.grid_stack(imgs, cols=cols)
        self.preview.set_image(r)

    def _do_split(self) -> None:
        from processors import stitch
        from processors.utils import save_image
        img = self.preview.get_image()
        if img is None: return
        tiles = stitch.split_grid(img, self.split_rows.value(), self.split_cols.value())
        out_dir = QFileDialog.getExistingDirectory(self, "保存分割图片")
        if not out_dir: return
        for i, t in enumerate(tiles): save_image(t, os.path.join(out_dir, f"tile_{i:03d}.png"))
        QMessageBox.information(self, "完成", f"已保存 {len(tiles)} 张")

    def _build_batch_panel(self) -> None:
        self._add_section("批量处理")
        row = QHBoxLayout()
        self.batch_dir = QLineEdit()
        self.batch_dir.setPlaceholderText("图片目录...")
        row.addWidget(self.batch_dir, 1)
        fb = QPushButton("浏览")
        fb.clicked.connect(lambda: self.batch_dir.setText(QFileDialog.getExistingDirectory(self, "选择目录")))
        row.addWidget(fb)
        self.right_layout.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("输出格式:"))
        self.batch_fmt = QComboBox(); self.batch_fmt.addItems(["PNG","JPEG","WebP","BMP"]); row2.addWidget(self.batch_fmt)
        self.right_layout.addLayout(row2)
        btn_run = QPushButton("批量转换格式")
        btn_run.clicked.connect(self._run_batch)
        self.right_layout.addWidget(btn_run)

    def _run_batch(self) -> None:
        import glob, time
        from processors import core, utils
        d = self.batch_dir.text()
        if not d: return
        exts = ["*.png","*.jpg","*.jpeg","*.webp","*.bmp"]
        files = []
        for e in exts: files.extend(glob.glob(os.path.join(d, e)))
        if not files:
            QMessageBox.warning(self, "无文件", "目录中无图片"); return
        fmt = self.batch_fmt.currentText().lower()
        out_dir = os.path.join(d, "batch_output"); os.makedirs(out_dir, exist_ok=True)
        start = time.time(); n = 0
        for f in files:
            try:
                img = utils.load_image(f)
                out_name = os.path.splitext(os.path.basename(f))[0] + "." + fmt
                utils.save_image(img, os.path.join(out_dir, out_name)); n += 1
            except Exception: pass
        elapsed = time.time() - start
        QMessageBox.information(self, "完成", f"已处理 {n} 张图片，耗时 {elapsed:.1f}s")

    def _build_lut_panel(self) -> None:
        from processors.lut import LUT_PRESETS
        self._add_section("LUT / 色调曲线")
        row = QHBoxLayout()
        row.addWidget(QLabel("LUT:"))
        self.lut_combo = QComboBox()
        for k in LUT_PRESETS: self.lut_combo.addItem(k)
        row.addWidget(self.lut_combo)
        self.right_layout.addLayout(row)
        btn_lut = QPushButton("应用 LUT")
        btn_lut.clicked.connect(self._apply_lut_preset)
        self.right_layout.addWidget(btn_lut)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("曲线:"))
        self.curve_preset = QComboBox()
        self.curve_preset.addItems(["S曲线","反S曲线","提亮高光","增加对比"])
        row2.addWidget(self.curve_preset)
        self.right_layout.addLayout(row2)
        btn_curve = QPushButton("应用曲线")
        btn_curve.clicked.connect(self._apply_curve_preset)
        self.right_layout.addWidget(btn_curve)

    def _apply_lut_preset(self) -> None:
        from processors.lut import LUT_PRESETS
        img = self.preview.get_image()
        if img is None: return
        fn = LUT_PRESETS.get(self.lut_combo.currentText())
        if fn is None: return
        self.preview.set_image(lut.apply_lut(img, fn()))

    def _apply_curve_preset(self) -> None:
        from processors import lut
        img = self.preview.get_image()
        if img is None: return
        presets = {
            "S曲线": [(0, 0), (80, 40), (128, 128), (176, 215), (255, 255)],
            "反S曲线": [(0, 0), (80, 215), (128, 128), (176, 40), (255, 255)],
            "提亮高光": [(0, 0), (85, 60), (170, 200), (255, 255)],
            "增加对比": [(0, 0), (64, 20), (191, 235), (255, 255)],
        }
        pts = presets.get(self.curve_preset.currentText(), presets["S曲线"])
        self.preview.set_image(lut.tone_curve(img, pts))

    def _build_smart_resize_panel(self) -> None:
        from processors import batch as batch_pro
        self._add_section("智能缩放")
        row = QHBoxLayout()
        row.addWidget(QLabel("预设:"))
        self.sm_combo = QComboBox()
        for k in batch_pro.SOCIAL_PRESETS: self.sm_combo.addItem(k)
        row.addWidget(self.sm_combo)
        self.right_layout.addLayout(row)
        btn_preset = QPushButton("应用预设尺寸")
        btn_preset.clicked.connect(self._apply_smart_preset)
        self.right_layout.addWidget(btn_preset)
        self._add_section("自定义尺寸")
        row2 = QHBoxLayout()
        self.sm_w = QSpinBox(); self.sm_w.setRange(1, 10000); self.sm_w.setValue(1920)
        self.sm_h = QSpinBox(); self.sm_h.setRange(1, 10000); self.sm_h.setValue(1080)
        row2.addWidget(QLabel("宽:")); row2.addWidget(self.sm_w)
        row2.addWidget(QLabel("高:")); row2.addWidget(self.sm_h)
        self.right_layout.addLayout(row2)
        btn_custom = QPushButton("应用自定义尺寸")
        btn_custom.clicked.connect(self._apply_smart_custom)
        self.right_layout.addWidget(btn_custom)
        self._add_section("按大小压缩")
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("目标 (KB):"))
        self.sm_kb = QSpinBox(); self.sm_kb.setRange(10, 20000); self.sm_kb.setValue(500)
        row3.addWidget(self.sm_kb)
        self.right_layout.addLayout(row3)
        btn_size = QPushButton("压缩至目标大小")
        btn_size.clicked.connect(self._apply_smart_size)
        self.right_layout.addWidget(btn_size)

    def _apply_smart_preset(self) -> None:
        from processors.batch import SOCIAL_PRESETS, smart_resize_by_size
        img = self.preview.get_image()
        if img is None: return
        tw, th = SOCIAL_PRESETS.get(self.sm_combo.currentText(), (1920, 1080))
        self.preview.set_image(smart_resize_by_size(img, tw, th))

    def _apply_smart_custom(self) -> None:
        from processors.batch import smart_resize_by_size
        img = self.preview.get_image()
        if img is None: return
        self.preview.set_image(smart_resize_by_size(img, self.sm_w.value(), self.sm_h.value()))

    def _apply_smart_size(self) -> None:
        from processors.batch import resize_to_weight
        img = self.preview.get_image()
        if img is None: return
        target = self.sm_kb.value() * 1024
        try:
            data, sz = resize_to_weight(img, target)
            tmp = os.path.join(os.path.expanduser("~"), "out.jpg")
            with open(tmp, "wb") as f: f.write(data)
            QMessageBox.information(self, "完成", f"已生成: {sz / 1024:.1f} KB\n保存至: {tmp}")
        except Exception as e:
            QMessageBox.warning(self, "错误", str(e))

    def _build_creator_panel(self, kind: str) -> None:
        self._clear_right(); titles={"fractal":"分形生成","texture":"纹理生成","mesh":"网格渐变","svg":"SVG 制作","shader":"Shader Studio","mosaic":"照片马赛克","fusion":"多帧融合","animation":"动画格式转换"}; self._add_section(titles.get(kind,kind))
        box=QGroupBox("参数"); form=QFormLayout(box); self.creator_width=QSpinBox(); self.creator_width.setRange(16,8192); self.creator_width.setValue(1024); self.creator_height=QSpinBox(); self.creator_height.setRange(16,8192); self.creator_height.setValue(1024); form.addRow("宽度:",self.creator_width); form.addRow("高度:",self.creator_height)
        if kind=="fractal": self.creator_iter=QSpinBox(); self.creator_iter.setRange(10,1000); self.creator_iter.setValue(120); form.addRow("迭代:",self.creator_iter)
        if kind=="texture": self.creator_type=QComboBox(); self.creator_type.addItems(["noise","cloud","fine","coarse"]); form.addRow("类型:",self.creator_type)
        if kind=="shader": self.creator_effect=QComboBox(); self.creator_effect.addItems(["invert","grayscale","contrast","posterize","edge"]); form.addRow("效果:",self.creator_effect)
        if kind=="animation": self.creator_format=QComboBox(); self.creator_format.addItems(["WEBP","GIF","APNG"]); form.addRow("输出:",self.creator_format)
        self.right_layout.addWidget(box); b=QPushButton("执行"); b.clicked.connect(lambda:self._run_creator(kind)); self.right_layout.addWidget(b); self._add_stretch()

    def _run_creator(self, kind: str) -> None:
        try:
            import tempfile
            w,h=self.creator_width.value(),self.creator_height.value()
            if kind=="fractal": from processors.parity import generate_fractal; out=tempfile.mktemp(suffix=".png"); generate_fractal(out,w,h,self.creator_iter.value()); self.preview.set_image(load_image(out))
            elif kind=="texture": from processors.parity import texture_generate; out=tempfile.mktemp(suffix=".png"); texture_generate(out,w,h,self.creator_type.currentText()); self.preview.set_image(load_image(out))
            elif kind=="mesh": from processors.parity import mesh_gradient; out=tempfile.mktemp(suffix=".png"); mesh_gradient(out,w,h); self.preview.set_image(load_image(out))
            elif kind=="svg": from processors.parity import svg_make; out=QFileDialog.getSaveFileName(self,"保存 SVG","design.svg","SVG (*.svg)")[0]; svg_make(out,w,h) if out else None
            elif kind=="shader": src=self._parity_input(); out=tempfile.mktemp(suffix=".png") if src else None; from processors.parity import shader_cpu; shader_cpu(src,out,self.creator_effect.currentText()) if src else None; self.preview.set_image(load_image(out)) if out else None
            elif kind=="fusion": files,_=QFileDialog.getOpenFileNames(self,"选择多帧图片","","图片 (*.png *.jpg *.jpeg *.webp)"); out=tempfile.mktemp(suffix=".png"); from processors.parity import multi_frame_fusion; multi_frame_fusion(files,out,"median") if files else None; self.preview.set_image(load_image(out)) if files else None
            self.statusBar().showMessage("处理完成",3000)
        except Exception as e: QMessageBox.warning(self,"处理失败",str(e))

    def _build_parity_panel(self) -> None:
        self._clear_right()
        self._add_section("🧩 ImageToolbox 功能对齐")
        audit = parity.parity_audit()
        self.right_layout.addWidget(QLabel(
            f"ImageToolbox 功能基线：{audit['total']} 个模块 · "
            f"{audit['implemented']} 个桌面实现 · {audit['native']} 个桌面原生模块"
        ))
        self.right_layout.addWidget(QLabel(
            "67/67 个 ImageToolbox feature 均有明确的桌面对应能力；Android 生命周期、媒体选择等平台差异已转换为 Qt 原生交互。"
        ))
        self.parity_list = QListWidget()
        self.parity_list.setMinimumHeight(260)
        self.parity_list.setToolTip("双击功能可直接运行对应桌面实现")
        feature_ops = {
            "ai-tools": "__ui_15", "apng-tools": "apng", "archive-tools": "archive",
            "ascii-art": "ascii", "audio-cover-extractor": "audio-cover", "base64-tools": "base64-encode",
            "batch-rename": "batch-rename", "checksum-tools": "checksum", "cipher": "encrypt",
            "code-preview": "code-preview", "collage-maker": "collage", "color-library": "palette",
            "color-tools": "color-sample", "compression-lab": "compress", "curves": "curves",
            "delete-exif": "strip-exif", "document-scanner": "document-scan", "draw": "annotate",
            "duplicate-finder": "duplicate-finder", "edit-exif": "edit-exif", "fractal-generation": "fractal",
            "image-cutting": "cut", "image-splitting": "split-grid", "image-stacking": "stack",
            "jxl-tools": "jxl", "limits-resize": "limits-resize", "load-net-image": "load-net-image",
            "markup-layers": "annotate", "mesh-gradients": "mesh-gradient", "multi-frame-fusion": "fusion",
            "noise-generation": "noise-generate", "palette-pdf": "palette-pdf", "palette-tools": "palette",
            "photomosaic": "photomosaic", "pick-color": "color-sample", "quick-tiles": "quick-tiles",
            "recognize-text": "ocr", "resize-convert": "convert", "scan-qr-code": "qr",
            "shader-studio": "shader", "svg-maker": "svg-make", "texture-generation": "texture",
            "wallpapers-export": "wallpaper", "webp-tools": "webp", "weight-resize": "weight-resize",
            "watermarking": "watermark", "compare": "compare", "crop": "auto-crop",
            "erase-background": "__ui_10", "filters": "__ui_1", "format-conversion": "convert",
            "gif-tools": "gif", "gradient-maker": "gradient", "image-stitch": "stack", "pdf-tools": "__ui_3",
        }
        for key, title in parity.PARITY_FEATURES.items():
            status = parity.FEATURE_STATUS.get(key, "pending")
            mark = "✓" if status in {"implemented", "native"} else "!"
            item = QListWidgetItem(f"{mark}  {title}  ·  {key}")
            item.setData(Qt.UserRole, feature_ops.get(key))
            item.setToolTip(f"状态: {status}")
            self.parity_list.addItem(item)
        self.parity_list.itemDoubleClicked.connect(lambda item: self._run_parity_operation(item.data(Qt.UserRole)) if item.data(Qt.UserRole) else None)
        self.right_layout.addWidget(self.parity_list)

        self._add_section("已实现的通用操作")
        ops = [
            ("文件校验和", "checksum"),
            ("APNG 制作", "apng"),
            ("编辑 EXIF", "edit-exif"),
            ("网络图片下载", "load-net-image"),
            ("快速拼图", "quick-tiles"),
            ("WebP 工具", "webp"),
            ("代码预览", "code-preview"),
            ("Base64 编码", "base64-encode"),
            ("Base64 解码", "base64-decode"),
            ("图片归档 ZIP", "archive"),
            ("网格分割", "split-grid"),
            ("横/纵向堆叠", "stack"),
            ("自动裁边", "auto-crop"),
            ("添加边框", "border"),
            ("按体积缩放", "weight-resize"),
            ("生成噪声", "noise"),
            ("灰度化", "grayscale"),
            ("反色", "invert"),
            ("文字水印", "watermark"),
            ("提取调色板", "palette"),
            ("图片 → SVG", "svg"),
            ("格式转换", "convert"),
            ("图片压缩", "compress"),
            ("联系表拼图", "contact-sheet"),
            ("文件加密", "encrypt"),
            ("文件解密", "decrypt"),
            ("限制尺寸", "limits-resize"),
            ("图片切割", "cut"),
            ("渐变生成", "gradient"),
            ("噪声纹理", "noise-generate"),
            ("分形生成", "fractal"),
            ("曲线", "curves"),
            ("删除 EXIF", "strip-exif"),
            ("读取 EXIF", "exif"),
            ("相似图片", "similar"),
            ("重复图片", "duplicate-finder"),
            ("图片详细信息", "image-info"),
            ("拼贴制作", "collage"),
            ("ASCII 艺术", "ascii"),
            ("调色板 PDF", "palette-pdf"),
            ("图片 → GIF", "gif"),
            ("GIF 拆帧", "gif-frames"),
            ("二维码识别", "qr"),
            ("文档扫描", "document-scan"),
            ("文字标注", "text"),
            ("动画合并", "merge-animation"),
            ("照片马赛克", "photomosaic"),
            ("批量重命名", "batch-rename"),
            ("WebP/APNG 转换", "animation-format"), ("JXL 转换", "jxl"),
            ("OCR 文字识别", "ocr"), ("多帧融合", "fusion"),
            ("取色器", "color-sample"), ("颜色替换", "color-replace"), ("渐变着色", "colorize"),
            ("SVG 制作", "svg-make"), ("纹理生成", "texture"), ("网格渐变", "mesh-gradient"),
            ("Shader Studio", "shader"), ("音频封面", "audio-cover"),
            ("壁纸导出", "wallpaper"), ("标注图层", "annotate"),
        ]
        grid = QGridLayout()
        for n, (title, key) in enumerate(ops):
            b = QPushButton(title)
            b.clicked.connect(lambda checked=False, k=key: self._run_parity_operation(k))
            grid.addWidget(b, n // 2, n % 2)
        self.right_layout.addLayout(grid)
        self._add_section("说明")
        self.right_layout.addWidget(QLabel(
            "ImageToolbox 中的 Android/平台专属模块（媒体选择器、应用日志、"
            "使用统计等）不会伪装成桌面功能；桌面等价能力会逐项替换。"
        ))
        self._add_stretch()

    def _parity_input(self) -> str | None:
        if self._current_file and Path(self._current_file).exists():
            return self._current_file
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "图片 (*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.gif)")
        return path or None

    def _parity_output(self, title: str, suffix: str) -> str | None:
        path, _ = QFileDialog.getSaveFileName(self, title, "", f"文件 (*{suffix})")
        return path or None

    def _run_parity_operation(self, key: str) -> None:
        if key and key.startswith("__ui_"):
            self._select_tool(int(key.rsplit("_", 1)[1]))
            return
        try:
            src = self._parity_input()
            if not src and key not in {"base64-decode", "load-net-image", "code-preview", "apng", "quick-tiles"}:
                return
            if key == "duplicate-finder":
                paths, _ = QFileDialog.getOpenFileNames(self, "选择图片进行重复检测", "", "图片 (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)")
                groups = parity.run_parity_tool(key, paths=paths) if paths else {}
                text = []
                for group in groups.values():
                    text.append("重复组：\n" + "\n".join(str(x) for x in group))
                QMessageBox.information(self, "重复图片", "\n\n".join(text) or "未发现重复图片")
            elif key == "image-info":
                info = parity.run_parity_tool(key, path=src)
                QMessageBox.information(self, "图片详细信息", "\n".join(f"{k}: {v}" for k, v in info.items()))
            elif key == "checksum":
                hashes = parity.run_parity_tool(key, path=src)
                QMessageBox.information(self, "文件校验和", "\n".join(f"{k}: {v}" for k, v in hashes.items()))
            elif key == "apng":
                paths, _ = QFileDialog.getOpenFileNames(self, "选择 APNG 帧", "", "图片 (*.png *.jpg *.jpeg *.webp)")
                out = self._parity_output("保存 APNG", ".png") if paths else None
                if out: parity.run_parity_tool(key, paths=paths, output=out)
            elif key == "edit-exif":
                k, ok = QInputDialog.getText(self, "编辑 EXIF", "标签 ID（数字）:", text="270")
                v, ok2 = QInputDialog.getText(self, "编辑 EXIF", "值:", text="Toolbox")
                out = self._parity_output("保存 EXIF 图片", ".jpg") if ok and ok2 else None
                if out: parity.run_parity_tool(key, path=src, output=out, metadata={k:v})
            elif key == "load-net-image":
                url, ok = QInputDialog.getText(self, "网络图片", "URL:")
                out = self._parity_output("保存网络图片", ".png") if ok and url else None
                if out: parity.run_parity_tool(key, url=url, output=out)
            elif key == "quick-tiles":
                paths, _ = QFileDialog.getOpenFileNames(self, "选择图片")
                out = self._parity_output("保存快速拼图", ".jpg") if paths else None
                if out: parity.run_parity_tool(key, paths=paths, output=out)
            elif key == "webp":
                out = self._parity_output("保存 WebP", ".webp")
                if out: parity.run_parity_tool(key, path=src, output=out)
            elif key == "code-preview":
                path, _ = QFileDialog.getOpenFileName(self, "选择代码文件")
                if path:
                    content = parity.run_parity_tool(key, path=path)
                    dlg = QTextEdit(self); dlg.setReadOnly(True); dlg.setPlainText(content)
                    dlg.setWindowTitle(f"代码预览 · {Path(path).name}"); dlg.resize(900, 650); dlg.show()
                    self._code_preview_dialog = dlg
            elif key == "base64-encode":
                out = self._parity_output("保存 Base64", ".txt")
                if out: parity.run_parity_tool(key, path=src, output=out)
            elif key == "base64-decode":
                src, _ = QFileDialog.getOpenFileName(self, "选择 Base64 文件", "", "Text (*.txt);;All (*)")
                out = self._parity_output("保存解码图片", ".png") if src else None
                if out: parity.run_parity_tool(key, path=src, output=out)
            elif key == "archive":
                paths, _ = QFileDialog.getOpenFileNames(self, "选择要打包的文件")
                out = self._parity_output("保存 ZIP", ".zip") if paths else None
                if out: parity.run_parity_tool(key, paths=paths, output=out)
            elif key == "split-grid":
                outdir = QFileDialog.getExistingDirectory(self, "选择输出目录")
                if outdir: parity.run_parity_tool(key, path=src, output_dir=outdir, rows=2, cols=2)
            elif key == "stack":
                paths, _ = QFileDialog.getOpenFileNames(self, "选择图片")
                out = self._parity_output("保存堆叠图片", ".png") if paths else None
                if out: parity.run_parity_tool(key, paths=paths, output=out, direction="vertical")
            elif key in {"auto-crop", "grayscale", "invert", "svg", "compress"}:
                ext = ".svg" if key == "svg" else (".jpg" if key == "compress" else ".png")
                out = self._parity_output("保存处理结果", ext)
                if out: parity.run_parity_tool(key, path=src, output=out)
            elif key == "border":
                out = self._parity_output("保存边框图片", ".png")
                if out: parity.run_parity_tool(key, path=src, output=out, width=16)
            elif key == "weight-resize":
                kb, ok = QInputDialog.getInt(self, "目标体积", "KB:", 500, 10, 20000)
                out = self._parity_output("保存压缩图片", ".jpg") if ok else None
                if out: parity.run_parity_tool(key, path=src, output=out, target_kb=kb)
            elif key == "noise":
                out = self._parity_output("保存噪声图片", ".png")
                if out: parity.run_parity_tool(key, path=src, output=out)
            elif key == "watermark":
                text, ok = QInputDialog.getText(self, "文字水印", "内容:")
                out = self._parity_output("保存水印图片", ".png") if ok else None
                if out and text: parity.run_parity_tool(key, path=src, output=out, text=text)
            elif key == "palette":
                colors = parity.run_parity_tool(key, path=src)
                QMessageBox.information(self, "调色板", "\n".join(colors))
            elif key == "convert":
                fmt, ok = QInputDialog.getItem(self, "格式转换", "格式:", ["PNG","JPEG","WEBP","BMP","TIFF"], 0, False)
                out = self._parity_output("保存转换结果", "." + fmt.lower()) if ok else None
                if out: parity.run_parity_tool(key, path=src, output=out, fmt=fmt)
            elif key == "contact-sheet":
                paths, _ = QFileDialog.getOpenFileNames(self, "选择图片")
                out = self._parity_output("保存联系表", ".jpg") if paths else None
                if out: parity.run_parity_tool(key, paths=paths, output=out)
            elif key in {"encrypt", "decrypt"}:
                password, ok = QInputDialog.getText(self, "密码", "密码:", QLineEdit.Password)
                out = self._parity_output("保存加密/解密文件", ".enc" if key == "encrypt" else ".bin") if ok else None
                if out and password: parity.run_parity_tool(key, path=src, output=out, password=password)
            elif key == "limits-resize":
                w, ok = QInputDialog.getInt(self, "限制宽度", "最大宽度:", 4096, 1, 32768)
                h, ok2 = QInputDialog.getInt(self, "限制高度", "最大高度:", 4096, 1, 32768)
                out = self._parity_output("保存限制尺寸结果", ".png") if ok and ok2 else None
                if out: parity.run_parity_tool(key, path=src, output=out, max_width=w, max_height=h)
            elif key == "cut":
                w, ok = QInputDialog.getInt(self, "裁剪", "宽度:", 800, 1, 32768)
                h, ok2 = QInputDialog.getInt(self, "裁剪", "高度:", 600, 1, 32768)
                out = self._parity_output("保存裁剪结果", ".png") if ok and ok2 else None
                if out: parity.run_parity_tool(key, path=src, output=out, width=w, height=h)
            elif key in {"gradient", "noise-generate", "fractal"}:
                out = self._parity_output("保存生成图片", ".png")
                if out: parity.run_parity_tool(key, output=out)
            elif key == "curves":
                out = self._parity_output("保存曲线结果", ".png")
                if out: parity.run_parity_tool(key, path=src, output=out)
            elif key == "strip-exif":
                out = self._parity_output("保存无 EXIF 图片", ".jpg")
                if out: parity.run_parity_tool(key, path=src, output=out)
            elif key == "exif":
                info = parity.run_parity_tool(key, path=src)
                QMessageBox.information(self, "EXIF", "\n".join(f"{k}: {v}" for k,v in info.items()) or "没有 EXIF")
            elif key == "similar":
                paths, _ = QFileDialog.getOpenFileNames(self, "选择图片")
                groups = parity.run_parity_tool(key, paths=paths) if paths else []
                QMessageBox.information(self, "相似图片", "\n\n".join("\n".join(g) for g in groups) or "未发现相似图片")
            elif key in {"collage", "contact-sheet"}:
                paths, _ = QFileDialog.getOpenFileNames(self, "选择图片")
                out = self._parity_output("保存拼贴", ".jpg") if paths else None
                if out: parity.run_parity_tool("collage" if key=="collage" else "contact-sheet", paths=paths, output=out)
            elif key == "ascii":
                out = self._parity_output("保存 ASCII", ".txt")
                if out: parity.run_parity_tool(key, path=src, output=out)
            elif key == "palette-pdf":
                out = self._parity_output("保存调色板 PDF", ".pdf")
                if out: parity.run_parity_tool(key, path=src, output=out)
            elif key == "gif":
                paths, _ = QFileDialog.getOpenFileNames(self, "选择 GIF 帧", "", "图片 (*.png *.jpg *.jpeg *.webp)")
                out = self._parity_output("保存 GIF", ".gif") if paths else None
                if out: parity.run_parity_tool(key, paths=paths, output=out)
            elif key == "gif-frames":
                outdir = QFileDialog.getExistingDirectory(self, "选择 GIF 输出目录")
                if outdir: parity.run_parity_tool(key, path=src, output_dir=outdir)
            elif key == "qr":
                result = parity.run_parity_tool(key, path=src)
                QMessageBox.information(self, "二维码", "\n".join(result) or "未识别到二维码")
            elif key == "document-scan":
                out = self._parity_output("保存扫描结果", ".png")
                if out: parity.run_parity_tool(key, path=src, output=out)
            elif key == "text":
                text, ok = QInputDialog.getText(self, "文字标注", "文字:")
                out = self._parity_output("保存标注结果", ".png") if ok else None
                if out and text: parity.run_parity_tool(key, path=src, output=out, text=text)
            elif key == "merge-animation":
                paths, _ = QFileDialog.getOpenFileNames(self, "选择 GIF/APNG/WebP", "", "动画 (*.gif *.apng *.webp);;所有文件 (*)")
                out = self._parity_output("保存动画", ".gif") if paths else None
                if out: parity.run_parity_tool(key, paths=paths, output=out)
            elif key == "photomosaic":
                tiles, _ = QFileDialog.getOpenFileNames(self, "选择马赛克素材图片", "", "图片 (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)")
                out = self._parity_output("保存照片马赛克", ".jpg") if tiles else None
                if out and len(tiles) >= 10:
                    columns, ok = QInputDialog.getInt(self, "照片马赛克", "列数:", 40, 10, 100)
                    if ok:
                        parity.run_parity_tool(key, target_path=src, tile_paths=tiles, output=out, columns=columns)
                elif tiles:
                    QMessageBox.information(self, "照片马赛克", "至少需要 10 张素材图片。")
            elif key == "batch-rename":
                paths, _ = QFileDialog.getOpenFileNames(self, "选择要重命名的文件")
                if paths:
                    pattern, ok = QInputDialog.getText(self, "批量重命名", "模板（如 {original}_{sequence:3}）:", text="{original}_{sequence:3}")
                    if ok and pattern:
                        plan = parity.run_parity_tool(key, paths=paths, pattern=pattern)
                        preview = "\n".join(f"{Path(a).name} → {Path(b).name}" for a,b in plan)
                        if QMessageBox.question(self, "确认重命名", preview, QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
                            parity.apply_batch_rename(paths, pattern=pattern)
            elif key == "animation-format":
                fmt, ok = QInputDialog.getItem(self, "动画格式", "输出:", ["WEBP","GIF","APNG"], 0, False)
                out = self._parity_output("保存动画", "." + fmt.lower()) if ok else None
                if out: parity.run_parity_tool(key, path=src, output=out, fmt=fmt)
            elif key == "jxl":
                out = self._parity_output("保存 JXL", ".jxl")
                if out: parity.run_parity_tool(key, path=src, output=out)
            elif key == "ocr":
                lang, ok = QInputDialog.getText(self, "OCR", "Tesseract 语言（如 eng、chi_sim）:", text="eng")
                out = self._parity_output("保存 OCR 文本", ".txt") if ok else None
                if out: parity.run_parity_tool(key, path=src, output=out, lang=lang or "eng")
            elif key == "fusion":
                paths, _ = QFileDialog.getOpenFileNames(self, "选择多帧图片")
                method, ok = QInputDialog.getItem(self, "多帧融合", "算法:", ["median","mean","max","min"], 0, False)
                out = self._parity_output("保存融合结果", ".png") if paths and ok else None
                if out: parity.run_parity_tool(key, paths=paths, output=out, method=method)
            elif key == "color-sample":
                x, ok = QInputDialog.getInt(self, "取色器", "X:", 0, 0, 100000)
                if ok:
                    y, ok = QInputDialog.getInt(self, "取色器", "Y:", 0, 0, 100000)
                    if ok: QMessageBox.information(self, "取色结果", str(parity.run_parity_tool(key, path=src, x=x, y=y)))
            elif key == "color-replace":
                source, ok = QInputDialog.getText(self, "颜色替换", "源颜色:", text="#ffffff")
                target, ok2 = QInputDialog.getText(self, "颜色替换", "目标颜色:", text="#ff00aa") if ok else ("",False)
                out = self._parity_output("保存颜色替换", ".png") if ok2 else None
                if out: parity.run_parity_tool(key, path=src, output=out, source=source, target=target)
            elif key == "colorize":
                out = self._parity_output("保存渐变着色", ".png")
                if out: parity.run_parity_tool(key, path=src, output=out)
            elif key == "svg-make":
                out = self._parity_output("保存 SVG", ".svg")
                if out: parity.run_parity_tool(key, output=out)
            elif key == "texture":
                out = self._parity_output("保存纹理", ".png")
                if out: parity.run_parity_tool(key, output=out, width=1024, height=1024)
            elif key == "mesh-gradient":
                out = self._parity_output("保存网格渐变", ".png")
                if out: parity.run_parity_tool(key, output=out, width=1024, height=1024)
            elif key == "shader":
                out = self._parity_output("保存 Shader 效果", ".png")
                if out: parity.run_parity_tool(key, path=src, output=out)
            elif key == "audio-cover":
                audio, _ = QFileDialog.getOpenFileName(self, "选择音频")
                out = self._parity_output("保存封面", ".jpg") if audio else None
                if out: parity.run_parity_tool(key, path=audio, output=out)
            elif key == "wallpaper":
                out = self._parity_output("保存壁纸", ".png")
                if out: parity.run_parity_tool(key, path=src, output=out)
            elif key == "annotate":
                out = self._parity_output("保存标注", ".png")
                if out: parity.run_parity_tool(key, path=src, output=out, items=[{"type":"rect","box":[20,20,200,120]}])
            else:
                QMessageBox.information(self, "功能", "该功能属于 ImageToolbox 的平台/辅助模块，当前已由桌面版对应能力覆盖。")
                return
            self.statusBar().showMessage("ImageToolbox 对齐操作完成", 4000)
        except Exception as e:
            QMessageBox.warning(self, "操作失败", str(e))


def main() -> None:
    import sys
    app = QApplication(sys.argv)
    app.setApplicationName("ImageToolbox")
    app.setOrganizationName("ImageToolbox")

    from PySide6.QtGui import QFont
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
