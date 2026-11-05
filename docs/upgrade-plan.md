# Toolbox 2.0 —— 原生桌面 UI 架构升级与现代化改造计划

## 1. 项目定位

项目名称：Toolbox 2.0

项目仓库：https://github.com/emoeem/toolbox

项目定位：Linux 原生专业图像处理与创作工具箱。

本次升级的核心目标是将现有 Python + PySide6 Widgets 桌面界面迁移为 C++ + Qt Quick + QML 架构，保留并逐步完善现有 Python 图像处理引擎。

本次不是简单的界面换肤，而是一次 UI 架构、模块边界、交互设计、字体系统和桌面应用工程化升级。

### 核心目标

1. UI 层完全脱离 Python，不再使用 Python 编写桌面界面。
2. 采用 C++ + Qt 6 Quick + QML 建立新的桌面界面。
3. 保留现有 Python 图像处理引擎，避免大规模重写成熟算法。
4. 建立 UI 与图像处理引擎之间稳定、可测试的通信协议。
5. 重构过度集中的 MainWindow，建立模块化架构。
6. 建立统一的设计系统、字体系统和主题系统。
7. 保证现有图像处理功能迁移期间不出现功能回退。
8. 优先完善 Linux Wayland 桌面体验。

## 2. 技术栈最终决策

### 2.1 前端与桌面 UI

- C++20
- Qt 6
- Qt Quick
- QML
- Qt Quick Controls
- Qt QML Models
- Qt Graphical Effects（按实际需要选择可用组件）
- CMake
- Qt Test / Qt Quick Test

UI 不再使用 Python、PySide6 或传统 QWidget 进行新功能开发。

QML 只负责界面和交互表达，不承载图像处理算法。

### 2.2 图像处理引擎

第一阶段继续使用：

- Python 3.11+
- NumPy
- Pillow
- OpenCV
- scikit-image
- imageio
- numba
- G'MIC

现有 processors 目录尽量保持原有算法接口和行为。

不允许为了配合新 UI 而一次性重写全部图像处理算法。

### 2.3 构建工具

- CMake：C++ 项目构建。
- Qt 6：界面和桌面基础设施。
- Ninja：本地构建。
- uv：Python 引擎依赖管理。
- GitHub Actions：自动化测试。
- clang-format：C++ 代码格式。
- clang-tidy：C++ 静态分析。
- Ruff：Python 代码检查。
- CTest：C++ 测试入口。

## 3. 新架构设计

### 3.1 总体目录结构

```text
toolbox/
├── CMakeLists.txt
├── CMakePresets.json
├── pyproject.toml
├── uv.lock
│
├── native/
│   ├── app/
│   │   ├── main.cpp
│   │   ├── application.cpp
│   │   └── application.h
│   │
│   ├── core/
│   │   ├── image_document.h
│   │   ├── image_document.cpp
│   │   ├── image_metadata.h
│   │   └── image_metadata.cpp
│   │
│   ├── services/
│   │   ├── image_service.h
│   │   ├── image_service.cpp
│   │   ├── filter_service.h
│   │   ├── filter_service.cpp
│   │   ├── batch_service.h
│   │   ├── batch_service.cpp
│   │   ├── fractal_service.h
│   │   └── task_service.h
│   │
│   ├── models/
│   │   ├── tool_model.h
│   │   ├── filter_model.h
│   │   ├── task_model.h
│   │   ├── history_model.h
│   │   └── recent_file_model.h
│   │
│   ├── backend/
│   │   ├── python_worker.h
│   │   ├── python_worker.cpp
│   │   ├── ipc_protocol.h
│   │   ├── ipc_protocol.cpp
│   │   └── backend_manager.cpp
│   │
│   └── graphics/
│       ├── image_canvas.h
│       ├── image_canvas.cpp
│       ├── image_texture.h
│       └── viewport_controller.cpp
│
├── ui/
│   ├── Main.qml
│   ├── components/
│   ├── layouts/
│   ├── pages/
│   │   ├── HomePage.qml
│   │   ├── EditorPage.qml
│   │   ├── BatchPage.qml
│   │   ├── FractalPage.qml
│   │   ├── ShaderPage.qml
│   │   ├── TexturePage.qml
│   │   └── SettingsPage.qml
│   │
│   ├── themes/
│   │   ├── Theme.qml
│   │   ├── Colors.qml
│   │   ├── Typography.qml
│   │   ├── Spacing.qml
│   │   └── Controls.qml
│   │
│   └── assets/
│
├── engine/
│   └── toolbox_engine/
│       ├── worker/
│       │   ├── main.py
│       │   ├── protocol.py
│       │   └── dispatcher.py
│       │
│       └── processors/
│           └── 现有处理算法
│
├── tests/
│   ├── native/
│   ├── qml/
│   ├── integration/
│   └── engine/
│
├── docs/
│   ├── architecture.md
│   ├── ipc-protocol.md
│   ├── ui-design-system.md
│   ├── ui-migration-matrix.md
│   └── upgrade-plan.md
│
└── packaging/
    ├── linux/
    └── resources/
```

