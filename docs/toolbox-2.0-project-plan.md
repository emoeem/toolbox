Toolbox 2.0：项目升级与实施总纲
文档类型： 产品定义、技术架构、UI/UX 设计、分阶段实施计划与 AI 编码代理工作规范
项目仓库： https://github.com/emoeem/toolbox
文档版本： 1.0
编写日期： 2026-11-06
当前项目阶段： Phase 0 代码工作已完成，目标 Linux 环境验收待执行
目标平台： Linux 桌面优先，Wayland 为第一验证目标
AI 编码环境： Windows 虚拟机（仅作为代码工作环境，不代表产品目标平台）

目录
1. 项目摘要
2. 项目现状与 Phase 0 状态
3. 产品目标与范围
4. 技术选型与架构决策
5. 总体架构
6. Python Worker 与 IPC 协议
7. UI/UX 设计阶段
8. 设计系统规范
9. 核心工作区与页面设计
10. 图像文档、画布与任务模型
11. 字体与主题系统
12. 渐进式目录结构
13. 分阶段实施路线
14. 测试、验收与质量门禁
15. Windows 虚拟机 AI 编码工作规范
16. Git 与变更管理规范
17. 风险与应对措施
18. 最终交付标准
19. 官方技术参考
1. 项目摘要
1.1 项目定位
Toolbox 是一个面向 Linux 桌面用户的专业图像处理与创作工具箱。它不应只是若干图片脚本的集合，而应逐步发展为具有统一工作流、统一画布、统一参数系统、统一任务管理和统一视觉语言的桌面创作软件。

项目覆盖的能力包括：
- 基础图像处理：亮度、对比度、色相、饱和度、曝光、裁剪、旋转、缩放与格式转换。
- 滤镜系统：基础滤镜、高级滤镜、可组合滤镜链、参数预览和预设。
- 图像分析：直方图、EXIF、图像比较、Checksum、重复图片检测等。
- 批量工作流：批量处理、批量转换、批量重命名和任务队列。
- 创作工具：渐变、分形、纹理、Shader、Photomosaic、图像融合和调色板。
- AI 能力：背景移除、超分辨率、降噪、色彩化及模型管理。
- 文件与辅助工具：PDF、OCR、水印、条形码、压缩、归档、加密和 Base64。
1.2 本次升级的核心决策
新 UI 使用 C++20 + Qt 6 Quick + QML；现有 Python 图像处理代码作为独立引擎保留，通过受版本控制的 IPC 协议接入。

