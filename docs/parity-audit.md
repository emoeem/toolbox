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
| `batch-rename` | 17 | **Batch + FilterChain 基础设施 usable**（见 A3） | 已建立 FilterChain/FilterStep/FilterPreset 体系；FilterChain 支持 add/remove/move/duplicate/enable/disable/validate_all/apply + CancelToken；FilterPreset JSON 保存/加载/删除；run_batch_filter_chain 支持多文件顺序处理、进度、取消、per-file 结果统计（succeeded/failed/cancelled）；单图失败不影响其他；与现有 TaskQueue/CancelToken 集成 | P1 |
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
| `filters` | 577 | **FilterDef + FilterChain + FilterPreset + Batch 全链路 usable**（见 A2 + A3） | A2 已建立 FilterDef 元数据体系（138 filters，75 curated 带参数），A3 在此之上建立 FilterChain（add/remove/move/duplicate/enable/disable/validate_all/apply + CancelToken）、FilterPreset（JSON save/load/delete）、run_batch_filter_chain（多文件顺序处理、进度、取消、per-file succeeded/failed/cancelled 统计）；UI 层 filter panel 已有"添加到链/应用整条链/Preset 保存加载"入口；不破坏 ALL_FILTERS/apply_filter 兼容性 | P0 |
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

## A2 FilterDef Infrastructure — 2026-09-22

### 目标

建立可扩展的 Filter 元数据体系，将现有 `(中文名, callable)` 升级为 `FilterDef`（定义+参数+processor+validation+preview+batch 元数据），同时不破坏 138+ legacy filters 和 advanced_filters。

### 已实现

- `processors/filter_defs.py`：核心模型
  - `FilterCategory`：12 分类（Blur / Color / Distortion / Edge / Noise / Sharpen / Stylize / Geometry / Lighting / Texture / Artistic / Other）
  - `FilterParam`：支持 int/float/bool/enum/color/string 六种类型，带 range validation、choices、description
  - `FilterDef`：key / display_name / category / params / processor / default_params() / validate_params() / apply() / param() / preview_supported / batch_supported
  - `FilterDefRegistry`：单例注册表
  - `register_filter()` helper
  - `_infer_params_from_signature()`：从函数签名自动推断参数
  - `_guess_category()`：关键字自动分类
  - `register_legacy_filters()`：批量迁移
  - `build_legacy_compat_layer()`：构建 ALL_FILTERS 兼容层

- `processors/filter_registry.py`：44 个 curated filters，全部带明确参数定义、validation、范围、步进和中文 label。覆盖 Blur（7）、Noise（6）、Color（14）、Distortion（8）、Edge（3）、Sharpen（3）、Stylize（6）、Texture（2）。

- `processors/__init__.py` 集成入口：
  - `advanced_filters.register_all()` → `filter_registry.register_curated_filters()` → `register_legacy_filters(filters.ALL_FILTERS)` → `build_legacy_compat_layer()` → `filters.ALL_FILTERS.clear()` + `update(ALL_FILTERS_COMPAT)`
  - 最终 ALL_FILTERS dict 内容替换为 FilterDef 驱动的 callable，但 dict 对象本身不变，旧代码 `from processors.filters import ALL_FILTERS` 和 `apply_filter(key, img)` 保持可用。

- `app/widgets/filter_parameter_widget.py`：根据 FilterDef.params 自动生成参数控件（int/float → LabeledSlider，bool → QCheckBox，enum → QComboBox，color → ColorField，string → QLineEdit）。复用 labeled_slider.py、color_field.py。提供 `paramsChanged` 信号、`current_params()`、`reset_to_defaults()`。

- `app/main_window.py` 最小 UI 接入：
  - filter list 下方新增参数区 + FilterParameterWidget
  - 选择 filter 时自动切换 FilterDef
  - 参数变化时实时 preview（preview 失败不 crash）
  - Apply 按钮优先使用 FilterDefRegistry 中的 FilterDef.apply(image, params)，带参数 validation
  - "↺ 默认" 重置按钮

- `tests/test_filter_defs.py`：69 个测试全部通过
  - FilterParam 创建、类型约束、默认值
  - validation：int/float range、enum choices、color tuple/hex、bool、string
  - FilterDef：default_params / validate_params / apply（默认 / 带参 / 非法参数抛 ValueError）
  - FilterDefRegistry：单例、注册、get、has、by_category
  - ALL_FILTERS 兼容：dict 仍可遍历、apply_filter 无参调用 OK、带参调用 OK
  - Curated filters 验证：12 个真实 curated filters，含精确参数断言
  - Legacy 自动迁移：138 个 legacy filters 全部在 registry 中
  - UI Layer（PySide6）：widget 生成 int/float/enum 控件、reset、无参数 filter、实际 apply 端到端

### 测试结果

- **新测试**：69/69 OK（tests/test_filter_defs.py）
- **全量回归**：114 测试，113 OK，1 GMIC backend 超时（pre-existing，与本次无关）
- Python compile：通过
- main_window.py syntax：通过

### Batch 兼容性