该目录结构是目标结构，不要求第一批次就搬动所有旧文件。

### 3.2 UI 与 Python 引擎通信

采用独立 Python Worker 进程。

C++ 使用 QProcess 启动 Worker，通过标准输入和标准输出进行 JSON Lines 控制消息通信。

消息协议使用版本号，并提供统一的请求、响应、任务进度、取消和异常结构。

示例：

请求：

```json
{
  "protocol": 1,
  "request_id": "req-001",
  "action": "image.adjust",
  "document_id": "doc-001",
  "params": {
    "brightness": 0.1,
    "contrast": 1.2
  }
}
```

响应：

```json
{
  "protocol": 1,
  "request_id": "req-001",
  "success": true,
  "result": {
    "document_id": "doc-001",
    "preview_available": true
  }
}
```

进度：

```json
{
  "protocol": 1,
  "type": "progress",
  "task_id": "task-001",
  "progress": 60
}
```

关键原则：

- JSON 只传递控制信息和小型参数。
- 不允许通过 Base64 在 JSON 中传输大型原始图像。
- 大型图像使用临时文件、内存映射文件或共享内存传递。
- Worker 内维护 document_id 和对应图像状态，避免反复复制完整图像。
- 预览结果采用适当的缩略图或图像纹理传递机制。
- 每项任务必须支持进度反馈与取消。
- Worker 崩溃时，前端能够识别错误并恢复界面。
- 不依赖本地 HTTP Server 作为主要 IPC 通道。

Python Worker 的启动、关闭、日志、异常和版本兼容均由 BackendManager 管理。

最终发布时应把 Python Runtime 和必要依赖打包为独立运行环境，普通用户不需要手动安装 Python。

## 4. UI 设计方向

### 4.1 整体视觉

设计目标：

- 现代桌面专业软件。
- 清晰的视觉层级。
- 统一的圆角和间距。
- 高质量中文字体。
- 克制的动画。
- 深浅色主题。
- 优秀的长时间工作体验。

整体采用现代桌面编辑器风格，参考专业图像工具、现代 IDE 和创作软件。

避免：
- 大量默认 Qt 控件直接堆叠。
- 过度使用渐变和霓虹色。
- 无意义的大面积留白。
- 所有功能都塞进一个巨型侧边栏。
- 每个面板采用不同的组件风格。

### 4.2 主界面布局

主界面划分为五个部分：

1. 左侧导航栏：工具分类、搜索、收藏和最近使用。
2. 顶部工具栏：打开文件、保存、撤销、重做、缩放和当前工具操作。
3. 中央画布：图像展示、缩放、平移、选区和预览。
4. 右侧检查器：当前工具参数、滤镜参数和高级设置。
5. 底部状态区：任务队列、处理进度、图像尺寸和缩放比例。

界面布局支持适当调整宽度、面板显隐和布局持久化。

### 4.3 工具分类

将当前大量工具按使用场景重新组织：

- 图像编辑：调整、裁剪、旋转、缩放、变换。
- 滤镜效果：基础滤镜、高级滤镜、G'MIC、艺术效果。
- 图像创作：渐变、分形、纹理、Shader、Photomosaic。
- 批量工具：批量处理、批量转换、批量重命名。
- 图像分析：直方图、EXIF、图像比较、Checksum。
- AI 工具：背景移除、超分辨率、降噪、色彩化。
- 文件工具：PDF、压缩、归档、加密、Base64。
- 设置：主题、字体、性能、后端、依赖诊断。