本次升级不采用以下路线：
- 不继续以 Python + PySide6 Widgets 作为新 UI 的长期技术基础。
- 不把整个项目改造成 Electron 应用。
- 不在第一阶段重写所有图像处理算法。
- 不进行一次性全仓目录搬迁。
- 不把 UI 设计留到 QML 编码结束后补做。
- 不以功能注册数量、占位页面或静态按钮数量作为功能完成证明。
1.3 成功原则
1. 先确定产品信息架构和视觉方向，再开始大规模 UI 编码。
2. 先明确 UI、应用服务和 Python Engine 的边界，再迁移功能。
3. 先完成一个真实的端到端垂直工作流，再扩展其他页面。
4. 优先保留已存在且有测试的 Python 处理能力。
5. 每个功能必须有明确的真实完成状态和证据。
6. 所有耗时任务在后台执行，不能阻塞界面主线程。
7. 代码代理只负责代码和文档；Linux 运行时验证由指定的 Linux 环境执行。
2. 项目现状与 Phase 0 状态
2.1 现有技术基础
当前项目已经包含相当数量的图像处理能力，不是从空仓库开始。已知主要组成如下：
- app/：现有 PySide6 UI。
- processors/：NumPy、Pillow、OpenCV 等图像处理实现。
- backends/：外部工具与后端适配。
- tests/：现有单元测试与部分 UI 静态/生命周期测试。
- docs/：功能审计、Parity、代码审查和项目健康度文档。
- tools/：开发辅助工具。
- pyproject.toml / uv.lock：Python 项目配置与依赖锁定。
当前值得保留的核心资产包括：
- FilterDef / FilterChain 声明式滤镜体系。
- 参数定义驱动的滤镜参数控件。
- 后台任务、任务取消与预览缓存基础能力。
- 批量处理能力。
- 分形渲染框架，包括多种 2D 分形与 Mandelbulb 3D。
- Shader Studio、Texture Studio。
- G'MIC 适配及其他图像处理后端。
- 已积累的处理正确性测试、回归记录和功能审计。
2.2 Phase 0：当前完成情况
根据项目维护者提供的工作记录：
- 分支 phase0-font-system 已创建。
- Phase 0 的代码修改和文档编写已完成。
- 当前变更为 6 个修改文件 + 6 个新文件。
- 所有变更暂未提交，等待验收后再决定是否提交。
- AI/本机工作阶段没有安装或搭建 Linux、Qt 运行环境，也没有执行真实 GUI。
- Phase 0 的 Linux 环境验收仍待执行，不能将代码工作完成写成运行测试通过。
已完成的代码工作（按维护者记录）
字体修复：
1. 重写 app/fonts.py，默认使用系统字体，不再默认强制 MiSans。
2. 删除启动时递归扫描系统目录寻找 MiSans 字体的逻辑。
3. 增加系统字体、中文字体和等宽字体的解析/回退逻辑。
4. 增加 mono_font(settings)，让等宽字体设置真正应用到编辑器。
5. app/panels/shader_studio.py 中的 LineEditor 改为接收外部字体参数，不再硬编码 QFont("Maple Mono", 11)。
6. 删除 app/theme.py 中两处 QSS 全局字体强制规则，字号和字体交由应用字体系统控制。
7. 设置对话框增加“系统默认”字体项，保存使用 itemData，恢复默认时重置字体设置。
8. 增加字体诊断接口 diagnose()。
9. 重写 tests/test_fonts.py，使用真实字体解析相关断言，不再断言必须使用 MiSans；无字体环境采用防御性跳过。
图像处理迁移基线：
1. 增加 tools/make_test_samples.py，用于生成确定性的渐变、棋盘、噪声和合成图像样本。
2. 增加 tests/test_engine_baseline.py，覆盖已确认的 42 个 core 操作、样本与 IO 往返 SHA-256 基线。
3. 基线平台标签包含 NUMBA_OK 对应的 JIT 状态，避免 CI 无 numba 与其他环境存在差异时误报。
4. 基线文件由指定 Linux 环境生成；首次验收前不应手工伪造 tests/baselines/engine_baseline.json。
文档：
- docs/architecture.md：现状架构分析。
- docs/ui-migration-matrix.md：45 个工具、2 个 Studio 和全局功能的迁移矩阵。
- docs/phase0-acceptance.md：Linux 环境 Phase 0 验收清单。
- docs/upgrade-plan.md：项目升级计划存档。
- CHANGELOG.md：记录 Phase 0 代码工作和后续验收说明。
Phase 0 仍需 Linux 环境完成的事项
- 在指定 Linux 环境安装项目已声明的依赖。
- 运行现有全量测试和新增测试。
- 首次生成并审查 engine baseline 文件。
- 启动原有 Qt 程序，实际检查字体下拉框、字号、中文回退、等宽字体和 Shader Studio 编辑器。
- 根据结果修复问题，再决定是否提交 Phase 0。
状态口径： Phase 0 = 代码实现完成 / Linux 环境验收待执行。任何文档、PR 或 AI 汇报都必须保留这个状态区分。
2.3 已记录但本轮不处理的技术隐患
这些问题作为后续架构风险记录，不得在 Phase 0 以外顺手扩大修改范围：
1. processors/parity.py 中 run_parity_tool 存在双重定义，前一个定义可能被覆盖。
2. G'MIC 存在 processors/gmic.py 与 backends/gmic_backend.py 双轨调用。
3. 部分 AI、Parity、保存等长任务可能仍在 GUI 主线程运行。
4. numba 与纯 Python 路径的数值行为并不完全一致，基线比较必须标注环境。
5. 现有 MainWindow 职责过重，后续应通过服务层逐步解耦。
处理上述隐患必须进入对应阶段的独立任务，不得以“顺手整理”为由扩大当前任务。
3. 产品目标与范围
3.1 第一目标平台
第一阶段产品目标为 Linux 原生桌面应用：
- 首要验证环境：Linux + Wayland。
- 次要兼容验证：Linux + X11。
- 优先处理常见 Linux 桌面环境的窗口、文件选择器、拖放、剪贴板、字体和高 DPI 行为。
- 不为 Windows VM 的开发便利而把产品目标改成 Windows。
未来是否支持 Windows 或 macOS，需单独立项评估，不属于当前第一阶段交付承诺。
3.2 产品定位
Toolbox 应当同时具备：
- 专业图像编辑器的画布、预览、历史和检查器体验。
- 创作软件的独立工作区和生成器工作流。
- 工具箱的快速搜索、分类、批处理和实用工具入口。
- 桌面应用的可靠任务管理、设置、依赖诊断和文件工作流。
3.3 本次升级范围
必须完成（P0）
- 新 C++ / QML UI 工程骨架。
- UI 与 Python Engine 的稳定通信接口。
- 主窗口、导航、主题、字体、组件系统。
- 图片打开、显示、缩放、平移和保存工作流。
- 基础图像编辑与预览。
- FilterDef / FilterChain 的新 UI 接入。
- Undo / Redo 的明确数据模型。
- 任务进度、取消、异常和 Worker 生命周期管理。
计划完成（P1）
- 批量处理。
- Fractal Studio。
- Texture Studio。
- Shader Studio。
- G'MIC。
- Gradient / Photomosaic / Fusion 等创作工具。
- 完整的设置与依赖诊断。
后续完成（P2）
- AI 工具及模型管理。
- OCR、PDF、EXIF 编辑。
- 加密、归档、Base64、压缩等辅助工具。
- 低频或边缘功能。
功能优先级最终以 docs/ui-migration-matrix.md 为准。任何优先级变更都必须同步更新迁移矩阵。
3.4 明确不属于当前目标的事项
- 一次性全量重写 Python 算法为 C++ 或 Rust。
- 复制参考项目全部边缘功能以追求数量。
- 为所有工具分别设计完全不同的视觉体系。
- 第一阶段同时开发多平台安装包。
- 在缺乏验证的情况下宣称所有功能达到参考产品等价水平。
4. 技术选型与架构决策
4.1 最终推荐技术栈
层	技术	主要职责
桌面应用	C++20	应用生命周期、服务、模型、系统集成
UI 描述	QML	页面、交互、布局和动画
UI 渲染	Qt Quick / Scene Graph	现代桌面界面与图像视口
控件	Qt Quick Controls + 自定义组件	按钮、输入、滑块、菜单和检查器
构建	CMake + Ninja	C++ / Qt 构建
图像引擎	Python 3.11+	现有图像算法与处理工作流
图像计算	NumPy / Pillow / OpenCV / scikit-image	处理基础能力
可选加速	numba	现有 JIT 加速路径
后端	G'MIC 等外部工具	可选图像处理能力
Python 依赖	uv + 锁文件	Worker 依赖管理
C++ 检查	clang-format / clang-tidy	格式与静态分析配置
Python 检查	Ruff	格式/静态代码检查
测试	Qt Test / Qt Quick Test / Python unittest	分层自动测试


4.2 Qt 版本策略
- 采用 Qt 6，不再基于 Qt 5 设计新架构。
- 优先评估当前稳定的 Qt 6 LTS 版本，当前官方文档列出的 Qt 6.12 为 LTS 候选。
- 最终锁定版本前，应核对目标 Linux 发行版可获得的 Qt 包、图形驱动、编译器和部署方式。
- 版本号、最低 CMake 版本及最低 C++ 标准必须在 Phase 2 技术原型结束时形成明确记录。
- 不在代码中混用不同 Qt 小版本的非兼容 API。
4.3 为什么选择 Qt Quick + QML
- QML 采用声明式方式表达界面，适合复杂页面、可复用组件和参数面板。
- C++ 可以提供稳定的应用服务、模型和高性能绘制组件。
- Qt Quick Scene Graph 能为图像视口、交互和界面绘制提供适合的扩展点。
- Qt 的 Linux 桌面集成和已有 Python 生态更符合现有项目资产。
4.4 技术边界
QML 负责
- 页面结构和布局。
- 用户交互。
- 组件状态展示。
- 动画和过渡。
- 绑定 C++ 暴露的属性、模型和服务。
- UI 层输入校验和轻量展示逻辑。
C++ 负责
- 应用生命周期。
- 文档、工具、滤镜、任务和历史模型。
- Worker 启动、IPC、异常与资源生命周期。
- 文件系统和桌面能力适配。
- GPU 画布与图像纹理管理。
- 应用配置和系统诊断。
Python Engine 负责
- 图像处理算法。
- 现有 FilterDef / FilterChain 执行。
- 分形、纹理及现有生成器逻辑。
- G'MIC 等后端封装。
- 批处理与长时间计算。
- 算法相关缓存和必要的工作数据管理。
禁止事项： 不允许将图像算法直接写进 QML JavaScript；不允许让 QML 直接管理 Python 进程；不允许把全部 C++ 业务塞入 main.cpp。
5. 总体架构
5.1 逻辑结构
┌────────────────────────────────────────────────────┐
│                 Toolbox Desktop App                 │
│                                                    │
│  ┌──────────────────── QML UI ───────────────────┐  │
│  │ MainWindow / Navigation / Workspaces          │  │
│  │ Canvas / Inspector / Dialogs / Components     │  │
│  └──────────────────────┬────────────────────────┘  │
│                         │ typed properties/models   │
│  ┌──────────────────────▼────────────────────────┐  │
│  │                C++ Application                 │  │
│  │ DocumentService / ToolService / TaskService  │  │
│  │ FilterService / History / Settings            │  │
│  │ BackendManager / Canvas Renderer              │  │
│  └──────────────────────┬────────────────────────┘  │
└─────────────────────────┼──────────────────────────┘
                          │ versioned IPC
                          ▼