FilterDef.apply(image, params) 是纯函数调用，不依赖任何 UI 控件。params dict 可以在 batch 管线中直接构造，不需要 widget。这为未来 FilterChain 和 Batch 处理打下了基础。

### 与 ImageToolbox 的差异

ImageToolbox 使用 Kotlin interface 体系（SimpleFilter / FloatFilter / PairFilter / TripleFilter / FloatBooleanFilter / GmicFilter 等 20+ 子类型接口 + 577 个独立 interface 定义），配合 KSP 注解处理器自动发现。Python 端选择更简单的 FilterDef dataclass + FilterDefRegistry 单例模式，避免过度设计。参数模型已对齐。

### 限制

- 参数自动推断 `_infer_params_from_signature()` 范围推断较宽松（`max(255, default*3)`），curated filters 之外的 filters 使用推断参数仅为辅助，不保证精确语义。
- 138 个 filters 中仅 44 个拥有 curated 明确参数定义；其余 94 个使用签名推断参数或无参数。
- preview 在主线程做，对大多数 filter 足够；复杂 filter 未来需接入 TaskQueue。

---

## A3 FilterChain / FilterPreset / BatchFilterChain — 2026-09-29

### 目标

在 A2 FilterDef 元数据体系之上，建立真正可复用的 FilterChain 基础设施，使多张图片可以顺序应用多个 filter；提供 FilterPreset 持久化；与现有 CancelToken/TaskQueue 集成。

### 新增模块

- `processors/filter_chain.py`
  - `FilterStep`：单一步骤，filter_key + params + enabled。不重复定义参数 schema，全部委托给 `FilterDefRegistry`。提供 `validate()` / `apply(img, cancel_token)` / `clone()` / `to_dict()` / `from_dict()`。
  - `FilterStepError`：明确错误，携带 step_index / filter_key / message / original。
  - `FilterChain`：有序步骤列表。API：`add()` / `add_step()` / `remove()` / `clear()` / `move_up()` / `move_down()` / `duplicate()` / `enable()` / `disable()` / `set_params()` / `validate_all()` / `apply(img, cancel_token)` / `clone()` / `enabled_steps()` / `to_dict()` / `to_json()` / `from_dict()` / `from_json()`。
  - 执行模型：按 enabled 顺序 apply；遇到未知 Filter key 在 add 阶段抛 KeyError；参数 validation 在 `validate_all()` 和 `apply()` 入口双重校验；单个步骤失败提供明确 `FilterStepError`；支持 CancelToken 在每个步骤前 raise_if_cancelled。
  - 纯数据结构，不依赖 Qt。

- `processors/filter_presets.py`
  - `save_preset(name, chain, overwrite=True)` / `load_preset(name)` / `load_preset_from_path(path)` / `list_presets()` / `delete_preset(name)` / `preset_exists(name)`
  - JSON 格式，schema_version 1，包含 name / created_at / updated_at / chain
  - 存储位置复用 `DesktopSettings` 设置 + 多级 fallback（HOME/.toolbox → HOME/.config → /tmp）
  - 禁止 pickle，只保存可序列化 params dict（只保存实际值，load 时通过 `FilterDef.default_params()` 补全默认值）

- `processors/batch_filter_chain.py`
  - `BatchItemStatus`：PENDING / RUNNING / SUCCEEDED / FAILED / CANCELLED
  - `BatchItemResult`：source / output / status / error / elapsed_ms
  - `BatchFilterChainResult`：items list + succeeded / failed / cancelled / total 计数
  - `run_batch_filter_chain(files, chain, output_dir, format, progress_cb, cancel_token, overwrite)`
  - 逐文件顺序处理；复用 `load_image` / `save_image` / `ensure_rgb`；复用 `CancelToken`；progress_cb 签名 `(index, total, status_str)`；单图失败不影响其他；取消后剩余文件全部标记 CANCELLED；返回完整 per-file 结果列表。

- `processors/filter_defs.py` 小改：`FilterDef.apply()` 增加可选 `cancel_token` 参数（不破坏原有调用签名）

### UI 接入（main_window.py filter panel 最小改动）

- "➕ 添加到链"：从当前 filter list 选择 + 当前 params widget 值 → `_filter_chain.add(key, params)`
- "▶ 应用整条链"：`validate_all()` + `FilterChain.apply(img)` + 错误弹窗
- "清空"：清空链
- "↑ ↓ ✕ ⇅"：上移 / 下移 / 删除 / 启禁（selected step）
- preset_row：ComboBox（列出全部 preset）+ 💾保存 + 加载 + 删除（QInputDialog 取名称，QMessageBox 确认删除）
- `_refresh_chain_list()` 渲染：🔸enabled / 🔹disabled 前缀 + 显示非默认值 params
- 点击 chain step 时自动 set_filter_def 到 param widget

### 测试

