# 架构分析（Phase 0 现状基线）

> 本文记录 Toolbox 1.x（Python + PySide6 Widgets）的现状架构，是 Toolbox 2.0
> （C++ + Qt Quick + QML）迁移决策的事实依据。所有结论均带 `file:line` 证据，
> 对应代码版本：`main@fa98847` 之后、`phase0-font-system` 分支。
>
> 功能级迁移清单见 [ui-migration-matrix.md](ui-migration-matrix.md)。

## 1. 概览

- 入口 `main.py` → `app/main_window.py:4460` `main()`；UI 全部在 `app/`（Widgets + QSS）。
- 算法在 `processors/`（约 40 个模块），外部程序抽象在 `backends/`（仅 GMIC 实现完整）。
- `app/main_window.py` 单文件 **4477 行**，单个 `MainWindow(QMainWindow)` 类
  （`app/main_window.py:118-4457`），包含 45 个侧栏工具面板的构建与全部业务 handler。
- 侧栏工具 45 项：`TOOL_ITEMS`（`app/main_window.py:69-115`）；工具→面板构建函数
  映射在 `_select_tool`（`app/main_window.py:630-676`）。另有 Texture Studio / Shader
  Studio 两个独立面板不在侧栏，从"ImageToolbox 功能补齐"面板双击进入
  （`app/main_window.py:3354-3356, 3454-3457`）。

## 2. 状态所有权（MainWindow 上帝对象）

`MainWindow` 直接持有（`_init_state` `app/main_window.py:297-316` 及 `__init__` 121-126）：

| 状态 | 位置 | 说明 |
|---|---|---|
| `_current_file` / `_recent_files` | 121-122 | 最近文件列表仅内存，不持久化（仅开关持久化） |
| `_settings` / `_font_info` / `_theme_mode` | 123-126 | QSettings 封装 + 字体解析结果 + 主题 |
| `_applied_image` | 299 | 已应用的"基准图"（ndarray） |
| `_history` | 298 | 撤销栈（像素副本 + FilterChain 快照 + 操作名） |
| 预览任务态 | 300-315 | 在途任务引用、代数计数器 `_preview_gen/_apply_gen`、180ms 防抖 QTimer、预览源缓存 |
| 任务队列 / 日志 Dock | 262-268 | `TaskQueueWidget` / `LogWidget`（`app/workbench.py`） |
| 面板控件 | 各 `_build_*_panel` | 控件直接挂 `self`，随工具切换 `setParent(None)+deleteLater()` 销毁（682-695），催生 `_widget_alive` 守卫（43-61） |

面板反向依赖极少：唯一组件→MainWindow 方法直调是 `preview_widget.py:198-205`
`dropEvent` → `mw.load_file(p)`；其余全部为信号上行（`app/main_window.py:184-186`）。

## 3. processors 调用模式（无 Service 层）

四种模式并存，MainWindow 是唯一编排者：

1. **模块顶层 import**（13 个模块，`app/main_window.py:19-40`）。
2. **handler 内 late import**（约 45 处，如 AI 抠图 `app/main_window.py:2359`、
   直方图 2695、比较 2766）。
3. **FilterDefRegistry 单例**：滤镜的唯一定义层
   （`processors/filter_defs.py:216-223`；注册链 `processors/__init__.py:25-31` →
   `advanced_filters.register_all` → `filter_registry.register_curated_filters` →
   `register_legacy_filters` → `build_legacy_compat_layer`；分形滤镜
   `processors/fractal.py:792`）。MainWindow 取定义并 `defn.apply(...)`
   （`app/main_window.py:1252, 1366`）。
4. **`parity.run_parity_tool` 字符串分发表**：约 55 个文件型工具的统一入口
   （`processors/parity.py:740`），UI 侧由约 230 行 if/elif 的
   `_run_parity_operation` 映射（`app/main_window.py:3451-3684`）。