工具搜索需要支持关键词、分类和最近使用记录。

## 5. 字体系统专项升级

字体系统作为第一优先级修复内容。

### 5.1 删除不合理设计

- 移除全局强制 MiSans 的 QSS 规则。
- 移除每次启动递归扫描全部系统字体目录的逻辑。
- 不再让主题文件强制指定固定字体。
- 修复等宽字体只读取但不应用的问题。
- 删除测试中强制必须使用 MiSans 的断言。

### 5.2 字体角色

UI 字体：
- 优先使用清晰、可读的系统 UI 字体。
- 中文可提供 Noto Sans CJK SC、Sarasa UI SC 等选项。
- LXGW ZhenKai 作为可选字体风格。

等宽字体：
- Maple Mono Normal NF CN。
- JetBrains Mono。
- 系统等宽字体回退。

Emoji 和符号：
- 使用系统 Emoji 字体回退。
- 不让 Emoji 字体影响普通中文文本。

### 5.3 字体配置功能

设置界面提供：

- UI 字体选择。
- 中文字体回退。
- 等宽字体选择。
- UI 字体大小。
- 等宽字体大小。
- 字体预览。
- 恢复系统默认设置。

程序必须能够查询控件实际使用的字体，而不是只检查配置中的字体名称。

字体测试需要检查中文、英文、数字、符号及 Emoji 的实际显示回退结果。

## 6. 图像画布专项设计

这是整个应用最重要的技术模块之一。

### 功能

- 高分辨率图像显示。
- 鼠标滚轮缩放。
- 鼠标拖动平移。
- 双击适配窗口。
- 100% 原始比例。
- 适合窗口。
- 棋盘格透明背景。
- 坐标显示。
- 选区和辅助线。
- 图像比较。
- 实时预览。
- 缩略图缓存。

### 性能原则

不要用简单的 QWidget 图片标签替代专业图像视口。

QML 画布使用 Qt Quick Scene Graph；必要时通过自定义 QQuickItem 和 QSG 节点实现纹理渲染。

高分辨率图像显示优先采用 GPU 纹理与按需刷新机制。

避免用 QQuickPaintedItem 承担需要高频更新的大型图像画布，因为这种方式存在额外的中间绘制开销。

所有图像处理均在后台运行，不能阻塞 UI 主线程。

## 7. 分阶段开发计划

每个阶段独立实施、独立验收。

未通过当前阶段验收，不允许提前进入下一阶段。

### Phase 0：项目基线与现有字体修复

优先级：P0

内容：

1. 确认现有功能清单。
2. 固定当前测试基线。
3. 建立核心图像测试样本。
4. 修复现有字体强制覆盖。
5. 删除不必要的字体全目录扫描。
6. 建立实际字体解析测试。
7. 整理现有 MainWindow 与 processors 的调用关系。
8. 建立 UI 功能迁移矩阵。

交付：

- 字体问题修复。
- 旧程序仍可以正常启动。
- 核心处理结果有可复现的基线。
- 架构分析文档。
- UI 功能迁移矩阵。

验收：

- 原有测试不回退。
- Qt GUI 能真实启动。
- 中文字体没有意外回退。
- 字体设置能够正确生效。
- 现有功能清单完整。

### Phase 1：Qt Quick 技术原型

优先级：P0

内容：

1. 建立独立 CMake 项目。
2. 创建 C++ Qt Quick 应用入口。
3. 建立 QML 主窗口。
4. 实现基础导航栏。
5. 实现中央图像画布。
6. 实现图像打开与显示。
7. 实现基础缩放和平移。
8. 完成简单参数面板。

本阶段只要求一条完整的小型工作流，不迁移全部功能。

验收：

- 程序完全不依赖 Python UI。
- C++ 能加载 QML。
- Wayland 环境下能够正常运行。
- GPU 图像显示正常。
- 字体和中文回退正常。
- 项目能通过 CMake 独立构建。

### Phase 2：Python Worker 与通信架构

优先级：P0

内容：

