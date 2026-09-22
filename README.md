# Toolbox

Linux 原生桌面图像工具箱，基于 Python + PySide6，目标是将 ImageToolbox 的核心图像处理能力转化为适合 Linux 桌面的专业工作流。

## 环境

- Python 3.11+
- PySide6 6.6+
- Pillow / OpenCV / scikit-image
- 可选：Tesseract、libjxl-tools、G'MIC、ONNX Runtime 等

## 运行

```bash
cd /home/emo/code/toolbox
.venv/bin/python main.py
```

也可以：

```bash
QT_QPA_PLATFORM=wayland .venv/bin/python main.py
```

## 测试

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m py_compile app/*.py processors/*.py main.py
```

Qt 无头 UI smoke test：

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "from PySide6.QtWidgets import QApplication; from app.main_window import MainWindow; app=QApplication([]); w=MainWindow(); print('UI smoke OK'); w.close()"
```

## 当前工作区

主窗口由左侧工具导航、中央图片预览、右侧参数面板组成，并提供可停靠的任务队列和运行日志。窗口几何、Dock 布局以及主题模式通过 Qt QSettings 持久化。

主题支持：

- Dark
- Light
- System

`Ctrl+T` 循环切换主题。

## ImageToolbox 对齐

参考项目位于 `/home/emo/code/ImageToolbox`。当前 parity registry 与参考项目均为 67 个 feature module，但 registry 数字不代表 UX/参数已经完全等价。

高复杂度模块正在逐项升级为专业桌面面板，包括：

- 分形
- 纹理生成
- 网格渐变
- Shader Studio
- SVG 制作
- Photomosaic
- 多帧融合
- 动画格式转换
- 批量重命名
- OCR
- EXIF

详细审计矩阵见 `docs/parity-audit.md`。

## Git 工作流

当前开发分支：

`feature/toolbox-parity-ui-overhaul`

原则：小步提交、功能独立 commit、测试通过后再合并主分支。