┌────────────────────────────────────────────────────┐
│                Python Worker Process               │
│                                                    │
│  Protocol / Dispatcher / Task Runtime              │
│        │                                           │
│        ▼                                           │
│  Existing processors / backends / generators      │
│                                                    │
└────────────────────────────────────────────────────┘
5.2 应用服务边界
建议建立以下 C++ 服务：
- BackendManager：启动、停止、监控 Worker，处理重启和版本握手。
- DocumentService：打开、关闭、保存文档，维护当前文档状态。
- ImageService：图像预览、缩放、转换和图像元数据接口。
- FilterService：滤镜列表、参数定义、预览、应用和预设。
- TaskService：统一创建、取消和跟踪任务。
- HistoryService：Undo / Redo 和历史状态协调。
- ToolCatalogService：工具分类、搜索、收藏和最近使用。
- SettingsService：字体、主题、布局和应用偏好。
- DiagnosticsService：Python、外部工具、图形能力和资源状态诊断。
服务只暴露 UI 必要的接口，不向 QML 暴露任意内部对象或处理器实现细节。
5.3 C++ Model 设计
需要优先建立：
- DocumentModel：打开文档、文档状态、路径、尺寸、色彩空间和修改状态。
- ToolModel：工具 ID、名称、分类、图标、关键词、状态。
- FilterModel：滤镜元信息、参数定义、能力和可用性。
- TaskModel：任务 ID、名称、状态、进度、错误和取消能力。
- HistoryModel：历史条目、当前节点、可撤销/重做状态。
- RecentFileModel：最近文件和时间信息。
列表和表格必须优先使用 Qt Model/View 方式暴露，而不是把大量独立属性塞进 QML。
5.4 迁移策略
- 先建立 python_worker 适配层，继续从当前 processors/ 和 backends/ 导入。
- 旧 app/ 在迁移期间保留，供原始功能、算法行为和界面工作流对照。
- 新 UI 逐个模块接入，不要求一开始移动整个 Python 包。
- 只有当所有引用、测试和打包路径稳定后，才讨论把 processors/ 移入更明确的 engine/ 包。
- 每次迁移都要记录旧入口、新入口、复用模块、差异和未完成项。
6. Python Worker 与 IPC 协议
6.1 Worker 运行方式
- Python Engine 运行在独立进程，不嵌入 C++ 主进程。
- C++ 通过 Qt QProcess 管理 Worker 生命周期。
- 第一版控制消息采用标准输入/输出上的 JSON Lines（每行一个 JSON 对象）。
- Worker 的标准输出只能写协议消息；日志和调试内容写标准错误。
- 必须定义协议版本、能力协商和 Worker 版本信息。
- Worker 不允许依赖当前工作目录才能找到处理模块。
6.2 控制消息协议
所有请求至少包含：
{
  "protocol": 1,
  "request_id": "req-0001",
  "action": "image.open",
  "params": {}
}
所有响应至少包含：
{
  "protocol": 1,
  "request_id": "req-0001",
  "success": true,
  "result": {}
}
任务进度事件：
{
  "protocol": 1,
  "type": "task.progress",
  "task_id": "task-0001",
  "progress": 45,
  "message": "Rendering preview"
}
错误事件/响应必须包含稳定错误码、可读消息和可选诊断详情：
{
  "protocol": 1,
  "request_id": "req-0001",
  "success": false,
  "error": {
    "code": "UNSUPPORTED_FORMAT",
    "message": "The image format is not supported",
    "details": {}
  }
}
必须支持的基础动作：
- worker.hello
- worker.shutdown
- capabilities.list
- image.open
- image.close
- image.metadata
- image.preview
- image.save
- filter.list
- filter.preview
- filter.apply
- task.cancel
- task.query
具体动作按阶段扩展，不能在每个 UI 页面中私自定义不同协议。
6.3 大图数据传递
- JSON 只传控制信息、参数、路径、ID、尺寸和元数据。
- 禁止将大型图像转成 Base64 后放进 JSON。
- 第一版优先使用受控临时文件作为图像结果交换方式，记录格式、尺寸、通道、色彩空间、文件长度和校验信息。
- 后续按性能数据引入 memory-mapped file 或共享内存。
- NumPy 侧可评估 memmap 或基于文件映射的读取方式。
- 所有临时资源必须有所有者、有效期和清理策略。
- 共享内存只能在确有性能收益、生命周期规则和错误恢复设计清楚后启用。
6.4 任务状态机
统一任务状态：
queued → running → completed
                 ↘ failed
                 ↘ cancelling → cancelled
