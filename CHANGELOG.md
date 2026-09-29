# Changelog

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