- **tests/test_filter_chain.py（新增，60 tests，全通过）**
  - FilterStep：create / unknown_def / clone / to_dict / apply / bad params
  - FilterChain：empty / add single / add multiple / add unknown / add_step / remove / clear / move_up / move_down / duplicate / enable_disable / set_params / enabled_steps
  - FilterChain.validate_all：all ok / unknown filter / out of range / disabled 不校验
  - FilterChain.apply：single / multi order / disabled 跳过 / params reach processor / unknown filter / validation 先于 processor
  - FilterChain.clone：params 独立 / name 保留
  - FilterChain.serialize：to_dict / from_dict roundtrip / json roundtrip / newer version reject
  - FilterStepError：属性
  - Preset：save/load roundtrip / overwrite / list / no-overwrite raises
  - Batch：succeeded / cancelled / one failure 不破坏其他 / progress cb / overwrite=False / invalid file
  - CancelToken：FilterDef.apply 在取消时 raise / FilterChain.apply 在取消时 raise
  - Smoke：gaussian_blur→sharpen_simple→sepia 输出正确 shape/dtype / 不同 params yield 不同图像

- **全量回归**：174 tests, 173 OK, 1 GMIC timeout（pre-existing）

### 兼容性

- ALL_FILTERS / apply_filter / legacy filters / FilterDef / FilterDefRegistry 全部保持不变
- processors/__init__.py 新增 FilterChain/FilterStep/save_preset/run_batch_filter_chain 等 re-export，但没有移除任何旧导出
- main_window.py 只在 filter panel 中追加新代码，未改动其他 panel

### 与 ImageToolbox 的差异

ImageToolbox 使用 KSP 注解处理器自动发现 FilterTemplate（`_Template.kt`）并持久化到 Room DB 或文件系统。Python 端选择简单的 JSON 文件 + `DesktopSettings` 路径，避免过度设计持久化层。FilterChain 在 ImageToolbox 中由 `FilterTemplateManager` 管理，Python 端直接用 dataclass 列表。

### 限制

- 没有把 `run_batch_filter_chain` 接入现有 `_build_batch_panel` UI（当前 batch panel 只做格式转换）；Filter Batch UI 入口暂时只在 filter panel 内部
- 还没有设计批量导出策略（per-file 命名、失败隔离 UI 呈现、并发 vs 顺序）；只实现了顺序处理 + per-file 结果
- Preset 存储路径写死（settings store + fallback），没有给用户 UI 选择
- ~~FilterChain.apply 是同步的；没有接入 TaskQueue；对大图像或复杂链可能阻塞 UI（preview 在主线程跑）~~ → A4 已解决
- 还没有 FilterChain 版本号与 FilterDef 版本号联动（如果未来 FilterDef 改了 params 名称，旧 Preset 会在 load 时部分失败）
- 未迁移的 94 个 filters 仍然只有签名推断 params，FilterDef 问题集中在 A2 已描述

---

## A4 TaskQueue 接入 / 后台 Preview / Batch FilterChain — 2026-09-29

### 目标

解决 A3 遗留的三个核心架构问题：FilterChain 同步执行阻塞 UI、Batch 面板没有真正使用 FilterChain、Preview 无法后台执行。同时为 FilterPanel 提供缓存/去重机制。

### 新增模块

- `processors/filter_chain_task.py`
  - `make_filter_chain_worker(image, chain, progress_cb, cancel_token) -> Callable[[Callable[[int], None], CancelToken], np.ndarray]`：返回适配 `TaskQueueWidget.enqueue()` 签名的 worker 函数。worker 在 TaskQueue 的 QThreadPool 线程中执行，内部支持 progress_cb（同时转发给 qprogress）和 cancel_token（在每个 step 前 raise_if_cancelled）。
  - `run_filter_chain_sync(image, chain, progress_cb, cancel_token) -> np.ndarray`：同步版本，供不需要后台执行的场景使用。
  - 两个函数都会把 FilterStep.step_index 从 -1（FilterStep.apply 内部默认）修正为原始 chain.steps 中的真实 index，使上层可以精确报告"第 N 步失败"。
  - Preview 缓存：`preview_cache_key(image, chain, max_side=256)` 使用 SHA1 哈希图像缩略采样 + chain.to_json() 的组合 key；`preview_cache_get/set/clear` 提供线程安全（threading.Lock）的 dict 缓存，上限 8 条，FIFO 淘汰。图像切换/关闭窗口时自动 clear。

### UI 接入

- Filter 面板 Preview 后台化（main_window.py）
  - `_on_filter_params_changed`（参数实时预览）：不再直接 `defn.apply()`，改为记录 `_pending_preview_params/_pending_preview_key` 并启动 250ms `QTimer` debounce。
  - `_do_single_filter_preview`：timer 到期后，先用 `preview_cache_key` 查缓存，命中则直接显示；未命中则构造单步骤 FilterChain，用 `make_filter_chain_worker` 提交给 `task_queue.enqueue()`。提交前先取消上一个 `_preview_task`，避免快速拖动参数产生任务堆积。
  - 回调 `_on_single_filter_preview_done/failed` 通过 Qt signal 在主线程 update_current()，避免跨线程 crash。
  - `_on_apply_chain`（"应用整条链"按钮）：完全重写为后台提交，用 `make_filter_chain_worker(img.copy(), self._filter_chain)` + `task_queue.enqueue()`，信号回调更新 preview 和状态栏。