要求：
- 所有任务有唯一 task_id。
- 取消是协作式取消，处理器必须在可取消点检查 token。
- 取消后不能再向 UI 推送过期结果覆盖新预览。
- 失败任务必须释放图像引用、临时文件和任务对象。
- Worker 退出时，前端必须将未完成任务标记为中断，并给出恢复方式。
- 进度事件必须节流，不能因高频信号造成界面卡顿。
- 所有异步响应都必须检查 request/task/document 的关联关系，防止旧任务污染新文档。
6.5 Worker 崩溃恢复
- C++ 检测进程退出码和异常退出。
- 提示用户未保存文档状态可能受影响。
- 能从原始文件重新打开的文档提供恢复入口。
- 对临时编辑状态要记录必要元数据，不得声称可以恢复未持久化的全部像素数据。
- 自动重启必须有限次，并防止崩溃循环。
- 重启后重新执行协议握手和能力探测。
7. UI/UX 设计阶段
UI/UX 设计是正式工程阶段，必须先于大规模 QML 页面实现。
7.1 设计目标
- 专业、清晰、现代，适合长时间桌面使用。
- 强调画布和内容，不让 UI 装饰抢夺图像注意力。
- 所有工作区使用同一组件体系。
- 高频功能易发现，低频功能通过搜索和分类到达。
- 支持深色与浅色主题。
- 支持窗口尺寸变化、面板收缩、隐藏和重新排列。
- 字体、对比度、焦点、键盘导航和状态表达必须一致。
7.2 参考方向
可研究以下软件的交互和布局，但不能复制其商标、专属图标或逐像素界面：
- Photoshop：画布、工具栏、图层/属性面板和图像操作习惯。
- Affinity Photo：工作区与上下文工具组织。
- DaVinci Resolve：复杂功能分区与专业工作流。
- Figma：检查器、组件系统和一致的交互反馈。
- Krita / GIMP：Linux 桌面图像编辑工作流和画布操作。
7.3 设计交付物
设计阶段至少交付：
1. 产品信息架构（IA）。
2. 全部页面清单和页面之间的导航关系。
3. 核心用户流程图。
4. 主窗口低保真线框图。
5. 编辑器、滤镜、批处理、Fractal、Shader、Texture 和 Settings 高保真设计稿。
6. 设计令牌（颜色、字体、尺寸、间距、圆角、阴影、动画）。
7. 核心组件库和组件状态说明。
8. 交互原型，包括弹窗、侧栏、面板、拖放、搜索和任务状态。
9. 空状态、加载态、错误态、无后端态、无可用滤镜态设计。
10. 窗口缩放和窄尺寸布局方案。
11. 设计决策记录，解释关键取舍。
建议使用 Penpot 等设计工具建立可维护的设计文件。设计稿是交互和视觉规范，不应被当成最终运行 UI。
7.4 设计验收
- 主窗口结构清楚，主次明确。
- 用户能够明确区分编辑工作区、生成器和工具页面。
- 同类组件外观、尺寸、交互一致。
- 主要流程无死路，错误和取消状态明确。
- 图像画布始终拥有足够空间。
- 深浅主题都具备可读性。
- 不同窗口尺寸下无明显重叠、裁切和控件失踪。
- 设计稿与实现任务存在可追踪映射关系。
8. 设计系统规范
8.1 视觉方向
建议采用中性、克制的专业创作工具风格：
- 深色主题以 Catppuccin Mocha 作为初始色彩参考，Mauve 作为少量强调色。
- 浅色主题采用中性灰白背景，保持足够文字和控件对比度。
- 画布周围使用低干扰的中性色，不要让界面底色明显污染用户对图像颜色的判断。
- 不使用大面积渐变、荧光色、重阴影或装饰性玻璃效果。
- 动画用于状态和层级过渡，不为了炫技而增加复杂动画。
最终色值以 UI 设计稿和设计令牌为准；不得在每个页面里写自己的颜色常量。
8.2 设计令牌
至少建立：
- color.background
- color.surface
- color.surfaceElevated
- color.border
- color.textPrimary
- color.textSecondary
- color.accent
- color.success
- color.warning
- color.error
- spacing.xs/sm/md/lg/xl
- radius.sm/md/lg/xl
- typography.ui
- typography.heading
- typography.numeric
- typography.monospace
- motion.fast/normal/slow
建议从 4px 间距基准开始，但必须通过设计稿统一，而不是机械地套用数字。
8.3 组件库
基础组件：
- AppButton
- IconButton
- ToolButton
- SearchField
- TextField
- NumberField
- SliderField
- SelectField
- ColorField
- ToggleField
- SegmentedControl
- Tooltip
- ContextMenu
- Dialog
- Toast
- ProgressIndicator
布局组件：
- AppSidebar
- TopToolbar
- InspectorPanel
- PanelHeader
- SectionGroup
- WorkspaceLayout
- StatusBar
- TaskQueuePanel
业务组件：
- ImageCanvas
- ImageThumbnail
- FilterCard
- FilterParameterGroup
- FilterChainItem
- TaskItem
- HistoryItem
- ToolCatalogItem
8.4 组件行为要求
所有组件必须定义：
- 默认态。
- Hover 态。
- Pressed 态。
- Focus 态。
- Disabled 态。
- Loading 态（适用时）。
- Error 态（适用时）。
- 键盘操作和可访问性语义。
业务页面不允许直接复制粘贴不同版本的滑块或按钮样式。
9. 核心工作区与页面设计
9.1 主工作台 / 首页
目标：提供统一入口，而不是把所有工具一股脑列成长列表。

