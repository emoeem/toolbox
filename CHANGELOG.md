# Changelog

## 2026-11-06 (Phase 4 — 新 UI 基础设施与应用壳)

依据总纲 `docs/toolbox-2.0-project-plan.md` Phase 4 任务清单完成：统一 UI
系统、基础组件库、设置/字体服务与任务队列。状态口径（总纲 §14.2）：本批
全部为 **code_complete / static_reviewed**；Linux 目标环境验收清单见
`docs/phase4-acceptance.md`，其中"任务面板随 Worker 事件更新"在 Worker 未
接入前如实标注 **Phase 3 验收后可验**，未执行任何目标环境运行验证。

> **CI 状态更新（同日后续）**：`phase4-ui-infra` 分支已达 **双 job 全绿**
> （test：307 Python 测试 + ruff；native：Build 零错误 + CTest 5/5 +
> clang-format 通过）。过程中 CI 实证修复：5 处编译错误（头文件路径、const
> 正确性、qmltyperegistrations include）、2 处运行期模型缺陷（TaskModel 空
> 变化发射、SettingsService 测试隔离失效——`setPath(IniFormat)` 不影响
> NativeFormat 实例，已改为显式 IniFormat 构造）、3 个 low 评审发现（mono
> 候选链补齐、Ctrl+Q 快捷键、NumberField 悬停穿透）。另：旧测试套件退出期
> heap corruption 经 gdb 与 main 对照组证实为 **main 既有缺陷**，以
> tearDownModule 收集 + CI 端 os._exit 绕过处理；CI 增设 clang-format
> 自动格式化机器人（PointerAlignment 修正为 Right）。Linux 实机 GUI 验收
> 仍待 `docs/phase4-acceptance.md` 执行。

### Added（C++ 服务与模型）

- `native/services/settings_service.{h,cpp}`：QSettings("Emo","Toolbox2")
  扁平键值外观（QML 单例）。键位与默认值见头文件键表：主题模式
  dark/light/system（默认 system，非法值归一化）、布局持久化
  layout/navExpanded 与 layout/inspectorCollapsed、字体 font/family 与
  font/mono 与 font/size（默认 11，镜像 app/fonts.py resolve_size）、
  preview/quality、tasks/concurrent、backend/python 与 backend/repoRoot
  （`Application::startBackend()` 经 value() 读取）。每次写入后 sync()；
  `addRecentFile` 最近文件去重置顶、上限 10；`resetLayout` 仅复位布局组；
  破损存储值回落默认而不传播。
- `native/services/font_service.{h,cpp}`：字体角色解析与诊断（QML 单例），
  镜像 app/fonts.py 语义——空族=平台默认、UI 走 SansSerif+抗锯齿+完全
  hinting、等宽走 Monospace hint；`resolveFamily` 候选链回退（sans/mono
  候选链内置于服务，与设置页共享）；`applyToApplication` 全局应用字号
  （非正值回落 11）；`diagnose` 返回 ui/mono 两段的 requested/resolved/
  size/coverage/fallback，coverage 固定五类（latin/digit/cjk/symbol/
  emoji），未覆盖类给出 ≤8 项回退族。
- `native/models/task_model.{h,cpp}`：Worker 驱动的任务行模型
  （QAbstractListModel）。trackRequest 记录 request_id→任务名；成功响应
  携带 result.task_id 建行（未跟踪/失败/同步响应不建行）；task.progress
  更新进度（夹取 0-100）；task.completed / task.failed 终态，CANCELLED
  呈现为 cancelled 而非 failed；cancelTask 将活跃行置 cancelling 并转发
  BackendManager，终态行本地拒绝（协议 §7）；终态行保留上限 64、FIFO
  裁剪且永不裁剪活跃行。角色名 taskTaskId/taskName/taskStatus/
  taskProgress/taskError 与 AppTaskItem.qml 契约一致。
