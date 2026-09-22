# ImageToolbox ↔ Toolbox 审计报告

审计时间：2026-09-22

## 阶段 0：项目概况

| 项目 | 技术栈 | 规模/入口 | Git |
|---|---|---|---|
| ImageToolbox | Kotlin + Jetpack Compose + Gradle | 67 feature modules | 独立 Git 仓库 |
| toolbox | Python + PySide6 + Pillow/OpenCV/scikit-image 等 | `main.py` + `app/main_window.py` | 本次新建 Git 基线 |

参考项目的 67 个 feature module 与 Toolbox parity registry 已逐项对齐，模块 ID 当前 67/67 完全覆盖。

## 阶段 1–2：功能对比矩阵

| 功能模块 | 参考实现规模 | Toolbox 当前状态 | 差异/验收重点 | 优先级 |
|---|---:|---|---|---|
| `ai-tools` | 44 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P0 |
| `apng-tools` | 8 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `archive-tools` | 13 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `ascii-art` | 6 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `audio-cover-extractor` | 7 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `base64-tools` | 6 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `batch-rename` | 17 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `checksum-tools` | 16 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `cipher` | 9 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `code-preview` | 10 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `collage-maker` | 3 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `color-library` | 3 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `color-tools` | 10 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `compression-lab` | 3 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `curves` | 4 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `delete-exif` | 4 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `document-scanner` | 2 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `draw` | 65 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P0 |
| `duplicate-finder` | 20 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `edit-exif` | 2 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `fractal-generation` | 25 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P0 |
| `image-cutting` | 9 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `image-splitting` | 8 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `image-stacking` | 9 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `jxl-tools` | 14 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `limits-resize` | 8 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `load-net-image` | 11 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `markup-layers` | 47 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P0 |
| `mesh-gradients` | 2 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `multi-frame-fusion` | 11 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `noise-generation` | 13 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `palette-pdf` | 9 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `palette-tools` | 15 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `photomosaic` | 11 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `pick-color` | 6 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `quick-tiles` | 7 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `recognize-text` | 39 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P0 |
| `resize-convert` | 2 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `scan-qr-code` | 22 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `shader-studio` | 9 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P0 |
| `single-edit` | 8 | 桌面原生等价 | Android 平台模块转换为 Qt/桌面机制；验证入口、持久化与行为即可 | P2 |
| `svg-maker` | 8 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `texture-generation` | 39 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P0 |
| `wallpapers-export` | 11 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `webp-tools` | 8 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `weight-resize` | 6 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `watermarking` | 17 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `app-logs` | 3 | 桌面原生等价 | Android 平台模块转换为 Qt/桌面机制；验证入口、持久化与行为即可 | P2 |
| `compare` | 20 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `crop` | 11 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `easter-egg` | 2 | 已实现，基础对等 | 已有对应处理器/入口；继续补边界测试与文档 | P1 |
| `erase-background` | 17 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `filters` | 577 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P0 |
| `format-conversion` | 2 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `gif-tools` | 13 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `gradient-maker` | 26 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `help` | 14 | 桌面原生等价 | Android 平台模块转换为 Qt/桌面机制；验证入口、持久化与行为即可 | P2 |
| `image-preview` | 2 | 桌面原生等价 | Android 平台模块转换为 Qt/桌面机制；验证入口、持久化与行为即可 | P2 |
| `image-stitch` | 18 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P1 |
| `libraries-info` | 4 | 桌面原生等价 | Android 平台模块转换为 Qt/桌面机制；验证入口、持久化与行为即可 | P2 |
| `library-details` | 2 | 桌面原生等价 | Android 平台模块转换为 Qt/桌面机制；验证入口、持久化与行为即可 | P2 |
| `main` | 15 | 桌面原生等价 | Android 平台模块转换为 Qt/桌面机制；验证入口、持久化与行为即可 | P2 |
| `media-picker` | 29 | 桌面原生等价 | Android 平台模块转换为 Qt/桌面机制；验证入口、持久化与行为即可 | P2 |
| `pdf-tools` | 124 | 已实现，但需要深度对等验证/完善 | 处理器与入口存在，但参考项目参数、交互或工作流更丰富；禁止以 registry 为完成依据 | P0 |
| `root` | 20 | 桌面原生等价 | Android 平台模块转换为 Qt/桌面机制；验证入口、持久化与行为即可 | P2 |
| `settings` | 164 | 桌面原生等价 | Android 平台模块转换为 Qt/桌面机制；验证入口、持久化与行为即可 | P2 |
| `usage-statistics` | 8 | 桌面原生等价 | Android 平台模块转换为 Qt/桌面机制；验证入口、持久化与行为即可 | P2 |

## 已确认的高风险差异

