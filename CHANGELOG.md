# Changelog

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