内容：
- 最近打开文件或项目。
- 快速打开、拖放入口。
- 常用工具与收藏工具。
- 工具分类入口。
- 最近使用的工作区。
- 最近任务摘要。
- 后端状态摘要（不应占据首页主视觉）。
验收：用户不需要理解内部模块结构，也能快速进入常见任务。
9.2 图像编辑工作区
建议布局：
- 左侧：工具栏或工具分类。
- 中央：图像画布。
- 右侧：上下文参数检查器。
- 顶部：文件、撤销/重做、缩放、视图和上下文操作。
- 底部：图像尺寸、缩放比例、色彩信息和任务状态。
核心能力：
- 打开、拖放、保存和另存为。
- 缩放、平移、适配窗口、100% 原始比例。
- 透明棋盘背景。
- 图像尺寸和元数据。
- Undo / Redo。
- 预览与最终应用。
- 选区和后续图层/标注扩展接口。
9.3 滤镜工作区
- 按分类浏览滤镜。
- 搜索滤镜。
- 显示滤镜说明和可用性。
- 选择滤镜后显示统一参数控件。
- 支持低分辨率实时预览。
- 停止拖动后生成更高质量预览。
- 支持应用、重置、保存预设和组合滤镜链。
- 预览结果、应用结果和取消行为必须一致。
9.4 批量处理工作区
- 文件导入和拖放。
- 文件列表、缩略图、名称和状态。
- 批量操作配置。
- 输出目录、命名规则和格式选项。
- 任务队列、单项进度和整体进度。
- 失败重试和失败详情。
- 取消单项任务或整个队列。
- 完成后打开输出目录。
9.5 Fractal Studio
- 公式/类型选择。
- 预览画布。
- 复数参数和迭代参数。
- 着色和调色板。
- 缩放与导航。
- 渲染质量与取消。
- 分辨率、导出和预设。
不能把分形工作区设计成普通滤镜参数表。它是从参数生成图像的独立工作流。
9.6 Shader Studio
- GLSL 编辑器。
- 代码诊断和编译状态。
- 预览画布。
- Uniform 参数面板。
- Shader 模板和库。
- 保存、另存为和导出。
- 编译失败和运行时错误显示。
编辑器等宽字体必须来自统一字体服务。真实 OpenGL/Vulkan 渲染环境验证留给 Linux 目标环境。
9.7 Texture Studio
- 生成器和预设列表。
- 纹理预览。
- 参数检查器。
- 随机种子与可重复生成。
- 分辨率、平铺和导出设置。
- G'MIC 或外部后端状态。
9.8 AI 工作区
- 模型和功能列表。
- 模型状态（未下载、下载中、已就绪、不可用）。
- 输入图像和输出预览。
- 模型参数。
- 显存/内存需求提示（仅在能可靠获取时显示）。
- 任务进度、取消和失败原因。
模型缺失时必须优雅降级，不允许出现无响应按钮或虚假的“已支持”状态。
9.9 工具箱与辅助页面
PDF、OCR、EXIF、水印、加密、压缩、归档等低频能力可以使用统一工具页面模板，但必须保留各自真实的输入、输出和错误处理逻辑。
9.10 设置与诊断
分组：
- 外观：主题、字体、字号、动画偏好。
- 工作区：面板布局、默认工具、最近文件。
- 性能：预览质量、缓存、并发任务数。
- 后端：Python Worker 版本、路径、启动状态。
- 外部依赖：G'MIC、FFmpeg、Tesseract 等实际依赖状态。
- 存储：缓存、临时目录和预设目录。
- 关于：版本、协议版本、许可证和诊断信息。
10. 图像文档、画布与任务模型
10.1 Document 模型
一个文档至少需要以下信息：
- document_id
- source_uri 或原始文件路径
- 当前工作数据引用
- 图像宽、高、通道和位深
- 色彩空间 / ICC 信息（可获取时）
- 格式和元数据
- is_modified
- 当前预览版本
- 历史状态
- 资源占用和生命周期状态
UI 不应直接持有 Python ndarray，也不应把完整图像数组反复通过 QML 属性复制。
10.2 Image Canvas
画布至少支持：
- 缩放和平移。
- 适配窗口。
- 100% 查看。
- 原始尺寸和设备像素比例的正确处理。
- 透明棋盘格。
- 鼠标坐标。
- 高分辨率纹理。
- 预览版本切换。
- 后续选区、辅助线和比较模式扩展。
实现策略：
- QML 负责画布外围布局和轻量交互。
- 大图渲染由 C++ 图形组件负责。
- 根据实际需求实现 QQuickItem / Scene Graph 自定义节点。
- 不将持续高频更新的大图画布建立在昂贵的逐帧 CPU 绘制路径上。
- 纹理上传、图像色彩空间、高 DPI 和显存释放必须有明确策略。
10.3 预览机制
- 拖动参数时使用防抖。
- 生成低分辨率预览。
- 同一参数组合可命中预览缓存。
- 新预览请求应取消或废弃过时任务。
- 参数停止变化后再请求高质量预览。
- 结果必须携带 document/version/request 标识，避免旧结果覆盖新结果。
- 预览与最终应用调用相同的算法参数语义。
10.4 Undo / Redo
- 明确记录每次修改的命令、参数、输入/输出版本或可恢复快照。
- 不允许只在 UI 层维护一个与 Python Engine 不一致的历史列表。
- 大图快照要有内存预算和清理策略。
- 历史记录至少支持撤销、重做、重置、分支失效处理。
- Worker 重启后历史状态如何恢复必须明确；无法恢复时应诚实提示。
11. 字体与主题系统
11.1 字体原则
- 默认使用系统 UI 字体，不强制 MiSans。
- 字体解析必须有优先级和系统回退。
- 中文 UI 字体和英文 UI 字体可以分角色处理。
- 数字/代码使用独立等宽字体角色。
- Emoji 和符号走系统字体回退，不污染正文字体。
- 不在每次启动时递归扫描所有系统字体目录。
- 不为单一字体写死文件路径。
- 不因本机缺少某字体而导致应用启动失败。
11.2 字体角色
可选候选（实际匹配以目标系统字体数据库为准）：
- UI 中文：系统 Sans、Noto Sans CJK SC、Sarasa UI SC、LXGW ZhenKai 等。
- UI 西文：系统 UI Sans 或用户指定字体。
- 等宽：系统 Monospace、Maple Mono、JetBrains Mono 等。
- 特殊符号：系统符号/Emoji 字体回退。
字体候选不等于必须打包字体。是否随应用分发字体，必须单独检查许可证和体积影响。
11.3 字体设置
提供：
- UI 字体选择。
- 中文回退字体策略。
- 等宽字体选择。
- UI 字号。
- 等宽字号。
- 预览样例。
- 恢复系统默认。
- 字体诊断结果。
诊断至少区分：配置字体、Qt 解析字体、实际文本回退情况。不能仅检查设置字符串就声称字体已生效。
11.4 主题系统
- 深色主题和浅色主题都必须完整。
- 主题定义集中存放于设计令牌。
- 页面禁止散落硬编码色值。
- 画布预览区域要有中性背景策略。
- 主题切换不应重置用户布局和文档状态。
- 字体、对比度、焦点和禁用态都要有测试或验收证据。
12. 渐进式目录结构
12.1 迁移期间推荐结构
不要求第一阶段搬迁所有旧文件。建议先在仓库根目录添加新原生应用和 Worker 入口：
toolbox/
├── CMakeLists.txt
├── CMakePresets.json
├── pyproject.toml
├── uv.lock
│
├── native/
│   ├── app/
│   │   ├── main.cpp
│   │   └── application.*
│   ├── core/
│   ├── models/
│   ├── services/
│   ├── backend/
│   └── graphics/
│
├── ui/
│   ├── Main.qml
│   ├── pages/
│   ├── components/
│   ├── layouts/
│   ├── themes/
│   └── assets/
│
├── python_worker/
│   ├── main.py
│   ├── protocol.py
│   ├── dispatcher.py
│   ├── task_runtime.py
│   └── adapters/
│
├── app/                 # 旧 PySide6 UI，迁移期间保留
├── processors/          # 现有 Python 处理器，暂不整体搬迁
├── backends/            # 现有后端
├── tests/
│   ├── native/
│   ├── qml/
│   ├── integration/
│   └── engine/
├── tools/
├── docs/
└── packaging/
12.2 目录迁移规则
- Phase 0 不搬迁现有目录。
- Phase 1 只补充产品/UI 文档和设计资产。
- Phase 2 增加 native/、`ui/` 的最小原型。
- Phase 3 增加 Worker 与 IPC 适配层。
- 旧 app/ 在核心工作流完成迁移前保留。
- processors/ 和 backends/ 先作为稳定的内部 Python 包被 Worker 调用。
- 只有在迁移矩阵确认所有引用路径、测试和打包均已调整后，才允许搬迁旧包。
13. 分阶段实施路线
每个 Phase 都有独立范围、代码交付物、文档交付物和验收门槛。没有通过当前阶段的目标环境验收，不进入下一阶段的功能扩张。AI 编码代理可以先完成代码，但不能把待验收状态标成通过。

Phase 0：字体系统与迁移基线
状态：代码实现已完成；Linux 环境验收待执行。

工作内容已在第 2 章记录。后续只处理 Linux 验收发现的问题，不重复重写已完成内容。

完成条件：
- Phase 0 验收清单全部检查。
- 引擎基线文件由指定环境真实生成。
- 现有全量测试和 GUI 字体检查结果被记录。
- 修复完成后再由维护者决定提交。
Phase 1：产品信息架构与 UI/UX 设计
目标：先把 Toolbox 2.0 设计清楚，不直接开始大规模业务编码。

任务：
1. 审查 docs/ui-migration-matrix.md，确认工具分类和优先级。
2. 建立产品导航树和工作区关系。
3. 梳理 3 条核心用户流程：单图编辑、滤镜处理、批量处理。
4. 确定主窗口布局。
5. 设计首页、编辑器、滤镜、批处理、Fractal、Shader、Texture、Settings。
6. 建立颜色、字体、间距、圆角、图标和动画设计令牌。
7. 建立基础组件库。
8. 输出交互原型和异常/空/加载状态。
9. 记录桌面窄窗口和不同缩放比例的布局行为。
代码代理职责：可以创建 QML 设计令牌草案、组件 API 草案和设计文档；在设计稿确认前，不得自行大规模实现全套页面。