`backends/`（`Backend` ABC `backends/base.py:8-16`）只被设置对话框
（`app/main_window.py:499-512`）和 Texture Studio 的 G'MIC 纹理使用。

## 4. 线程 / 任务 / 取消

- **混合模型**：7 个调用点走 `TaskQueueWidget` 私有 QThreadPool（默认 4 线程，
  `app/workbench.py:81-85`）：调整预览 864、调整应用 915、滤镜链应用 1122、
  单滤镜预览 1310、批量链 3061、批量转换 3076、分形渲染 4452。
- **仍在 GUI 线程同步执行的长任务**（用 `processEvents()` 缓解冻结）：全部 AI 操作
  （`app/main_window.py:2358-2641`）、全部 parity 操作（3451-3684）、高级滤镜 4328、
  EXIF 1553、OCR 1636、G'MIC 1950、保存 2300。→ 迁移重点。
- **取消体系已成型可复用**：`CancelToken`（`processors/cancellation.py:10-26`，
  `threading.Event` 封装）+ `Task.cancel()`（`app/workbench.py:59`）+ 协作检查点
  （滤镜链每步 `processors/filter_chain_task.py:95`、批量链
  `processors/batch_filter_chain.py:71-83`、G'MIC 子进程轮询 kill
  `processors/gmic.py:33-46`）+ 代数计数丢弃过期结果（`app/main_window.py:304-306`）
  + 关闭清理（`closeEvent` 281-295 → `task_queue.shutdown()` `app/workbench.py:93-104`）。
- **预览管线**（迁移时需保留的行为）：180ms 防抖（312-315）→ 两级分辨率
  （拖动 384px / 停稳 768px，1292-1294）→ LRU 预览缓存 8 条
  （`processors/filter_chain_task.py:14-64`）→ 代数比对丢弃过期回调。
- Texture Studio 自带独立 QThreadPool + RenderJob（`app/panels/texture_studio.py:14-22, 64`）；
  Shader Studio 无工作线程，33ms QTimer 驱动 GL 重绘（`app/panels/shader_studio.py:49-51`）。

## 5. 撤销 / 重做

- 只有 undo，没有 redo。栈元素 `(ndarray 副本, FilterChain 快照, 操作名)`，
  **像素级回滚**，不重放 processor 调用。
- 容量：30 条 + 512MB 字节预算（`app/main_window.py:346-357`）。
- 写入时机：显示新结果**之前**快照（`_push_history` 359-374）。
- 统一提交入口 `commit_processed_result`（450-451）；undo 恢复图像 + 回退
  `_applied_image` + 整体替换 FilterChain（390-404）；`reset_all` 清历史、恢复原图、
  代数计数器作废在途预览（406-427）。

## 6. 设置与持久化

| 数据 | 位置 | 载体 |
|---|---|---|
| 主题/窗口/字体/输出目录/最近文件开关 | QSettings("Emo","Toolbox")（`app/settings_store.py:9-13`） | Windows 注册表 / Linux `~/.config/Emo/Toolbox.conf` |
| 字体设置 | `font/family`、`font/size`、`font/mono`（读 `app/fonts.py:49-61`，写 `app/main_window.py:524`） | 同上 |
| 滤镜链预设 | `~/.toolbox/filter_presets/*.filterchain.json`（`processors/filter_presets.py:23-34`，原子写 106-121） | JSON 文件 |
| AI 后端/模型注册表 | `~/.cache/image-toolbox/models/*.json`（`processors/ai_models.py:13-35, 115-127`） | JSON 文件 |
| 纹理缩略图 / G'MIC 缓存 | `~/.cache/toolbox/texture_thumbs`、`~/.cache/toolbox/gmic/filters.json`（`app/panels/texture_studio.py:12`、`backends/gmic_backend.py:14-16`） | 目录/JSON |
| Shader / Texture 用户库 | `~/.local/share/toolbox/{shaders,textures}`（`app/panels/shader_studio.py:99`、`texture_studio.py:64`） | 目录 |