- `Application` 扩展：暴露 taskModel/settingsService/fontService 属性与
  `startBackend()`（从 SettingsService 读取 backend/* 后配置并启动
  BackendManager）。

### Added（QML 组件库与应用壳接线）

- `ui/components/` 28 个 App 前缀组件（基础/布局/业务三层，全部仅引用
  Theme 令牌）：AppButton、AppIconButton、AppToolButton、AppTextField、
  AppNumberField、AppSliderField、AppSelectField、AppColorField、
  AppToggleField、AppSegmentedControl、AppSearchField、AppTooltip、
  AppContextMenu、AppDialog、AppToast、AppProgressIndicator、
  AppPanelHeader、AppSectionGroup、AppInspectorPanel、AppSidebar、
  AppTopToolbar、AppStatusBar、AppWorkspaceLayout、AppTaskItem、
  AppTaskQueuePanel、AppHistoryItem、AppImageThumbnail、
  AppToolCatalogItem。
- `ui/Main.qml`：SettingsService.themeMode 驱动 Theme.darkMode；状态栏
  实时显示 BackendManager 状态；AppTaskQueuePanel 底部抽屉绑定
  Application.taskModel。
- `ui/pages/SettingsPage.qml`：外观（主题三态、字体族/字号、字体诊断）、
  工作区（布局持久化状态 + 重置布局）、后端（python/repoRoot 配置、
  启动按钮、Worker 状态）四个分区真实读写服务；HomePage 接入
  SettingsService.recentFiles 最近文件（只读展示）。

### Added（测试）

- `tests/native/test_task_model.cpp`：以真实 BackendManager（不启动
  Worker）直接 emit responseReady/taskEvent 信号模拟协议事件，覆盖建行
  条件、进度夹取、终态/取消呈现、cancelTask 转发与终态拒绝、64 条终结
  保留上限与活跃行保护；角色名断言锁定 QML 契约。
- `tests/native/test_settings_service.cpp`：QTemporaryDir 隔离 store 的
  默认值、读写往返、信号去重、破损存储回落、主题归一化、addRecentFile
  空值/去重/上限 10、resetLayout 仅动布局组。
- `tests/native/test_font_service.cpp`：resolveFamily 候选链回退（无字体
  环境 QSKIP，镜像 tests/test_fonts.py 口径）、diagnose ui/mono 五类覆盖
  键结构与回退列表上限、非正字号回落 11、applyToApplication 全局应用。
- `tests/native/CMakeLists.txt` 注册 task_model / settings_service /
  font_service 三个 CTest 目标（与既有两目标同一模式：被测源文件直接
  编入测试目标）。

### Added（文档）

- `docs/phase4-acceptance.md`：Linux 目标环境验收清单（构建、CTest 全绿、
  GUI 启动、主题/字体设置真实生效、布局持久化、任务面板随 Worker 事件
  更新——Worker 未接前如实标注 Phase 3 验收后可验）。

### 已知限制（如实记录）

- 任务面板行更新在真实操作流中不可验：UI 内尚无发起异步动作的入口，
  端到端复核依赖 Phase 3 垂直切片可用，接线随 Phase 5 文件工作流完成。
- AppSidebar/AppInspectorPanel 尚未读写 layout/* 键（折叠交互随对应
  工作区页面交付），本阶段布局持久化以 store 往返与设置页读写为准。
- 设置测试的 store 隔离依赖 Linux 原生格式为 INI（QSettings::setPath
  重定向）；Windows 原生格式为注册表，重定向不生效。

## 2026-11-06 (Phase 1-3 — 设计系统、Qt Quick 原型与 Worker/IPC)

依据总纲 `docs/toolbox-2.0-project-plan.md` 完成三个阶段的代码/文档工作。
状态口径（总纲 §14.2）：本批全部为 **code_complete / static_reviewed**；
Linux 目标环境验收见 `docs/phase2-acceptance.md`、`docs/phase3-acceptance.md`，
未执行任何目标环境运行验证。

### Phase 1（设计交付物，全部为文档）

- `docs/ui-design-system.md`：设计令牌定稿（Catppuccin Mocha 深色 + 中性浅色、
  Mauve 强调色的可访问浅色变体）、间距/圆角/字排/动效/布局常量、组件状态与
  可访问性要求。
- `docs/product-information-architecture.md`：导航树、页面清单与导航关系、
  主窗口五区布局、P2 入口的诚实状态表达。
- `docs/user-flows.md`：三条 P0 核心流程（单图编辑/滤镜处理/批量处理）+
  共用异常路径。
- `docs/ui-page-spec.md`：P0 四页与 P1 Studio 页的布局规格与状态定义。
- `docs/ui-component-spec.md`：组件库 API 草案（基础/布局/业务三层）及与
  IPC 动作的对接关系。
- `docs/toolbox-2.0-project-plan.md`：总纲存档（附录 A 指定路径）。

### Phase 2（C++ / Qt Quick 技术原型，code_complete）

- 构建体系：根 `CMakeLists.txt`（Qt ≥ 6.4 下限 / C++20 / 预留 Phase 3 backend
  源）+ `CMakePresets.json`（linux-debug / linux-release / linux-ci）。
- C++：`native/app/`（main.cpp、Application QML 单例：导航/工具目录/页面路由/
  版本信息）、`native/models/`（ToolModel + NavModel，QAbstractListModel +
  QAbstractItemModelTester 契约测试）、`native/graphics/`（ImageCanvas：
  QQuickItem + QSGSimpleTextureNode，滚轮指针锚定缩放/拖动平移/双击适配/
  100%/图像空间棋盘格合成，纹理仅在 updatePaintNode 上传）。
- QML：`ui/themes/Theme.qml`（与设计系统文档逐令牌对应的单例）、
  `ui/Main.qml`（令牌驱动的应用壳 + Loader 路由）、`ui/components/AppSidebar.qml`
  （P2 项禁用 + 阶段标注）、`ui/pages/`（Home/Editor 真实骨架；Batch/Fractal/
  Shader/Texture/Planned 为诚实计划状态页；Settings 含可用的主题切换）。
- 质量工具：`.clang-format`（Qt 风格）、`.clang-tidy`（保守基线）。
- 测试：`tests/native/test_models.cpp`（模型契约 + QML 角色名锁定）。

### Phase 3（Python Worker 与 IPC 垂直切片，code_complete）

- 协议：`docs/ipc-protocol.md`（JSON Lines、消息形状、动作表、错误码、
  握手/崩溃恢复/取消语义、版本策略、临时文件数据传递规则）。
- Python 侧 `python_worker/`：`protocol.py`（编解码/校验/错误码）、
  `task_runtime.py`（线程池 + queued/running/completed/failed/cancelling/cancelled
  状态机 + 100ms 进度节流 + 复用 processors.cancellation.CancelToken）、
  `dispatcher.py`（同步/异步动作表：worker.hello/shutdown、capabilities.list、
  image.open/close/metadata/save、filter.list/preview/apply、task.cancel/query）、
  `adapters/`（DocumentStore 文档表 + FilterDefRegistry/FilterChain 协议化，
  import processors 仅发生在适配层）、`main.py`（stdin 主循环、双运行方式
  bootstrap、信号优雅退出；stdout 只写协议消息，日志走 stderr）。
- C++ 侧 `native/backend/`：`ipc_protocol.{h,cpp}`（消息构造/分类/校验/错误码）、
  `python_worker.{h,cpp}`（QProcess + 行分帧 + stderr 尾部留档）、
  `backend_manager.{h,cpp}`（握手超时 5s、崩溃检测与 ≤3 次自动重启、
  Stopped 状态不误报崩溃、request_id 关联）。
- 测试：`tests/test_worker_protocol.py`（编解码/分发/异步任务/取消/节流，
  纯进程内、CI 可跑）、`tests/native/test_ipc_protocol.cpp`（消息形状锁定）。
- CI：新增 `native` job（ubuntu + 发行版 Qt 6 开发包：CMake preset 构建、
  clang-format 门禁、clang-tidy 咨询性检查、CTest）。

### 已知限制（如实记录）

- C++/QML 代码未在任何环境编译运行（Windows 侧无 Qt 工具链，按总纲 §15.3
  不搭建）；编译期错误风险由 CI `native` job 兜底。
- 垂直切片的 QML 交互接线（编辑器按钮直接调用 BackendManager）未实现——
  Phase 3 验收允许以 C++ 测试驱动，QML 全面接线归 Phase 4。
- Worker `image.open` 当前为同步动作（大图打开会占一个任务线程直至完成），
  异步化列入 Phase 4 任务清单。

## 2026-11-05 (Phase 0 — 字体系统修复与迁移基线)

Toolbox 2.0 升级的 Phase 0（升级计划见 `docs/upgrade-plan.md`）：修复字体
强制覆盖体系，建立 UI 迁移所需的架构文档与引擎行为基线。

### Changed（字体系统）

- **删除 QSS 全局字体强制**（`app/theme.py`）：浅色/深色两处
  `* { font-family: "MiSans"...; font-size: 13px }` 移除。此前该规则覆盖
  `QApplication.setFont()`，导致设置中的字体族与字号均不生效。
- **删除启动时全目录字体扫描**（`app/fonts.py`）：`ensure_packaged_misans()`
  每次启动对 `~/.local/share/fonts`、`/usr/share/fonts`、`~/.fonts` 递归
  `rglob` 查找 MiSans 的逻辑整体移除。
- **`app/fonts.py` 重写**：默认字体改为系统默认（空 family → 平台
  fontconfig/平台解析），MiSans 不再硬编码为首选与默认值；等宽字体新增
  `mono_font()`（候选链 Maple Mono/JetBrains Mono 等 → `QFont.Monospace`
  hint 系统等宽回退），并新增诊断接口 `glyph_coverage()` /
  `fallback_candidates()` / `diagnose()`（基于 QFontInfo/QRawFont，可查询
  中文/英文/数字/符号/Emoji 的实际解析与回退，对应"字体最终解析结果可诊断"）。
- **等宽字体设置真正生效**：Shader Studio 代码编辑器由硬编码
  `QFont('Maple Mono',11)`（`app/panels/shader_studio.py`）改为接收
  `mono_font(settings)` 解析结果。
- **设置对话框**（`app/main_window.py`）：字体/等宽下拉框新增"(系统默认)"
  项（存空值）；保存改用 `currentData()`，修复选中具体字体时误存显示文本的
  隐患；"恢复默认"现在同时重置字体三项（此前遗漏字体）。

### Fixed（测试）

- `tests/test_fonts.py` 重写：删除"QSS 必须含 MiSans"的强制断言；改为断言
  主题不强制字体族/字号/不含 MiSans，并新增系统默认解析、显式族应用、缺失
  回退、等宽 hint/应用、五类字符覆盖与诊断结构的真实解析测试（无字体环境
  自动 skip，兼容 CI 容器）。

### Added（迁移基线）

- `tools/make_test_samples.py`：4 张确定性测试样本（渐变/棋盘/噪声/合成，
  固定参数与种子，不依赖外部图片）。
- `tests/test_engine_baseline.py`：核心引擎行为基线 —— 样本哈希 + 42 个
  core 算子输出 + save/load 往返的 sha256 对照（`TOOLBOX_REGEN_BASELINE=1`
  重新生成；平台标签含 Python 版本与 numba 状态，环境不一致时 skip 不误报）。
  首次在 Linux 虚拟机运行后提交 `tests/baselines/engine_baseline.json`。
- `docs/architecture.md`：现状架构分析（MainWindow 上帝对象、4 种 processors
  调用模式、线程/取消体系、撤销、持久化、已知隐患，全部带 file:line 证据）。
- `docs/ui-migration-matrix.md`：全部 UI 功能 → 2.0 八大工具类 → 目标 Phase
  的迁移矩阵，含外部依赖汇总与未实现功能真实状态标注。

## 2026-09-29 (第三轮 — 手工运行发现的崩溃)

实际运行 `main.py` 时暴露的一批"点击才触发"的缺陷。这类问题不会被单元测试
发现，因为没有任何测试会去点那些按钮 —— 已补充静态与生命周期回归测试。

### Fixed

- **`self.preview.get_image()` 不存在（14 处调用点，13 个功能全部报
  `AttributeError`）**。`ImagePreview` 的访问器是 `current_image()`，
  `get_image()` 从未存在过。受影响：图像对比、差异图、图像校验和、条码/二维码
  解码、形状遮罩、直方图、拼接/拼贴/分割、LUT 预设、曲线预设、智能缩放
  （preset/custom/size）。全部改为 `current_image()`。
- **3 处 `NameError`（模块未导入）**：
  - `_apply_lut_preset()` 使用裸 `lut.`，但只导入了 `LUT_PRESETS`，且 `lut`
    仅在**另一个**函数里局部导入 —— 运行时 `NameError: name 'lut' is not defined`；
  - `_make_mesh_grad()` 使用裸 `gradients.`（同样只导入了 `MESH_PRESETS`）；
  - 批量转换的 `conv_worker()` 使用裸 `utils.load_image/save_image`，改用模块级
    已导入的 `load_image` / `save_image`。
- **撤销 / 重置在切换工具后崩溃**
  `RuntimeError: libshiboken: Internal C++ object (QListWidget) already deleted`。
  面板在切换工具时通过 `setParent(None)` + `deleteLater()` 销毁，但 Python
  属性仍指向已析构的 C++ 对象；`undo()` / `reset_all()` 是跨面板可达的
  （前者还有全局快捷键），因此 `_refresh_chain_list()` 与
  `filter_param_widget.reset_to_defaults()` 会踩到已删除对象。
  原有 `hasattr(self, '_refresh_chain_list')` 这类守卫是无效的 —— 方法一直存在，
  需要检查的是 **widget 本身是否还活着**。新增 `_widget_alive()`
  （基于 `shiboken6.isValid`）并在两处加守卫。

### Added — Tests

- `tests/test_main_window_static.py`（5 项）：
  - `test_every_preview_method_used_exists` —— 扫描 `main_window.py` 里所有
    `self.preview.<名字>`，断言它们在 `ImagePreview` 上真实存在（可捕获本次
    14 处同类缺陷）；
  - `test_main_window_module_references_are_imported` —— AST 逐函数分析，
    断言函数内用到的 `processors` 子模块在该作用域可见（可捕获本次 3 处
    `NameError`，且能区分"在别的函数里导入过"这种假阴性）；
  - 生命周期用例：切换面板销毁 Filter panel 后 `undo()` / `reset_all()` 不得抛错，
    以及从未构建 Filter panel 时 `reset_all()` 可用（preview 的 Esc 快捷键路径）。

两个静态用例都做过变异验证：把 `get_image()` 或未加守卫的
`self._chain_list.clear()` 放回去，对应用例立即失败。

### Verification

- `QT_QPA_PLATFORM=offscreen TOOLBOX_NO_NUMBA=1 .venv/bin/python -m unittest discover -s tests`
  → **268 tests / OK（1 skipped）**
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_fractal tests.test_filter_robustness tests.test_core` → 56 tests / OK
- `_smoke_test.py` → ALL SMOKE TEST PASSED
- 逐个驱动真实 UI 处理函数验证（对比 / 差异图 / 校验和 / 条码 / 直方图 /
  形状遮罩 / 拼接 / 拼贴 / 分割 / LUT / 曲线 / 智能缩放 x3）均已通过。

---

## 2026-09-29 (第二轮 — 代码审查 / Bug 修复 / 性能优化)

审查范围：全仓库约 12.5k 行。所有结论均由可重复命令或实测数据支撑；详见
[`docs/code-review-fixes.md`](docs/code-review-fixes.md)。

### Fixed — 严重正确性

- **`processors/core.py` `contrast()` 公式漏除 255**（未提交改动引入）：对比度系数被放大约 255 倍，
  把图像压成约 3 个色调。实测 89488 色 → 20 色；任何"应用调整"都会破坏图像。
  修复后与参考曲线**逐像素完全一致**。
- **`processors/core.py` `hue_shift()` 用 `% 180` 环绕**：输入为 float32 时 OpenCV hue 量程是
  0..360（uint8 才是 0..180），导致色相环被折半 —— `+180°` 对红/绿完全无效，H≥120 的色相全部错位。
  改为 `% 360`，12 个色相带 × 6 种偏移全部校验通过。
- **`processors/filter_defs.py` `FilterDef.apply()` 吞掉真实 `TypeError`**：`except TypeError`
  无法区分"处理器不接受该关键字参数"与"处理器内部抛 TypeError"，会把滤镜**用默认参数重跑一遍**，
  静默产出错误结果。改为用 `inspect.signature` 过滤参数，错误立即上抛（调用次数 2 → 1）。
- **撤销（Undo）对滤镜/变换路径完全失效**：`_push_history()` 在 `set_display()` 之后调用，
  快照的是**新图**，撤销等于空操作。重构为 `_commit_image()`（先快照 → 再显示 → 标记已应用），
  11 条真实 UI 路径已验证撤销可恢复。
- **保存崩溃**：`self._applied_image or self.preview.current_image()` 对 ndarray 求布尔值，
  应用过任何编辑后保存必抛 `ValueError: truth value of an array is ambiguous`。
- **`processors/filters.py` `dither_bayer()` 缺一个冒号**：`[:h, w]` 实际是单列索引，
  非正方形图直接崩溃，正方形图则用单列广播抖动。修正为 `[:h, :w]`。
- **`processors/filters.py` `old_tv()` 扫描线无法广播**：`(h, 1)` 对 `(h, w, 3)` 只在 h == w 时成立，
  **所有非正方形图都崩溃**。改为 `scanlines[..., None]`。
- **`processors/filters.py` `anaglyph()` 窄图 shift=0**：`w < 50` 时 shift 为 0，
  产生空切片赋值 `ValueError`。改为 `max(1, ...)` 并夹取边界。
- **退化尺寸崩溃**：`kaleidoscope` / `mirror_reflection` / `dual_split` / `reduce_colors` / `glitch`
  在 1×1、2×2、5×3、3×200 等尺寸下抛异常（空切片、kmeans 簇数 > 样本数、`randint(0, 0)`）。
- **`app/panels/shader_studio.py` `LineEditor`**：`_gutter` 只在 `resizeEvent` 中惰性创建，
  而 `updateRequest` 会先触发，首次布局即产生 `AttributeError` 回溯。改为构造时创建。
- **`app/workbench.py` 失败任务永久泄漏**：`Task._all_tasks` 是类级强引用列表，
  只有 `finished`/`cancelled` 会调用 `_cleanup_task()`，`failed` 不会。每次滤镜失败都会永久泄漏
  Task 对象及其闭包捕获的**全分辨率图像**（24MP 约 72MB/次）。实测 5 个失败任务 100% 残留。

### Fixed — 健壮性

- **只读目录被误判为可用**：`mkdir(exist_ok=True)` 对**已存在的只读目录也会成功**，
  因此不能用来决定缓存/预设目录。新增 `processors.utils.ensure_writable_dir()`（用真实临时文件探测），
  预设目录与 GMIC 缓存目录在只读 HOME / 容器 / NFS 下会回退到系统临时目录，而不是抛裸 `OSError`。
  这同时让 5 个原本失败的预设测试转为通过。
- **预设非原子写**：改为临时文件 + `fsync` + `os.replace`；`list_presets()` 不再静默丢弃损坏预设
  （新增 `include_errors=True`）。
- **外部工具无超时且可能挂起**：`processors/media.py`（magick/ffmpeg）、`processors/parity.py`（cjxl）、
  `processors/gmic.py` 补上超时。另外发现 **`gmic` 在 stdin 非终端时会读取命令管道并永久阻塞**
  （管道输入下无限挂起、`< /dev/null` 才返回），已对全部 gmic 调用加 `stdin=subprocess.DEVNULL`。
- **滤镜链取消未真正打通**：`FilterDef.apply()` 从不把 `cancel_token` 转发给处理器，
  因此声明了 `cancel_token` 的处理器（如 `parity.generate_fractal`）内部检查全是死代码。
- **`preview_widget`**：`_numpy_to_pixmap()` 现在对非连续数组做 `ascontiguousarray`
  （`QImage` 直接包裹 numpy 缓冲，stride 不符会导致图像错位）；`paintEvent` 不再调用会触发
  `update()` 的 `fit_image()`；空状态提示里的 `\\n` 是字面反斜杠而非换行；删除死代码 `_dark_background()`。
- **任务池并发 8 → 4**：单条 24MP float32 流水线中间量约 288MB，8 条并发峰值可达数 GB；
  关窗时 `TaskQueueWidget.shutdown()` 有界等待，避免退出被最长滤镜卡住。
- **测试套件全局单例污染**：`tests/test_filter_chain_task.py` 注册的 `_test_boom`（故意抛异常）
  会泄漏到 `FilterDefRegistry` 全局单例，影响其他模块（已实测导致假失败）。
  新增 `FilterDefRegistry.unregister()` 并在 `tearDownModule` 中清理，已验证执行顺序无关。

### Performance

实测环境：24MP (6000×4000) / 12MP / 1200×1600，numba 0.67 可用。

| 项目 | 优化前 | 优化后 | 说明 |
|---|---|---|---|
| 调整面板「应用调整」（GUI 线程阻塞） | 2760 ms | **1.2 ms** | 跳过默认值步骤 + LUT + 转后台任务；后台 78 ms 完成，约 35x |
| `floyd_steinberg` | 4479 ms (600×800)，24MP 约 220 s | **5.2 ms**，24MP 约 0.4 s | numba JIT + 分行；**逐像素一致**，约 550x |
| `circular_pixelation` | 204 ms (1200×1600) | **21 ms** | 向量化 + 删除死代码；**逐像素一致**，约 10x |
| `brightness` / `contrast` / `exposure` | 65 / 103 / 66 ms (12MP) | **13~15 ms** | 256 项 LUT；**逐像素一致**，4~8x |
| `vignette` | int64 索引图 → float64 距离图，每次重算 | 中间量减半 | 改 float32 并按尺寸缓存掩膜 |
| 参数预览：每次滑块 tick 重算降采样 | 60 ms/次 (48MP) | **0.018 ms** | 按 (identity, size, generation) 缓存 |
| 撤销历史内存 | 30 张全分辨率副本 ≈ **2.1 GB** (24MP) | ≤ 512 MB | 按总字节预算裁剪，同时保留 30 条上限 |
| `LogWidget` 日志 | 每条消息重建全文，O(n²) | 增量追加 | 缓冲上限 5000 条 |

- `processors/_jit.py` — 抽出共享 `maybe_jit`，`fractal.py` 与 `filters.py` 共用（numba 缺失时自动降级）。
- 修正 `filters.py` 中 3 处 `np.indices()` 未指定 dtype 导致 int64 → float64 的问题
  （`vintage` / `haze` / `wave`）。
- 滤镜参数原先被重复校验最多 3 次（`make_filter_chain_worker` → `validate_all` → `FilterStep.apply`
  → `FilterDef.apply`），已消除其中一层。

### Changed — 行为变更（升级注意）

- `MainWindow._apply_adjust_full_res()` 现在是**异步**的（提交到任务队列）。
  `_smoke_test.py` 已相应加入 `wait_apply()` 等待。需要同步结果的调用方请改用任务信号。
- 提交新结果的正确写法是 `self._commit_image(result, "原因")`；
  不要再用 `set_display()` 紧跟 `_push_history()` 的顺序（那会让撤销失效）。
- 滤镜参数预览原先恒定 384px（`else 768` 是死分支，因为 `_is_dragging_sliders` 恒为真）；
  现在拖动时用 384、停止后自动补一次 768。
- `dither_bayer()` 输出会变化 —— 之前是崩溃或错误的单列图案，现在才真正应用 4×4 Bayer 矩阵。
- `vignette()` / `wave()` 中间量由 float64 改 float32，输出最多 **±1 LSB**；
  调整链中 `saturation(0)` / `vibrance(0)` 现在被跳过，省掉一次有损 HSV 往返（≤1 LSB）。
- `floyd_steinberg()` 新增可选 `cancel_token` 参数（按行分 20 段检查）。
- `TaskQueueWidget` 线程池由 8 降为 4。

### Added — Tests

- `tests/test_core.py`（19 项）— 覆盖此前**零覆盖**的 `processors/core.py`：
  `contrast` 默认值恒等 / 不posterize / 与参考曲线一致、`hue_shift` 全色环正确性、
  LUT 与浮点路径逐像素一致、`vignette`/`border`、`ensure_writable_dir` 只读回退。
  已做变异验证：换回原 buggy 的 `contrast`/`hue_shift` 后，9 项中 7 项失败。
- `tests/test_filter_robustness.py`（8 项）— **153 个滤镜 × 16 种尺寸 = 2448 次运行，0 失败**
  （修复前 16 处崩溃）；另含针对缺冒号 / 广播 / 空切片缺陷的定点断言。
- `tests/test_task_and_history.py`（10 项）— 失败任务回收、`shutdown()`、
  撤销语义、保存不再崩溃、历史字节预算、日志上限。
- `tests/test_shader_studio.py` — 新增 `LineEditorGutterTests`（gutter 必须在
  `updateRequest` 之前存在）。

### Verification

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests`：
  **262 tests / 261 PASS**（1 GMIC `test_cli_run` timeout，pre-existing 环境问题）。
  本轮开始前为 223 tests / 9 errors（9 个全部来自只读 `~/.toolbox`、`~/.cache/toolbox` 沙箱限制，
  其中 5 个预设测试已由可写性回退修复）。
- `QT_QPA_PLATFORM=offscreen .venv/bin/python _smoke_test.py`：**ALL SMOKE TEST PASSED**
  （init / 快速拖动 / 应用 / 撤销 / 二次应用 / 重置）。
- 全滤镜扫描：153 filters × 16 sizes = 2448 runs，**0 失败**（灰度输入另测 153 项，0 失败）。
- 真实 UI 提交路径逐一驱动验证（反色/灰度/直方图均衡/CLAHE/暗角/旋转×3/翻转×2/缩放/裁剪×3/
  水印×2/边框/自动裁剪）：`changed=True`、`history=1`、`_applied_image` 同步、**undo 全部恢复原图**。

### Known Issues（本轮未解决）

- `test_gmic_backend.GmicTests.test_cli_run` 在本机沙箱中超时：`gmic -input 16,16,1,1 -noise 5`
  在无 `-output` 时行为不稳定（`stdin=DEVNULL` 已把无限挂起转为有界返回，但该 sandbox 下
  仍可能超过测试的 5s 超时）。属于 pre-existing 环境问题。
- 真实 Wayland/X11 GUI、Shader OpenGL runtime 仍无法在无显示环境验证（`QOpenGLWidget is not
  supported on this platform`）。
- `saturation` / `vibrance` / `highlights_shadows` 仍需完整 HSV/亮度变换（非线性），未做 LUT；
  24MP 下单次约 310~520 ms，是调整链剩余的主要开销。
- `MainWindow` 仍约 4400 行，职责拆分未完成。

---

## 2026-09-29

### Added — A3/A4 FilterDef / FilterChain / TaskQueue / Preview / FilterPreset

- `processors/filter_defs.py` — 声明式 FilterDef / FilterParam / FilterCategory 系统
- `processors/filter_registry.py` — FilterDefRegistry + curated 自动注册管线
- `processors/filter_chain.py` — FilterChain / FilterStep / FilterChainError，可组合、可禁用/启用、可序列化
- `processors/filter_chain_task.py` — FilterChainWorker（QThread 后台渲染）+ PreviewCache（命中/跳过）
- `processors/filter_presets.py` — FilterPresetManager（JSON 持久化，跨会话恢复）
- `processors/batch_filter_chain.py` — BatchFilterChain（多文件批处理）
- `processors/cancellation.py` — CancelToken（可链式传递到后台任务）
- `app/widgets/filter_parameter_widget.py` — FilterDef 参数 → Qt widget 自动生成（滑块/下拉/颜色选择器）
- `app/main_window.py` FilterPanel / BatchPanel / Preview 重构为 FilterDef 驱动
- 新增 FilterCategory：BLUR / SHARPEN / ADJUST / COLOR / EFFECT / NOISE / DISTORT / ARTISTIC / UTILITY / FILTER_GEN / BLEND / FILTER_GEN_2 / MULTIFRAME / FILTER_VARIANT / FILTER_SAMPLE / EXPERIMENTAL / **FRACTAL**

### Added — A5 Fractal 分形框架

- `processors/fractal.py` — 完整分形渲染框架（879 行）
  - FractalColoring 枚举：SMOOTH（Nielsen 平滑）/ BANDED / GRAYSCALE
  - FractalParams dataclass：cx, cy, scale, power, iterations, bailout, julia_c, phoenix_c, nova_relaxation
  - FractalResult：image (PIL.Image), iterations_array (np.int32), escaped_mask
  - **15 种 2D escape-time 公式**（全部真实数学实现，非 alias）：
    Mandelbrot / Multibrot / Julia / Burning Ship / Tricorn / Multicorn / Celtic / Buffalo / Perpendicular Burning Ship / Phoenix / Newton / Nova / Magnet I / Magnet II / Buddhabrot（密度渲染）
  - **1 种 3D 公式**：Mandelbulb（distance estimator + ray marching + spherical z↦zⁿ）
  - smooth coloring 用 Nielsen 平滑着色，escape_radius 真参与逃逸判断
  - `render_fractal(width, height, formula_key, params, cancel_token, progress_cb)` — 统一入口
  - CancelToken 按 row 分块检查，取消立即终止；progress 0→100 单调递增
  - numba 可选加速（`_maybe_jit` 装饰器），import 失败自动 fallback 纯 Python
  - 每个 2D 公式自动注册为 `fractal_*` FilterDef，capabilities 动态推导参数

### Tests

- `tests/test_fractal.py` — 29 项：15 种公式注册、参数真生效（Julia const diff=28.7, Multibrot power diff=19.6, center/zoom diff=49.9）、CancelToken 中断、progress 单调、3D Mandelbulb smoke、FilterDef/FilterChain/Preset 集成
- `tests/test_filter_defs.py` — FilterDef 参数声明式 API、capabilities 推导
- `tests/test_filter_chain.py` — FilterChain 组合、禁用/启用、FilterStepError
- `tests/test_filter_chain_task.py` — 后台 FilterChainWorker、CancelToken、PreviewCache
- `tests/test_imports.py` — 模块导入稳定性

### Verification

- `uv run python -m unittest discover -s tests -v`：**222/223 PASS**（1 GMIC timeout，pre-existing）
- `uv run python -m unittest tests.test_fractal -v`：**29/29 PASS**
- PySide6 offscreen MainWindow smoke：创建 OK → 15 fractal filters 可见于 filter_list → FilterDef apply OK → CancelToken 传播 OK → closeEvent 无 crash
- numba 可选加速：检测到环境可用时自动启用；无 numba 时 fallback 纯 Python

### Changed

- `app/main_window.py` — +1112/-384 行，FilterPanel/BatchPanel/Preview 全面重构为 FilterDef + FilterChain + TaskQueue 架构
- `processors/__init__.py` — 新增 filter_defs / filter_registry / filter_chain / filter_presets / batch_filter_chain / fractal 导出

### Known Issues

- Creator Fractal panel 仅 Mandelbrot/Julia 下拉，全部分形公式通过 Filter panel 访问
- 2D escape-time 扩展公式 ~27 种未实现（Barnsley 系 / Sine / Sinh / Feather / Tetration / Spider 等，escape-time 小变体，模式完全一致，后续可批量补充）
- 2D Density/Attractor 15 种未实现（Hopalong / Martin / Clifford 等，独立随机迭代吸引子）
- 3D Geometric IFS / Quaternion / Attractor 12 种未实现
- OrbitTrap / Angle coloring 未实现
- Mandelbulb 未注册为 FilterDef（3D 从空场景渲染，非"输入图像处理"语义）
- Magnet I/II 公式的圆吸收条件可能需要对照标准 Julia 变体验证

---

## 2026-09-22

### Added

- 建立 `feature/toolbox-parity-ui-overhaul` 开发分支与 Git 基线。
- 增加 ImageToolbox 67 个 feature 的桌面 parity 审计矩阵。
- 增加专业参数面板：分形、纹理、网格渐变、Shader、SVG、Photomosaic、多帧融
  合、动画转换。
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