交付物：
- docs/product-information-architecture.md
- docs/user-flows.md
- docs/ui-design-system.md
- docs/ui-page-spec.md
- docs/ui-component-spec.md
- Penpot 设计文件或可追踪的设计稿链接（若项目采用 Penpot）。
验收：页面结构完整、关键流程闭合、设计语言统一，所有 P0 页面有明确布局和状态定义。
Phase 2：C++ / Qt Quick 技术原型
目标：建立可扩展的新原生应用骨架，不迁移全部功能。

任务：
1. 建立 CMake 项目入口。
2. 确定 Qt 6 LTS 版本和必要模块。
3. 建立 C++20 应用入口。
4. 加载 QML 主窗口。
5. 建立基础导航、页面路由和设计令牌。
6. 建立一个最小图像显示原型。
7. 建立一组 C++ Model 暴露给 QML。
8. 建立 C++ / QML 单元测试骨架。
9. 配置 clang-format、clang-tidy、qmllint 等静态质量工具。
本阶段不连接全部 Python 功能，不搬迁旧算法。

交付物：可独立构建的新项目骨架、架构说明、基础 QML 页面、模型示例和目标 Linux 验收清单。

验收：指定 Linux 环境能够构建并启动 Qt Quick 应用；Windows 代码工作环境不需要执行这一验收。
Phase 3：Python Worker 与 IPC 垂直切片
目标：从新 UI 调用一个真实旧处理器，证明架构可行。

任务：
1. 建立 Worker 启动入口。
2. 定义协议版本和错误码。
3. 实现 JSON Lines 读取和写入。
4. 实现 BackendManager。
5. 实现 worker.hello 能力握手。
6. 实现图像打开、简单处理和保存三个动作。
7. 实现请求关联、任务进度和取消。
8. 实现临时文件数据传递。
9. 实现 Worker 崩溃和重启状态处理。
10. 写协议单测和跨进程集成测试。
本阶段只选择简单、稳定、有现有测试的处理器做垂直切片，不迁移所有滤镜。

验收：新 C++ UI 能打开一张图、调用一个现有 Python 处理器、显示结果并保存；错误、取消和 Worker 退出都可被前端感知。
Phase 4：新 UI 基础设施与应用壳
目标：形成可持续开发的统一 UI 系统。

任务：
1. 主窗口和导航系统。
2. 页面路由和工作区容器。
3. 设计令牌和主题服务。
4. 字体角色和字体设置。
5. 基础组件库。
6. ToolCatalogModel 和搜索。
7. TaskModel 和任务队列面板。
8. SettingsService 和布局持久化。
9. Toast、Dialog、错误提示和空状态。
10. 基础可访问性与键盘导航。
验收：页面和组件不重复造轮子，主题与字体行为统一，应用状态和任务状态能够真实展示。
Phase 5：核心图像编辑工作流
目标：优先交付真正可用的图像编辑器。
5A：文件工作流
- 打开文件。
- 拖放文件。
- 最近文件。
- 图像元信息。
- 保存和另存为。
- 格式转换。
5B：画布
- 缩放和平移。
- 适配窗口与 100% 比例。
- 透明棋盘格。
- 鼠标坐标。
- 画布刷新和纹理释放。
- 高 DPI 基本行为。
5C：基础编辑
- 亮度、对比度、曝光、饱和度、色相。
- 裁剪、旋转、翻转、缩放和变换。
- 参数预览和应用。
- Undo / Redo。
- 重置。
5D：图像状态
- 修改状态。
- 保存状态。
- 历史记录。
- 任务取消。
- 失败提示和恢复。
验收：核心工作流端到端可用；处理输出通过既定基线或合理的逐像素/数值对照；UI 无长任务阻塞。
Phase 6：滤镜系统与创作工作区
按顺序迁移：
1. FilterDef 列表与分类。
2. 参数定义驱动的 QML 控件。
3. 预览与缓存。
4. FilterChain。
5. 预设保存与恢复。
6. G'MIC。
7. Batch Processing。
8. Fractal Studio。
9. Texture Studio。
10. Shader Studio。
11. Gradient、Photomosaic、Fusion 等。
每个 Studio 保留独立工作区布局，但共享主题、字体、任务、对话框和参数组件。

验收：算法行为与旧实现有证据对照；长任务不阻塞；参数和取消语义正确；图形功能在目标 Linux 图形会话下验证。
Phase 7：AI 与辅助工具
按迁移矩阵安排：
- AI 背景移除。
- AI Upscale。
- AI 降噪。
- AI 色彩化。
- AI 模型管理。
- OCR。
- PDF。
- EXIF。
- 水印。
- 条形码。
- 压缩、归档、加密和 Base64。
要求：模型和外部依赖状态必须真实；缺少模型或二进制时不得显示虚假的可用状态；失败和取消必须能够解释。