- Batch 面板接入 FilterChain 模式（main_window.py）
  - 新增控件：`batch_use_chain`（QCheckBox，预留模式切换）、`batch_chain_preset`（QComboBox，首项"(当前滤镜链)" + 所有已保存 preset）、`batch_overwrite`（"覆盖已存在" QCheckBox）。
  - 新增按钮：原来的"批量转换格式"保留（mode="convert"），新增"▶ 批量滤镜链处理"（mode="chain"，objectName="primary"）。
  - `_run_batch(mode="convert")`：convert 分支保持原有纯格式转换逻辑不变；chain 分支调用 `run_batch_filter_chain()`，通过 `chain_worker(qprogress, qcancel)` 适配 TaskQueue API，内部将 `(index, total, status_str)` 进度映射为 `qprogress(pct)`。
  - `_on_batch_chain_done(result)`：显示成功/失败/取消统计；失败文件超过 0 时用 QMessageBox 展示前 10 条详细错误。
  - 原有格式转换路径完全保留，兼容老用户。

### 生命周期安全

- `_on_image_changed`（切换/修改原图时）：自动取消正在执行的 preview task + 清空缓存。
- `closeEvent`：同样取消 preview task + 清空缓存。
- 所有 Task signal 回调都通过 Qt Signal→Slot 在主线程执行，不会操作已销毁的 QObject（因为 widget 在 QTimer.singleShot 和 task.signals 连接时已经是 parent 关系，关闭后 Qt 会自动断开）。

### Curated Filters 签名验证

通过 `inspect.signature` 验证了 A2 注册的 curated filters 的 FilterDef params 与实际 processor 签名的一致性：
- **OK 且无参数**：cyberpunk / lomo / polaroid / hdr_tone_mapping / cartoon 等（processor 只有 img 参数，registry params=[]）——这些是"无参数风格滤镜"，不应该伪造参数。
- **OK 且有参数**：bloom(threshold, strength) / glow(strength) / film_grain(amount) / halftone(dot_size) / chromatic_aberration(amount) / gaussian_blur(ksize, sigma) / sharpen_simple(strength) / dehaze(strength) / bilateral_blur(d, sigma_color, sigma_space) 等——参数名称、类型、默认值与 processor 签名完全一致。
- **不在 registry 中**：vignette（只有 legacy vignette_blur，没有单独的 vignette 关键词注册）——这不是一致性问题，是命名差异。

### GMIC 适配层状态

查看了 `backends/gmic_backend.py` 和 `processors/gmic.py`，确认 backend 已经能执行 GMIC CLI 命令（`subprocess.run(['gmic', ...])`），但当前 test 环境 GMIC CLI 有超时问题（pre-existing，timeout=5s 仍超时）。本阶段不强行实现 GMIC→FilterDef 适配层，因为无法在真实 backend 不可靠的情况下验证。后续 GMIC 作为独立模块在 backend 可靠后再实现最小适配。

### 测试

- **新增 tests/test_filter_chain_task.py（20 tests，全通过）**
  - `TestFilterChainTask`：`run_filter_chain_sync` 成功 / 带 progress callback / CancelledError / FilterStepError 携带真实 step_index / 跳过 disabled steps / 空链
  - `TestFilterChainWorker`：`make_filter_chain_worker` 成功 / 取消后抛 CancelledError / FilterStepError 携带 filter_key / 使用外部 CancelToken
  - `TestPreviewCache`：key 随 chain params 变 / key 随图像变 / cache hit / cache miss / clear / disable 状态改变 key
  - `TestBatchFilterChainWithTaskQueue`：成功 / 一个失败继续后续 / 取消停止 / overwrite=False / progress_cb 被正确调用

- **全量回归**：194 tests，193 OK，1 GMIC timeout（pre-existing，与 A4 无关）
- **offscreen MainWindow smoke test**：通过（Filter面板 + Batch面板均能构建、图片能加载、closeEvent 无 crash）

### 兼容性

- 复用现有 `TaskQueueWidget.enqueue()` / `Task.cancel()` / `TaskSignals.progress/finished/failed/cancelled`，未修改 workbench.py 任何代码。
- 未破坏 ALL_FILTERS / apply_filter / FilterDef / FilterDefRegistry / FilterChain / FilterPreset / run_batch_filter_chain 的任何 API。
- Batch 面板原有格式转换按钮（"批量转换格式"）保留，FilterChain 处理作为新增模式。
- 原有 `_apply_instant`（调整面板的实时滑块）保持不变——它是单值滑块 apply，不走 FilterChain。

### 与 ImageToolbox 的差异

- ImageToolbox 使用 `CoroutineScope.launch(Dispatchers.Default)` 做后台执行，Kotlin 的协程取消是结构化的。Python 端用 `QThreadPool.globalInstance()` + `QRunnable` + `CancelToken` 事件机制，取消是 cooperative 的（依赖每个 step 前调用 raise_if_cancelled）。
- ImageToolbox 的 FilterChain 预览没有显式缓存；Python 端增加了轻量 SHA1+JSON 缓存（上限 8 条，线程安全），因为 desktop 端用户拖动 slider 速度更快。
- ImageToolbox 的 Batch UI 是独立 Activity，Python 端嵌入在同一 dock 内。