1. 实现独立 Worker 入口。
2. 实现 JSON Lines 协议。
3. 实现 C++ QProcess 管理器。
4. 实现请求和响应映射。
5. 实现任务进度。
6. 实现任务取消。
7. 实现异常与日志传递。
8. 实现 document_id 管理。
9. 实现文件或共享内存数据传递原型。
10. 实现 Worker 崩溃后的错误处理。

验收：

- C++ 可以调用真实 Python 处理器。
- 可以读取和处理真实图像。
- 返回的结果与旧程序一致。
- 处理任务不阻塞 UI。
- 取消任务确实能够终止处理。
- 不需要对大型图像进行 JSON Base64 编码。

### Phase 3：新 UI 基础设施

优先级：P0

内容：

1. 完整主窗口。
2. 页面导航系统。
3. 搜索系统。
4. 主题系统。
5. 字体系统。
6. 组件设计系统。
7. 参数控件系统。
8. 通知系统。
9. 任务队列。
10. 设置与布局持久化。

建立统一组件：

- Button
- IconButton
- SearchField
- Slider
- NumberField
- Select
- ColorPicker
- ParameterGroup
- ToolCard
- InspectorPanel
- TaskItem
- ImageCanvas

所有页面必须使用统一组件和设计令牌。

验收：

- 新 UI 不依赖 QWidget。
- 各组件可独立测试。
- 深色和浅色主题正常。
- 字体设置全局生效。
- 主窗口尺寸变化后布局合理。

### Phase 4：核心图像编辑功能迁移

优先级：P0

严格按下面的顺序迁移：

第一批：基础文件工作流
- 打开图像。
- 拖放图像。
- 保存和另存为。
- 格式转换。
- 图像信息。
- 最近文件。

第二批：中央画布
- 缩放和平移。
- 原始尺寸查看。
- 适配窗口。
- 透明棋盘格。
- 图像比较。

第三批：基础编辑
- 亮度。
- 对比度。
- 饱和度。
- 色相。
- 曝光。
- 裁剪。
- 旋转。
- 翻转。
- 缩放。
- 变换。

第四批：滤镜系统
- FilterDef。
- 参数自动生成。
- 滤镜分类。
- 参数预览。
- 滤镜应用。
- 滤镜组合。
- 预设管理。

第五批：历史管理
- Undo。
- Redo。
- 历史记录。
- 重置操作。
- 任务完成状态。

验收：

- 原有处理器全部复用。
- 图片处理结果通过逐像素或合理误差对照。
- Undo/Redo 行为正确。
- 大图操作不卡 UI。
- 所有核心功能完成手工验证。

### Phase 5：创作与高级功能迁移

优先级：P1

依次迁移：

1. Batch Processing。
2. Fractal Studio。
3. Texture Studio。
4. Shader Studio。
5. G'MIC。
6. Gradient Studio。
7. Photomosaic。
8. 图像融合。
9. 调色板。
10. 绘图与标注。

这一阶段主要处理复杂参数界面、生成器工作流、长时间后台任务和高级预览。

Shader Studio 必须进行真实图形会话验证，不允许只依赖无头测试。

验收：

- 每个模块独立加载。
- 参数修改真实有效。
- 后台任务支持取消。
- 预览和最终结果行为一致。
- GPU 渲染通过真实桌面环境验证。

### Phase 6：低频工具与 AI 功能迁移

优先级：P2

迁移范围：

- OCR。
- AI 背景移除。
- AI Upscale。
- AI 降噪。
- AI 色彩化。
- AI 模型管理。
- PDF 工具。
- EXIF 编辑。
- 水印。
- 条形码。
- 加密。
- Base64。
- 压缩与归档。
- 其他辅助工具。

不要求一次性复制参考项目所有边缘功能。

对未实现或依赖不完整的功能必须明确标注状态，不能通过仅仅注册功能名称就宣称已经完成。

验收：

- 真实输入输出测试。
- 依赖缺失时有明确提示。
- 模型下载和缓存不阻塞 UI。
- 失败任务可以恢复。
- 未完成能力有清晰状态。

### Phase 7：发布与工程化

优先级：P1

内容：

1. CMake Release 构建。
2. Python Worker 独立打包。
3. 资源与字体打包策略。
4. Linux 启动脚本。
5. 外部依赖诊断。
6. AppImage 或 Flatpak 发布方案。
7. CachyOS / Arch Linux 安装验证。
8. 日志和崩溃报告。
9. 完整安装测试。
10. 更新 README 与安装文档。

