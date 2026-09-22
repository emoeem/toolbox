# Changelog

## 2026-09-22

### Added

- 建立 `feature/toolbox-parity-ui-overhaul` 开发分支与 Git 基线。
- 增加 ImageToolbox 67 个 feature 的桌面 parity 审计矩阵。
- 增加专业参数面板：分形、纹理、网格渐变、Shader、SVG、Photomosaic、多帧融合、动画转换。
- 增加批量重命名预览与安全执行。
- 增加可停靠任务队列、进度、暂停/继续、取消和运行日志。
- 增加窗口布局保存、恢复和重置。
- 增加 Dark / Light / System 主题与持久化设置。
- 增强 OCR：语言、页面布局和结果保存。
- 增强 EXIF：读取、编辑、删除。
- 增加 parity processor 回归测试。

### Verification

- `python -m unittest discover -s tests -v`：4/4 通过。
- PySide6 offscreen UI smoke：通过。
- `python -m py_compile app/*.py processors/*.py main.py`：通过。