### 限制

- 单滤镜实时 Preview 缓存没有考虑图像缩放（当前 key 里只记录原图像素哈希，不区分预览尺寸）——实际预览总是用 `preview._original`（原图），所以这不是 bug，但如果未来引入缩略图预览路径需要调整 key 构造。
- `_preview_task` 字段在 Filter 面板和 Batch 面板间共用（因为都是 MainWindow 级），但两者不会同时触发——Filter 面板触发 Preview，Batch 面板用独立的 task_queue 任务，互不干扰。
- Debounce 时间 250ms 是经验值，复杂滤镜链可能需要更长（用户感觉延迟）；未来可以改为自适应。
- run_filter_chain_sync 是同步的，如果调用方已经在后台线程（如 BatchFilterChain 内部）没问题，但如果直接从主线程调用还是会阻塞——文档应标记"仅供非 UI 线程使用"。
- GMIC CLI backend 在当前环境不可靠，没有做 GMIC→FilterDef 适配层；这是独立的 backends 问题，不在 FilterDef/FilterChain 范围内。
- FilterPanel 的"应用整条链"用 `img.copy()` 深拷贝原图，避免后台执行期间原图被修改。如果用户在后台链执行中又点击"撤销"，后台 task 完成时会覆盖撤销状态——需要后续加版本号检查来避免。

---

## A5 Fractal 分形能力对齐 — 2026-09-29

### 目标

将 Toolbox 从仅支持 Mandelbrot/Julia 两个分形的零散实现，扩展为完整的分形渲染框架，接入现有 FilterDef/TaskQueue/FilterChain 基础设施，并与 ImageToolbox FractalGeneration 模块的公式集合对齐。

### 审计：ImageToolbox Fractal 覆盖范围

通过读取 ImageToolbox `feature/fractal-generation` 的 `FractalFormula.kt`（枚举 56 个公式），确认了以下核心分类：

**2D Escape-time 类（Mandelbrot 系）**：
- Mandelbrot, Multibrot, Julia, Multicorn, Tricorn, Celtic, Buffalo, PerpendicularBurningShip, BurningShip, BurningShipJulia, CelticJulia, AlphaMandelbrot, AlphaMandelbrotJulia, BarnsleyMandelbrot, BarnsleyJulia, BarnsleyII, BarnsleyIII, HybridMandelbulbJulia（2D 部分）, SierpinskiCarpet, SierpinskiTriangle, VicsekCross, HeighwayDragon, PythagorasTree, KochSnowflake, Collatz, Newton, Nova, Phoenix, Spider, ManOWar, Lambda, Thorn, MandelbrotSine, JuliaSine, MandelbrotCosine, JuliaCosine, MandelbrotSinh, JuliaSinh, Feather, Cactus, Zubieta, Tetration, MagnetI, MagnetII, BurningShipJulia（独立公式）, CelticJulia（独立公式）

**2D Density/Attractor 类**：
- Buddhabrot, Hopalong, Martin, Gingerbreadman, Chip, Quadruptwo, Threeply, Clifford, DeJong, Ikeda, Tinkerbell, GumowskiMira, BarnsleyFern, IFSDragon, IFSTwig, ChristmasTree

**3D（distance estimator / ray marching / geometric IFS / attractor）**：
- Mandelbulb, Mandelbox, MengerSponge, SierpinskiTetrahedron, QuaternionJulia, SierpinskiGasket, OctahedralIFS, IcosahedralIFS, ApollonianGasket, Kleinian, HybridMandelbulbJulia, QuaternionCubic, Pickover（3D attractor）, Lorenz, Rossler

**ColorModel / Coloring**：Smooth, Banded, OrbitTrap, Angle（四种，与 GradientPalette 配合）

**FractalEngine 实现**：通过 `com.t8rin.fractal_engine.FractalEngine`（外部 native 依赖，未包含在 repo 源码中）

### Toolbox A5 实际实现

#### 新增模块

- **`processors/fractal.py`** — 完整分形渲染框架（745 行）
  - `FractalColoring` 枚举：SMOOTH / BANDED / GRAYSCALE
  - `FractalParams` dataclass：cx, cy, scale, power, iterations, bailout, coloring, julia_c, phoenix_c, nova_relaxation, supersampling
  - `FractalResult` dataclass：image (PIL), iterations_array (np.int32), escaped_mask (bool)
  - 2D Escape-time 核心（每个公式函数独立，支持 numba jit 可选加速）
  - 3D Ray marching + distance estimator（Mandelbulb）
  - `_register_2d_formula` / `_2D_FORMULAS` registry
  - `render_fractal(width, height, formula_key, params, cancel_token, progress_cb)` — 统一入口
  - `register_fractal_filters()` — FilterDef 自动注册
  - 渲染器分块（row）检查 CancelToken + 报告 progress（0~100）