- **分形**：参考实现包含 formula / power / iterations / bailout / palette / coloring / viewport / camera / quaternion / supersampling 等参数；当前 Python 生成器只有基础 Mandelbrot 参数。
- **纹理生成**：参考实现包含 FastNoise、GMIC、Raymarch、Pattern 以及多个独立参数组件；当前 `texture_generate()` 只有少数生成类型。
- **Shader Studio**：参考实现包含 GLSL 编辑、preset/library、参数编辑、验证、导入/导出和预览；当前 CPU shader 是效果型处理器，不是完整 shader studio。
- **批量重命名**：参考实现有 pattern、sequence、日期来源、手动日期/时间等工作流；当前已补安全预览/执行面板，但仍需继续覆盖全部 token 行为。
- **绘图/标注图层**：参考实现是交互式多层编辑；当前 `annotate()` 是离线绘制接口，仍需升级为真正画布/图层编辑器。
- **OCR**：参考实现有 engine/model/language/segmentation 参数；当前桌面版主要依赖 Tesseract，需要继续做参数化与依赖检测。
- **EXIF**：当前读取/删除较完整，但编辑入口仍需升级为字段编辑器并保留格式/元数据安全策略。
- **Photomosaic / Fusion / SVG / Mesh / WebP/APNG/JXL**：处理器已经存在，但参数和专业工作流仍需继续对齐。

## 阶段 3 已开始的实现

- 建立 `feature/toolbox-parity-ui-overhaul` 分支。
- 新增可停靠/浮动的任务队列与运行日志 Dock。
- 增加窗口布局持久化、布局重置。
- 主题支持 Dark / Light / System，并持久化。
- 将分形、纹理、网格渐变、Shader、SVG、Photomosaic、多帧融合、动画转换等从单一占位入口升级为参数化专业面板。
- 新增批量重命名预览/安全执行面板，检测目标重名和覆盖风险。
- 新增核心 parity processor 单元测试。

## 验收命令

```bash
cd /home/emo/code/toolbox
.venv/bin/python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "from PySide6.QtWidgets import QApplication; from app.main_window import MainWindow; app=QApplication([]); w=MainWindow(); print('UI smoke OK'); w.close()"
.venv/bin/python -m py_compile app/*.py processors/*.py main.py
```

当前已验证：4/4 单元测试通过、Qt offscreen UI smoke 通过、Python 编译检查通过。

## 下一阶段

1. 把高风险模块继续做成真正的编辑器/参数工作流，而不是简单 generator panel。
2. 把批处理接入任务队列，支持取消/重试/进度。
3. 完善设置、依赖检测、最近文件、错误详情、日志过滤与导出。
4. 继续完善停靠布局预设、高 DPI 和键盘可达性。
5. 对 67 个模块逐项建立回归样例和手动验收清单。

## A1 Shader Studio — 2026-09-22

### 已实现

- 独立 `processors/shader_studio/` 模块，模型、uniform 解析、GLSL 验证、用户 preset library 解耦于主窗口。
- 独立 `app/panels/shader_studio.py` 专业面板。
- GLSL 编辑器：行号、关键字/函数/数字/注释高亮。
- uniform 自动解析，支持 float/int/vec2/vec3/vec4/color 方向的参数模型；sampler2D 作为资源 uniform 不进入普通数值编辑器。
- `@min/@max/@step/@label/@group` 注释元数据。
- 用户 preset JSON 持久化、删除、搜索、导入/导出。
- 三个内置 shader：Color Invert、Grayscale、Tint。
- `glslangValidator` 语法/编译验证，错误显示在面板中，不让坏 shader 直接导致应用退出。
- Qt `QOpenGLWidget` 实时预览架构：fullscreen triangle、纹理输入、`u_time`、`u_resolution`、uniform 更新和 framebuffer 导出。
- 预览动画暂停/播放基础设施。

### 测试

- 3 个内置 shader 均通过 `glslangValidator`：Color Invert / Grayscale / Tint。
- uniform parser / library persistence / invalid GLSL 共 3 个 Shader 专项测试通过。
- 全部回归测试：7/7 通过。
- Python compile：通过。
- offscreen Qt panel construction：通过，但 Qt 在无图形会话中明确报告 `QOpenGLWidget is not supported on this platform.`；这是测试环境缺少 Wayland/X11/GL context 的环境限制，不将其报告为 GUI OpenGL 运行通过。
- 独立 QOffscreenSurface OpenGL context 尝试：当前 Remote Desktop 无图形会话，`QOpenGLContext.create()` 返回 false，因此没有伪造“GPU shader runtime”结果。

### 与 ImageToolbox 的差异

ImageToolbox 的 Shader Studio 是 Android OpenGL/Compose 工作流，提供 shader preset、参数编辑、预览、导入/导出等能力。Desktop 版本现在采用 PySide6 + Qt OpenGL，功能模型保持对应，但 GLSL 运行时不是 Android 的 shader implementation；uniform 类型/语法以 desktop GLSL 3.30 为目标。当前尚未声称完成逐字节/逐算法一致性，也尚未实现完整 shader helper-source 编辑器、sampler 资源绑定 UI、序列帧批量导出和更复杂的 preset repository metadata。这些作为后续 A1.1 增量，而不是伪装成已完成。