Linux 是第一阶段正式支持目标。

后续是否支持 Windows、macOS，单独立项，不与本次 Linux 迁移混在一起。

## 8. 测试体系

### 单元测试

- Python Engine 继续运行原有测试。
- C++ Services 独立测试。
- IPC 协议测试。
- QML 组件测试。
- 字体配置测试。
- 图像文档状态测试。

### 集成测试

至少覆盖：

1. 打开图像 → 修改参数 → 预览 → 应用 → 保存。
2. 打开图像 → 滤镜组合 → 撤销 → 重做。
3. 批量图像处理。
4. 分形生成。
5. Worker 中途取消。
6. Worker 崩溃。
7. 缺少 G'MIC 等外部依赖。
8. 大尺寸图像处理。
9. 不支持的文件格式。

### 视觉测试

保留关键界面的截图回归：

- 主窗口。
- 图片编辑器。
- 滤镜参数面板。
- 分形工作区。
- Shader Studio。
- Texture Studio。
- 设置页面。

重点检测字体、布局、文本截断、控件状态和主题变化。

### 真实环境测试

至少在以下环境验证：

- Linux Wayland。
- Linux X11。
- NVIDIA GPU。
- 系统字体缺失或回退。
- HiDPI 与不同缩放比例。

offscreen 测试不能代替真实桌面测试。

## 9. 非功能质量指标

- UI 主线程不得执行耗时图像处理。
- 图像预览支持防抖和任务取消。
- 大型图像避免无意义的完整副本。
- 页面切换不能泄漏资源。
- Worker 退出时正确释放任务和临时文件。
- 页面布局支持持久化。
- 所有操作提供明确的错误信息。
- GUI 能够独立于开发环境启动。
- 字体最终解析结果能够被诊断。
- 关键图像处理结果保持旧版本行为。

## 10. 开发规则

1. 采用阶段式开发。
2. 每个批次先分析需求，再检查相关代码、设计实现、测试和验收。
3. 只开发当前阶段的范围。
4. 不因为已经知道 P1/P2 的需求就提前实现它们。
5. 先建立兼容层，再迁移功能，不允许无计划删除旧实现。
6. 每个独立批次都需要测试和验收记录。
7. 新旧程序并行保留，直到新实现得到验证。
8. 不以功能注册数量代替真实完成度。
9. 不允许未经要求提交、推送、重置、切换、清理或改写 Git 历史。
10. 变更通过独立分支和 Pull Request 管理。

## 11. 风险管理

### IPC 性能

风险：大型图像在不同进程之间复制造成明显性能损失。

方案：Worker 持有图像文档状态，大型数据通过文件映射或共享内存传递。

### Python 打包

风险：OpenCV、NumPy、AI 相关依赖导致 Worker 体积增加或动态库冲突。

方案：基础引擎与可选 AI 依赖分开打包，采用独立诊断和可选资源安装方案。

### UI 迁移

风险：现有大量功能直接依赖 MainWindow 中的状态和方法。

方案：先提取稳定 Service API，再逐模块接入 QML，不直接把旧 MainWindow 整体翻译成 QML。

### Qt 许可

风险：不同 Qt 模块具有不同授权条件。

方案：正式发布前核对实际使用模块的 LGPL/GPL/商业许可及动态链接和再分发义务。

## 12. 最终完成标准

Toolbox 2.0 被认定完成，需要同时满足：

- 新 UI 完全采用 C++ + Qt Quick + QML。
- 桌面 UI 不再依赖 Python。
- 旧图像处理引擎已通过稳定接口接入。
- 所有 P0 核心工作流迁移完成。
- 计划范围内的 P1/P2 工具具有明确的真实完成度。
- 字体和主题系统完成现代化。
- 图像画布性能达到预期。
- Wayland 环境实机验收完成。
- 自动测试、集成测试及关键视觉测试通过。
- Linux 发布包能够在干净环境中安装和启动。
- 用户无需单独安装 Python。
- 文档与功能完成情况保持一致。

---

**项目总体原则：先解决架构边界，再构建新界面，最后分批迁移功能。不要把 UI 重写、图像算法重写和新增功能混为一个开发任务。**