验收：每项功能都有输入、处理、输出、错误和依赖测试，完成度写回迁移矩阵。
Phase 8：打包、发布与最终质量验收
任务：
1. Linux Release 构建。
2. Worker 和 Python Runtime 打包。
3. 资源、字体和模型分发策略。
4. 外部二进制依赖诊断。
5. AppImage / Flatpak / Arch 包方案评估。
6. 安装、升级和卸载验证。
7. 干净用户环境启动验证。
8. Wayland 和 X11 验证。
9. 日志、崩溃和问题反馈能力。
10. 最终文档和版本发布。
验收：普通用户无需手工安装开发工具链即可安装和启动；缺依赖时有明确提示；安装包许可证和第三方依赖声明完整。
14. 测试、验收与质量门禁
14.1 测试分层
Python Engine
- 保留现有 unittest。
- 保留纯 Python 与 numba 路径测试。
- 保留确定性样本和 SHA-256 基线。
- 算法正确性优先于仅检查输出尺寸或非空。
C++
- Service 单元测试。
- Model 数据状态测试。
- IPC 编解码测试。
- Worker 生命周期测试。
- 临时资源释放测试。
QML
- 组件状态测试。
- 页面导航测试。
- 参数控件绑定测试。
- 空、加载、错误和禁用状态测试。
- 关键键盘交互测试。
集成
至少覆盖：
1. 打开图像 → 修改参数 → 预览 → 应用 → 保存。
2. 滤镜组合 → 预览 → 应用 → Undo → Redo。
3. 批量处理 → 进度 → 单项取消 → 失败恢复。
4. Worker 意外退出 → UI 状态更新 → 重新启动。
5. 缺少 G'MIC / AI 模型 / OCR 工具时的降级路径。
6. 大图和长时间处理。
真实目标环境
由指定 Linux 目标环境执行：
- Wayland 图形会话。
- X11（计划支持时）。
- NVIDIA 或其他实际目标 GPU。
- 高 DPI / 不同缩放比例。
- 字体缺失和字体回退。
- 安装包干净环境。
14.2 代码完成与验收通过必须分开
每项任务状态采用：
- planned：计划中。
- in_progress：开发中。
- code_complete：代码已写完，尚未完成目标环境验收。
- static_reviewed：完成静态审查，但未运行目标程序。
- runtime_verified：指定运行环境实际验证通过。
- accepted：维护者确认验收。
- blocked：存在阻塞问题。
AI 在 Windows VM 完成代码时，最多根据真实执行过的检查标记为 code_complete 或 static_reviewed。没有 Linux 目标环境证据，不得标记 runtime_verified 或 accepted。
14.3 CI 质量门禁
随着新项目建立，增加：
- C++ 格式和静态检查。
- CMake 配置/构建（在合适的 Linux CI runner 上）。
- QML 静态检查。
- Python Ruff。
- Python unittest。
- C++ 单元测试。
- QML 测试。
- IPC 集成测试。
CI 必须明确区分 Linux 目标测试与 Windows 代码工作环境，不以 Windows 构建结果代替 Linux 图形和打包验收。
15. Windows 虚拟机 AI 编码工作规范
本章是给 AI 编码代理的强制工作约束。优先级高于代理自行设想的开发流程。
15.1 环境定义
- AI 编码代理运行在 Windows 虚拟机中。
- Windows VM 是代码编辑、文件阅读、静态分析和文档编写环境。
- 产品目标仍然是 Linux 桌面。
- 不得把 Windows VM 当作最终运行或验收环境。
- 不要求 AI 在 Windows VM 安装 Linux 桌面、Wayland、GPU 驱动或真实 Linux 图形栈。
- 不要求 AI 在 Windows VM 搭建完整 Qt/Linux 运行环境。
15.2 AI 允许执行的工作
- 阅读仓库文件、README、文档、源码和 Git 历史。
- 检查调用关系、API、类型、配置和目录结构。
- 编写、修改和删除经当前任务授权的代码与文档。
- 新增或更新测试代码，为后续 Linux 环境验证做准备。
- 进行静态代码审查、文本搜索、差异审查和一致性检查。
- 检查 CMake、QML、Python 和资源引用是否前后一致。
- 更新迁移矩阵、CHANGELOG 和阶段状态。
- 汇报修改文件、关键设计、未解决问题和运行时待验收项。
15.3 AI 不允许擅自执行的工作
- 不启动最终桌面应用。
- 不声称完成真实 GUI 验收。
- 不在实体电脑上运行项目。
- 不为完成任务而擅自搭建完整运行环境。
- 不擅自安装系统级依赖、驱动、Qt SDK 或 Linux 桌面环境。
- 不执行会改变用户运行环境的安装脚本。
- 不把 Windows 本地构建成功描述为 Linux 目标平台构建成功。
- 不伪造测试结果、截图、性能数字或基线文件。
- 不用未执行过的测试命令宣称“测试全绿”。
如果当前任务明确要求只写代码，代理不得为了“验证”而擅自启动程序或安装环境。它应当编写必要测试，并把实际执行留给指定的 Linux 环境。
15.4 跨平台代码要求
虽然开发工具运行在 Windows VM，但目标代码面向 Linux：
- 路径处理使用跨平台 API，不拼接硬编码反斜杠。
- 不把 C:\\... 开发路径写入生产代码。
- 不依赖 Windows 特有进程、文件或图形行为。
- Worker 启动路径必须通过配置/应用资源定位机制计算。
- Python 子进程环境变量要显式管理，不依赖 Windows 用户全局状态。
- Linux 文件权限、可执行权限、临时目录和动态库问题写入 Linux 验收清单。
- 需要区分 Windows 代码编辑时的文件路径与 Linux 产品运行时路径。
15.5 每个 AI 开发批次的固定流程
1. 读取：先读取任务涉及的文件、接口、测试和当前文档。
2. 分析：说明现有行为、依赖关系、潜在副作用和最小修改范围。
3. 计划：列出准备修改的文件、实现方式和测试代码。
4. 实现：只完成当前任务范围，不提前开发后续 Phase。
5. 静态审查：检查旧 API 残留、导入、资源引用、类型、协议字段和目录引用。
6. 差异审查：检查完整 diff，不覆盖用户未要求的改动。
7. 记录：更新 CHANGELOG、迁移矩阵或阶段报告。
8. 交付：准确标记代码完成、静态检查完成和运行时待验收状态。
15.6 AI 汇报模板
每批开发完成后，按以下结构汇报：
# 本批次结果

## 1. 目标
本批次要解决的问题。

## 2. 修改内容
列出修改文件、新文件及各自用途。

## 3. 实现说明
关键设计、调用路径、接口变化和兼容性。

## 4. 静态检查
列出实际执行过的检查；没有执行就明确写未执行。

## 5. 运行时状态
默认写：未在 Windows VM 启动 Linux 目标程序，待指定 Linux 环境验收。

## 6. 风险与遗留问题
列出已知限制和下一阶段依赖。

## 7. Git 状态
说明当前分支、修改和未提交状态；不得擅自提交或推送。
16. Git 与变更管理规范
16.1 基本原则
- 每个 Phase 或明确独立的批次使用独立分支。
- main 保持受保护，按仓库既有 PR 流程合入。
- 当前 phase0-font-system 分支和未提交变更必须受到保护。
- 不得在 Phase 0 尚未验收时擅自覆盖、清理或重置它的工作。
16.2 禁止擅自执行的 Git 操作
除非维护者明确要求，AI 不得：
- git reset --hard
- git clean
- git checkout 到其他分支并覆盖工作区
- git switch 导致未提交变更丢失
- git stash 隐藏用户变更
- git rebase
- git commit
- git push
- 强制推送或改写历史
可以进行只读状态检查、diff 检查和普通代码阅读。创建分支、提交、推送、合并均需按维护者当前指令执行。
16.3 变更原则
- 一批次尽量只解决一个明确目标。
- 不做与任务无关的大规模格式化。
- 不顺手重命名大批模块。
- 不删除旧 UI 或旧处理器，除非迁移完成且任务明确授权。
- 协议变化必须更新协议文档、测试和版本兼容逻辑。
- 每次引入新的第三方依赖都必须记录用途、许可证、平台限制和可选/必选属性。
17. 风险与应对措施
17.1 IPC 数据传输开销
风险：大图在进程之间复制造成内存和性能损耗。

应对：第一版用 Worker 内文档状态和临时文件交换；通过实测数据决定是否引入内存映射或共享内存。不要过早实现复杂共享内存协议。
17.2 Python 打包复杂度
风险：NumPy、OpenCV、Pillow、numba 和 AI 依赖会增加发布包体积，并可能带来动态库冲突。

应对：基础处理依赖与可选 AI 依赖拆分；Worker 采用独立运行时；提供依赖诊断；发布前检查许可证和动态库。
17.3 QML 页面膨胀
风险：把复杂业务写在 QML 中，最终形成难以测试的页面脚本。