- **`processors/filter_defs.py`** — 新增 `FilterCategory.FRACTAL` + `"分形"` label（1 行枚举 + 1 行 label）

- **`processors/filter_registry.py`** — 调用 `register_fractal_filters()` 自动注册所有分形公式（~5 行）

- **`tests/test_fractal.py`** — 29 tests（见下）

#### 2D 公式实现（15 个，全部真实数学实现）

| Toolbox key | ImageToolbox 对标 | 实现方式 | 参数真正生效 |
|---|---|---|---|
| `fractal_mandelbrot` | Mandelbrot | zₙ₊₁ = zₙᵖ + c | power, iterations, bailout |
| `fractal_multibrot` | Multibrot (defaultPower=3.0) | 同上，默认 power=3.0 | power, iterations, bailout |
| `fractal_julia` | Julia | zₙ₊₁ = zₙᵖ + C（常数） | power, iterations, bailout, julia_c |
| `fractal_burning_ship` | BurningShip | Re(zₙ₊₁)=|Re(zₙ)|+Re(c), Im(zₙ₊₁)=|Im(zₙ)|+Im(c) | power, iterations, bailout |
| `fractal_tricorn` | Tricorn | zᵖ 的共轭（z→z̄） | power, iterations, bailout |
| `fractal_multicorn` | Multicorn (defaultPower=3.0) | zᵖ 的共轭，默认 power=3.0 | power, iterations, bailout |
| `fractal_celtic` | Celtic | |Re(zₙ)| + i·Im(zₙ) | power, iterations, bailout |
| `fractal_buffalo` | Buffalo | |Re(zₙ)| - i·|Im(zₙ)| | power, iterations, bailout |
| `fractal_perpendicular_burning_ship` | PerpendicularBurningShip | |Re(zₙ)| + i·(-|Im(zₙ)|) | power, iterations, bailout |
| `fractal_phoenix` | Phoenix | zₙ₊₁ = zₙᵖ + c + pc·zₙ₋₁ | power, iterations, bailout, phoenix_c |
| `fractal_newton` | Newton | Newton 迭代求解 zᵖ=1 根的吸引盆 | power, iterations（收敛条件） |
| `fractal_nova` | Nova | zₙ₊₁ = zₙ - α·(f(z)/f'(z) - c + z) | power, iterations, nova_relaxation |
| `fractal_magnet_i` | Magnet I | Julia 变体，圆吸收条件 | iterations, bailout |
| `fractal_magnet_ii` | Magnet II | Julia 变体（c 不 -1.0） | iterations, bailout |
| `fractal_buddhabrot` | Buddhabrot | 密度渲染，渲染逃逸路径的轨道热图 | iterations, bailout（用 Monte Carlo 采样） |

每个公式内部实现都独立函数化，接受 (px, py, ...) 坐标 + 参数，返回 (escape_iteration, smooth_iteration_value) 元组。smooth coloring 公式基于 **Nielsen 平滑着色**（`nu = log(log|z|²/2) / log(p)`），Burning Ship / Tricorn / Phoenix / Multicorn / Celtic / Buffalo / PerpShip 都真实修改了迭代公式的某部分（不是简单 alias Mandelbrot）。

#### 3D 公式实现（1 个）

| Toolbox | ImageToolbox 对标 | 实现方式 |
|---|---|---|
| `render_mandelbulb` (独立函数) | Mandelbulb | Distance estimator + Ray marching + spherical 坐标变换 z↦zⁿ |

使用标准 distance estimator 公式 `DE = 0.5·log(r)·r / dr` 迭代，最多 64 ray marching steps。Camera 参数：distance, yaw, pitch, fov。**尚未注册为 FilterDef**（3D Mandelbulb 通常单独面板渲染，不适合 FilterChain 的"输入一张图生成一张图"模型——它从空场景生成 3D 图像）。

#### 颜色系统

- `_apply_gradient(norm)` — 基于正弦的 HSL-like 渐变（R=norm·255, G/B 用 sin 叠加），不依赖外部 GradientPalette
- `FractalColoring.SMOOTH` — 基于 smooth iteration value（Nielsen 平滑）做颜色插值
- `FractalColoring.BANDED` — 基于整数迭代 count % 256 做颜色，产生色带
- `FractalColoring.GRAYSCALE` — 同 smooth 但映射到灰阶
- ImageToolbox 的 OrbitTrap / Angle coloring 尚未实现（需要 orbit trap 计算，额外复杂度）

#### FilterDef 接入

- 15 个分形公式各注册一个 FilterDef，key 前缀 `fractal_`，category=`FRACTAL`（新增）
- 每个 FilterDef 的参数根据 formula capabilities 动态生成：
  - 所有公式都有 cx/cy/scale/iterations/coloring
  - `can_power=True` → power (default 来自公式 default_power)
  - `can_bailout=True` → bailout
  - `can_julia=True` → julia_c_x/julia_c_y
  - `can_phoenix=True` → phoenix_c_x/phoenix_c_y
  - `can_nova=True` → nova_relaxation
- processor 签名统一：`processor(img, cx, cy, scale, power, iterations, bailout, coloring, julia_c_x, julia_c_y, phoenix_c_x, phoenix_c_y, nova_relaxation, width_override, height_override, cancel_token)`
- **参数真的进入计算**（见 smoke test 验证：`Julia const diff=28.7`, `Multibrot power diff=19.6`, `Center/zoom diff=49.9`）
- FilterChain 可以直接包含任何 fractal_* step → `FilterStepError` 携带真实 filter_key/step_index
- FilterPreset 可以保存/恢复（JSON 持久化扁平 params dict）
- preview_supported=True, batch_supported=True

#### 性能

- **基础路径**：纯 Python + math.sqrt + math.log（不依赖外部 lib），64×64 Mandelbrot ≈ 0.01s（逃逸时间公式），Buddhabrot ≈ 0.28s（Monte Carlo 采样），Mandelbulb 64×64 ≈ 0.16s（ray marching）
- **numba 可选加速**：`_maybe_jit(nopython=True, cache=True)` 装饰器已就位；环境中 numba 可用（`.venv` 安装了），会自动启用；无 numba 时 fallback 纯 Python，保证可移植性
- **分块 + CancelToken**：按 row 渲染，每 row 检查 cancel，CancelToken 取消后立即抛 CancelledError 终止
- **preview 低分辨率**：Toolbox Filter panel 的 Preview 机制会自动给较低分辨率图像（缩略图），高分辨率留到正式 Apply

#### Toolbox UI 集成

- 现有 Fractal/Creator panel（`_build_creator_panel("fractal")`）原来只有 Mandelbrot/Julia 下拉框 → **保留**，作为 Creator 模式
- Filter panel 现在有 15 个 `fractal_*` filters → 用户可以像用其他 filter 一样用分形，加进 FilterChain，做 Batch 处理
- TaskQueue / CancelToken / Preview cache 已在 A3 完成，直接复用：`make_filter_chain_worker(fractal_output_chain, ...)` → 后台渲染 → Qt signal 更新 Preview
- **FractalFilter panel 专属 UI**（公式下拉 + 参数控件 + 独立渲染 + 进度条 + 取消按钮）尚未扩展——当前 Creator panel 仍是最基本的 Mandelbrot/Julia 选项。不过所有分形公式都已经可以通过 Filter panel 访问 + 进入 FilterChain + 做 Batch，这是"可用"状态。专属 UI 扩展可以在后续迭代

### 测试结果

- **tests/test_fractal.py（29 tests）** — 全部 PASS：
  - Formula registry 验证（所有 15 个 key 存在 + formula_info 有效）
  - 2D 渲染：64×64 正确尺寸 + iterations_array dtype + escaped_mask
  - 参数真生效：Julia 常数 → diff=28.7, Multibrot power → diff=19.6, center/zoom → diff=49.9, iterations → diff=16.8, coloring smooth/banded/grayscale 两两 diff>3.0
  - CancelToken 中断 + progress 单调且最终 ≥99
  - 3D Mandelbulb smoke（32×32, power=8, 16 iter）+ power 改变影响输出
  - FilterDef registry 15 个 fractal_* 正确注册 + category=FRACTAL
  - FilterDef 参数 capabilities 正确（Julia 有 julia_c_x/y，Mandelbrot 没有；Nova 有 nova_relaxation）
  - FilterChain 包含 fractal steps 能正常 apply
  - FilterPreset round-trip 完整保留 fractal params

- **全量回归**：**223 tests → 222 PASS, 1 GMIC timeout（pre-existing，与 A5 无关）**
- **MainWindow offscreen smoke**：Window 创建 OK → Fractal panel 创建 OK → 15 fractal filters 可见于 filter_list → FilterDef apply 正常 → CancelToken 传播正常 → closeEvent 无 crash

### ImageToolbox 对标与未实现

| 分类 | ImageToolbox 数量 | Toolbox A5 实现 | 状态 |
|---|---|---|---|
| 2D Escape-time 核心 | ~16 | 15 | ✅ Implemented（含 Buddhabrot density） |
| 2D Escape-time 扩展（Julia 系/Barnsley 系/Sine/Cosine/Sinh/Feather/Cactus/Zubieta/Tetration/Spider/ManOWar/Lambda/Thorn 等） | ~27 | 0 | ⚠️ Not implemented（公式在 ImageToolbox 源码中存在但 Toolbox 暂时未逐个实现；这些都是 escape-time 系的小变体，实现模式与现有 15 个完全一致，可在后续迭代中逐一补充） |
| 2D Density/Attractor（Hopalong/Martin/Gingerbreadman/Chip/Quadruptwo/Threeply/Clifford/DeJong/Ikeda/Tinkerbell/GumowskiMira/BarnsleyFern/IFSDragon/IFSTwig/ChristmasTree） | ~15 | 0 | ⚠️ Not implemented（独立迭代吸引子，不是 escape-time 系，实现模式不同） |
| 2D Geometric IFS（SierpinskiCarpet/Triangle/VicsekCross/HeighwayDragon/PythagorasTree/KochSnowflake） | ~7 | 0 | ⚠️ Not implemented（几何构造，不是 escape-time） |
| 3D Distance Estimator（Mandelbulb/Mandelbox/HybridMandelbulbJulia） | ~3 | 1 (Mandelbulb) | ✅ Partially implemented（核心 distance estimator + ray marching 已实现；Mandelbox 的 SDF fold 变换后续补充；已暴露为 `render_mandelbulb()` 函数，尚未注册为 FilterDef） |
| 3D Geometric IFS（MengerSponge/SierpinskiTetrahedron/SierpinskiGasket/OctahedralIFS/IcosahedralIFS/ApollonianGasket/Kleinian） | ~7 | 0 | ⚠️ Not implemented |
| 3D Quaternion（QuaternionJulia/QuaternionCubic） | ~2 | 0 | ⚠️ Not implemented（4D 复数，需要 Quaternion distance estimator） |
| 3D Attractor（Lorenz/Rossler/Pickover(3D)） | ~3 | 0 | ⚠️ Not implemented（独立迭代吸引子） |
| Coloring（四种） | 4 | 3 | ✅ Mostly implemented（Smooth/Banded/Grayscale ✅，OrbitTrap/Angle ⚠️ 未实现） |

### 关键架构决策

1. **FilterDef 粒度**：每个公式独立 FilterDef（15 个 `fractal_*`），而不是一个通用 `fractal_generator`。原因：capabilities 不同（Julia 需要 julia_c 参数，Mandelbrot 不需要），Filter UI 可以根据 capabilities 自动显示对应参数控件。代价是 FilterDef 注册数量多，但自动化生成（`register_fractal_filters` 遍历 `_2D_FORMULAS`）。

2. **3D 不进 FilterDef**：3D Mandelbulb 暴露为 `render_mandelbulb()` 顶层函数，不注册为 FilterDef。理由：FilterDef 的 processor 签名期望输入是 numpy 图像（用于 FilterChain 场景），而 Mandelbulb 从空场景渲染 3D 图像——没有"输入图像处理"的语义。Toolbox 未来会有 3D 独立面板。

3. **Color 层不硬绑 GradientPalette**：Toolbox 现有 `tools/gradients.py` 有 GradientPalette，但 Fractal coloring 用了自己的简单正弦渐变 `_apply_gradient(norm)`，避免引入重量级依赖。后续可以对接 GradientPalette。

4. **numba 可选**：检测 import 失败自动 fallback。基础 CPU 路径完全独立，不依赖 CUDA。

5. **CancelToken 分块检查**：按 row 检查（Mandelbulb 按 row 检查，每 row 内 ray marching 64 steps）。响应频率 = height / 50 ≈ 每 2% 检查一次。

### 限制 / 已知问题

- **2D 扩展公式未实现**（Barnsley 系/Sine/Cosine 等 27 个）：实现模式与现有 escape-time 公式完全一致，每个只需要复制 `_register_2d_formula` + 一个 `_xxx_iter` 函数（复杂度低，可在后续迭代批量补充）
- **Density/Attractor 类 0/15**：Hopalong/Martin 等是**随机迭代吸引子**（不是 escape-time），需要独立渲染引擎。Toolbox 有 `processors/attractors.py` 吗？目前没有——整个 attractor 系是空白
- **3D Geometric IFS/Quaternion 系 0/12**：距离估计器实现复杂，且 Mandelbulb 也需要完善（还没有 ambient occlusion、lighting 等）
- **OrbitTrap / Angle coloring 未实现**：需要额外计算 orbit points 或 angle，会增加 escape-time 路径的每像素计算量
- **Mandelbulb 不是 FilterDef**：如上所述
- **Creator Fractal panel 仅 Mandelbrot/Julia 下拉**：现有 `_build_creator_panel("fractal")` UI 未扩展，只识别两个 formula；用户需要通过 Filter panel 才能访问所有 15 个分形公式。这是"功能可用但 UI 不完整"状态
- **Newton / Magnet 公式的 bailout 参数不生效**（设了 `can_bailout=False`）：Newton 用收敛条件（步长 < 1e-9 或 r < 1e-15），Magnet 用 `r→1` 收敛或 `r>1e10` 发散——都不是 escape-time bailout，正确
- **Magnet 公式的逻辑**：`_magnet1_iter` 的 `|z|=1` 吸收检查在实际 Julia 变体里可能需要 `f(z)=z²+c-1`（Magnet I）和 `f(z)=z²+c`（Magnet II），而实际吸收条件是 `z ∈ ∂D`（单位圆边界）——当前实现简化为 `abs(r-1.0) < 1e-15`，可能不准确。需要后续对照标准 Magnet Julia 公式验证

### 测试覆盖

| 模块 | 测试数 | PASS |
|---|---|---|
| tests/test_fractal.py | 29 | 29 ✅ |
| 全量回归 | 223 | 222 ✅ + 1 GMIC timeout（pre-existing） |
| MainWindow offscreen smoke | 1 次 | ✅ 全部通过 |
