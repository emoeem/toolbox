import os

AI_PANELS = '''
    def _build_ai_remove_bg_panel(self) -> None:
        from processors.ai import BG_REMOVE_MODELS
        self._add_section("AI 智能抠图")
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
        btn_remove = QPushButton("🎯 一键抠图 (输出透明 PNG)")
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
            result = ai.remove_background(img, model=self.rmbg_model.currentData(),
                                          alpha_matting=self.rmbg_alpha_matting.isChecked())
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
            rgba = ai.remove_background(img, model=self.rmbg_model.currentData(),
                                        alpha_matting=self.rmbg_alpha_matting.isChecked())
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
        self._add_section("AI 智能放大")
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
        self.upscale_method.addItems(["Lanczos (快速)", "Bicubic", "AI 模型 (需模型)"])
        row2.addWidget(self.upscale_method)
        self.right_layout.addLayout(row2)
        btn = QPushButton("📈 执行 Upscale")
        btn.clicked.connect(self._ai_upscale)
        self.right_layout.addWidget(btn)
        self._add_section("信息: Lanczos 快速，AI 模型更精细但需要下载")

    def _ai_upscale(self) -> None:
        from processors import ai
        img = self.preview.current_image()
        if img is None: return
        factor = int(self.upscale_factor.currentText().replace("x", ""))
        method = self.upscale_method.currentText()
        self.statusBar().showMessage(f"Upscale {factor}x 中...", 0)
        QApplication.processEvents()
        try:
            if "Bicubic" in method:
                result = ai.upscale_cubic(img, factor)
            elif "AI" in method:
                result = ai.upscale_realesrgan(img, factor)
            else:
                result = ai.upscale_lanczos(img, factor)
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
        self.denoise_method.addItems(["NLM (推荐)", "双边滤波", "中值滤波", "小波式"])
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
        self._add_section("色彩风格化")
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
        btn_enhance = QPushButton("✨ AI 增强 (降噪+放大+饱和+对比)")
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

    def _build_ai_depth_panel(self) -> None:
        from processors.ai import DEPTH_MODELS
        self._add_section("AI 深度图")
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
        self._add_section("说明: 简单启发式无需下载任何模型")

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
                        f"模型 {key} 暂不可用，已用启发式替代。\n"
                        f"你可手动 rembg.new_session('{key}') 下载。")
                    result = ai.depth_map(img)
            self.preview.set_image(result)
            self.statusBar().showMessage("深度图完成", 3000)
        except Exception as e:
            self.statusBar().clearMessage()
            QMessageBox.warning(self, "失败", str(e))

'''

path = "/home/emo/code/toolbox/app/main_window.py"
with open(path) as f:
    content = f.read()

marker = '    def _show_about(self) -> None:'
old_marker = marker + '\n        QMessageBox.about(self, "关于", "Image Toolbox Python 桌面版\\n\\n基于 PySide6 + OpenCV\\n重构自 Android 开源项目")\n'
new_marker = marker + '\n        QMessageBox.about(self, "关于", "Image Toolbox Python 桌面版\\n\\n基于 PySide6 + OpenCV + rembg AI\\n重构自 Android 开源项目")\n'

content = content.replace(old_marker, new_marker)
content = content.replace(new_marker, new_marker + AI_PANELS)

with open(path, "w") as f:
    f.write(content)

import ast
ast.parse(content)
print("OK - AI panels appended and syntax validated")