应对：QML 只组织视图；业务状态进入 C++ Model/Service；重复页面抽成组件；页面文件按工作区拆分。
17.4 图像画布性能
风险：大分辨率图像、频繁纹理上传、重复拷贝和预览刷新使界面卡顿。

应对：独立 Canvas Renderer；区分预览和最终图；任务版本化；有缓存预算；根据数据选择纹理和映射方案。
17.5 迁移期间功能回退
风险：新 UI 未覆盖旧 UI 的隐含行为。

应对：旧实现保留；迁移矩阵逐项记录；使用确定性样本；处理结果与基线对照；完成 Linux 验收后再决定淘汰旧入口。
17.6 视觉设计与实现偏离
风险：设计稿只是参考图，开发时各页面自行发挥。

应对：设计令牌、组件规格、页面规格和视觉测试都纳入交付；偏离必须写明原因并更新设计文件。
17.7 Qt 许可与第三方依赖
风险：Qt 模块、字体、图标和 Python 外部依赖有不同许可证要求。

应对：发布前核对实际模块和分发方式的许可义务；建立第三方组件清单、许可证文件和 Notices。不能把“开源”当作许可证审查的替代。
18. 最终交付标准
Toolbox 2.0 达到正式交付条件，必须同时满足以下要求：
架构
- 新 UI 完全使用 C++ + Qt Quick + QML。
- 新 UI 不依赖 Python GUI 框架。
- Python 作为独立处理 Worker 运行。
- IPC 协议有版本、测试和异常处理。
- C++ 服务、模型和 QML 页面分层清晰。
UI/UX
- 有完整设计稿和设计系统。
- 首页、编辑器、滤镜、批处理、Studio 和设置页面完成。
- 组件视觉和交互统一。
- 深浅主题正常。
- 字体和回退可诊断。
- 窗口大小和高 DPI 行为合理。
功能
- P0 核心图像工作流完整。
- P1/P2 按迁移矩阵逐项验收。
- 不以占位实现冒充完成。
- 图像输出有基线或明确对照证据。
性能与稳定性
- GUI 主线程不执行长时间图像处理。
- 大图预览和最终处理分离。
- 任务支持取消和异常恢复。
- Worker 退出时资源能够清理。
- 页面切换和窗口关闭不存在持续资源泄漏。
发布
- Linux 目标环境构建和启动成功。
- Wayland 第一验证目标通过。
- 安装包有清晰依赖和许可证说明。
- 普通用户不需要自己搭建 Python 开发环境。
- 文档和实际交付状态一致。
19. 官方技术参考
以下链接用于后续技术实现和 API 核对。具体 API 必须以项目最终锁定的 Qt 版本文档为准。
Qt / QML
- Qt Releases：https://doc.qt.io/qt.html
- Qt Quick 应用与 QML：https://doc.qt.io/qt-6/qtquick-index.html
- QML 与 C++ 集成：https://doc.qt.io/qt-6/qtqml-cppintegration-overview.html
- Qt Quick Scene Graph：https://doc.qt.io/qt-6/qtquick-visualcanvas-scenegraph.html
- Qt Quick C++ 扩展点：https://doc.qt.io/qt-6/qtquick-cppextensionpoints.html
- Qt Quick Controls：https://doc.qt.io/qt-6/qtquickcontrols-index.html
- Qt QML 测试：https://doc.qt.io/qt-6/qtquicktest-index.html
- Qt CMake：https://doc.qt.io/qt-6/cmake-get-started.html
进程与数据传递
- QProcess：https://doc.qt.io/qt-6/qprocess.html
- QSharedMemory：https://doc.qt.io/qt-6/qsharedmemory.html
- QFile：https://doc.qt.io/qt-6/qfile.html
字体与许可
- QFont：https://doc.qt.io/qt-6/qfont.html
- QFontDatabase：https://doc.qt.io/qt-6/qfontdatabase.html
- Qt Licensing：https://www.qt.io/licensing
附录 A：AI 新任务提示词模板
下面的模板可以作为每次交给 Windows VM 中 AI 编码代理的任务开头：
你正在维护 emoeem/toolbox 项目。请先阅读仓库根目录的
`docs/toolbox-2.0-project-plan.md`（或维护者指定的本总纲路径）、
`docs/architecture.md`、`docs/ui-migration-matrix.md` 和当前阶段验收文档。

强约束：
1. 你的工作环境是 Windows 虚拟机，产品目标是 Linux 桌面；不要混淆两者。
2. 当前任务只要求写代码、读代码和维护文档，不要求实机启动应用。
3. 不要安装系统依赖、Qt SDK、Linux 桌面或 GPU 驱动来搭建运行环境。
4. 可以增加测试代码，但没有在目标 Linux 环境执行就不得宣称测试通过。
5. 不要提交、推送、合并或重写 Git 历史，除非维护者明确要求。
6. 不要 reset、clean、stash、rebase 或切换分支覆盖当前工作。
7. 不要提前实现后续 Phase 的内容。
8. 不要为了界面方便把 Python 图像算法写进 QML。
9. 旧 processors/ 和 backends/ 是待复用资产，不得随意删除或整体搬迁。

本批次工作流程：
- 先读取涉及文件和调用关系；
- 给出最小修改计划；
- 仅实施当前任务；
- 静态检查旧 API、引用、协议和资源；
- 审查完整 diff；
- 更新必要文档；
- 汇报修改文件、实现内容、未执行的目标环境测试和剩余风险。

完成状态必须区分 code_complete、static_reviewed、runtime_verified 和 accepted。
目标 Linux 环境验收未执行时，只能报告代码已完成或静态审查完成。
附录 B：Phase 状态总表
Phase	名称	状态	关键交付
0	字体系统与迁移基线	代码完成 / Linux 验收待执行	字体修复、确定性样本、Engine 基线代码、架构文档
1	产品信息架构与 UI/UX 设计	未开始	页面树、用户流程、设计稿、设计系统
2	C++ / Qt Quick 技术原型	未开始	CMake、C++ 入口、QML 主窗口、图像显示原型
3	Python Worker 与 IPC	未开始	协议、BackendManager、真实处理器垂直切片
4	UI 基础设施	未开始	组件库、主题、字体、Model、任务和设置
5	核心图像编辑	未开始	文件、画布、基础编辑、历史管理
6	滤镜与创作工作区	未开始	FilterChain、Batch、Fractal、Texture、Shader 等
7	AI 与辅助工具	未开始	AI、OCR、PDF、EXIF 及低频工具
8	打包与正式发布	未开始	Linux 安装包、依赖诊断、实机验收和文档


维护原则：本总纲定义方向和阶段边界；阶段验收文档定义具体检查项；迁移矩阵定义每项功能的实际状态。三者必须保持一致。任何代码完成报告都不得替代目标 Linux 环境的运行时验收。