## 7. 字体系统（Phase 0 已修复）

修复前的问题与处置（对应升级计划 §5.1）：

| 问题 | 原位置 | 处置 |
|---|---|---|
| QSS 全局 `* { font-family: "MiSans"...; font-size: 13px }` 强制覆盖 | `app/theme.py:54,145` | 已删除；字体由 `app.font()` 统一控制 |
| 启动递归扫描 4 个系统字体目录找 MiSans | `app/fonts.py:17-23` | 已删除（`ensure_packaged_misans` 移除） |
| MiSans 硬编码为首选与默认 | `app/fonts.py:6,27` | 默认改为系统默认（空 family → fontconfig/平台解析）；候选链保留 Noto CJK/Sarasa/YaHei/LXGW |
| 等宽字体只读取不应用 | `app/fonts.py:29-30` | 新增 `mono_font()`（候选链 → `QFont.Monospace` hint 系统回退），Shader Studio 编辑器已接入（`app/panels/shader_studio.py:104`） |
| 测试强制断言 MiSans | `tests/test_fonts.py:17-19` | 已重写为真实解析断言（QFontInfo/QRawFont，覆盖中/英/数字/符号/Emoji 诊断） |

新增诊断接口：`app/fonts.py` 的 `glyph_coverage()` / `fallback_candidates()` /
`diagnose()`，供设置页与测试查询"实际解析结果"（升级计划 §9 可诊断性要求）。

未纳入本次范围（记录待迁移）：水印字体候选列表含 MiSans Linux 路径
（`processors/filters.py:11-17`，已有优雅回退，归 Phase 5 绘图标注迁移）；
ASCII 工具硬编码 DejaVu Linux 路径（`processors/ascii.py:38,61`，归 Phase 6）。

## 8. 已知隐患（迁移时必须处理）

1. **`parity.run_parity_tool` 双重定义**：`processors/parity.py:609` 与 `:740` 各定义
   一次，后者覆盖前者且多 7 个工具。前者是死代码，但阅读/审计易错。
2. **G'MIC 双轨**：`processors/gmic.py:25`（subprocess 直调）与
   `backends/gmic_backend.py:44`（Backend 抽象）并存，行为与缓存不同。
3. **GUI 线程长任务**（见 §4）：AI/parity/保存等主线程同步执行。
4. **`_recent_files` 不持久化**（`app/main_window.py:122`），设置里只有开关。
5. **面板控件挂 self + deleteLater**：跨面板引用依赖 `_widget_alive` 运行时守卫，
   新 UI（QML 页面生命周期）天然消除该问题，但迁移时需注意行为等价。
6. **ImageToolbox 功能补齐面板是元功能**（67 项清单 + 60 按钮的分发器，
   `app/main_window.py:3327-3684`）：其中部分功能为注册名而非完整实现
   （`docs/functionality-audit.md`），迁移矩阵中逐项标注真实完成度，不得照搬数量。

## 9. 对 2.0 架构的映射建议（结论）

- **Service 层边界已可画**：§3 的 4 种调用模式收敛为 `image_service`（文档/历史/
  预览管线）、`filter_service`（FilterDefRegistry/链/预设）、`task_service`
  （TaskQueue/CancelToken 语义平移到 IPC 任务）、文件工具组（parity 分发表直接
  映射为 Worker action 表）。
- **取消与进度语义现成**：`CancelToken` + 代数计数 + progress_cb 的组合与计划的
  JSON Lines 协议（request_id/task_id/progress/cancel）一一对应，Worker 化时按此翻译。
- **预览管线参数**（防抖 180ms、384/768 两级、LRU 8 条）作为新画布的性能基线指标。
- **Undo 语义**：像素快照 + FilterChain 快照的混合模型在 Worker 化后需改为
  document_id 状态 + 快照引用，避免大图跨进程复制。
