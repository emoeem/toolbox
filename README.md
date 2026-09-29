# Toolbox

Linux 原生桌面专业图像工具箱，基于 **Python 3.11 + PySide6 (Qt 6)** 构建，目标是将 [ImageToolbox](https://github.com/8bitPetter/ImageToolbox) 的核心图像处理能力转化为适合 Linux 桌面的高效工作流。

## 特性

- **FilterDef / FilterChain**：可组合的图像处理管线，每个滤镜都是可序列化的 FilterDef，支持预设保存/恢复、批量应用、后台渲染
- **Fractal 分形框架**：15 种 2D escape-time 分形（Mandelbrot / Julia / Burning Ship / Tricorn / Multibrot / Phoenix / Newton / Buddhabrot 等）+ Mandelbulb 3D，平滑着色 / 带状着色 / 灰度着色，CancelToken 可中断，numba 可选 JIT 加速
- **TaskQueue + Preview**：统一后台任务队列，实时预览（低分辨率缩略图 + debounce + 缓存命中），进度回调，可取消
- **参数面板自动生成**：FilterDef 声明式参数 → Qt widget 自动创建（滑块 / 下拉 / 颜色选择器），无需为每个滤镜手写 UI
- **Creator 工作流**：Fractal / Shader / SVG / Photomosaic / Texture Studio 等生成器
- **主题与布局持久化**：Dark / Light / System，窗口布局保存恢复
- **多格式支持**：JPEG / PNG / WEBP / HEIF / AVIF / JXL / TIFF / PDF

## 目录结构

```
toolbox/
├── app/                      # Qt UI 层
│   ├── main_window.py        # 主窗口 + 所有面板（Filter / Fractal / Batch / Compare ...）
│   ├── preview_widget.py     # 图像预览
│   ├── workbench.py          # 工作区管理
│   ├── theme.py              # Dark/Light/System 主题
│   ├── settings_store.py     # QSettings 持久化
│   ├── fonts.py              # 字体加载
│   └── widgets/
│       └── filter_parameter_widget.py   # FilterDef → Qt widget 自动生成
├── processors/               # 图像处理核心（无 UI 依赖）
│   ├── core.py               # 基础 numpy/Pillow 操作
│   ├── filter_defs.py        # FilterDef / FilterParam / FilterCategory
│   ├── filter_registry.py    # FilterDefRegistry + curated 自动注册
│   ├── filter_chain.py       # FilterChain / FilterStep / FilterChainError
│   ├── filter_presets.py     # FilterPresetManager（JSON 持久化）
│   ├── filter_chain_task.py  # FilterChainWorker + PreviewCache（后台渲染）
│   ├── batch_filter_chain.py # BatchFilterChain（批处理）
│   ├── cancellation.py       # CancelToken
│   ├── _jit.py               # numba maybe_jit 共享助手（缺失时自动降级为纯 Python）
│   ├── utils.py              # save_image / load_image / ensure_writable_dir
│   ├── fractal.py            # 分形渲染框架（15 2D + Mandelbulb 3D）
│   ├── filters.py            # 传统滤镜集合
│   ├── advanced_filters.py   # 高级滤镜
│   ├── gmic.py               # G'MIC 封装
│   ├── gradients.py          # 渐变/调色板工具
│   ├── utils.py              # save_image / load_image / to_numpy 等
│   └── ...
├── backends/                 # 外部后端（GMIC CLI 等）
├── tests/                    # 单元测试
├── docs/
│   ├── parity-audit.md       # ImageToolbox parity 审计矩阵
│   └── code-review-fixes.md  # 代码审查报告（Bug 修复 + 性能优化，含实测证据）
├── main.py                   # 入口
├── pyproject.toml            # PEP 621 项目配置 + 依赖
└── uv.lock                   # 锁定依赖版本
```

## 环境要求

| 依赖 | 版本 |
|---|---|
| Python | ≥ 3.11 |
| PySide6 | ≥ 6.6 |
| numpy | ≥ 1.24 |
| OpenCV (headless) | ≥ 4.8 |
| Pillow | ≥ 10.0 |
| scikit-image | ≥ 0.22 |
| imageio | ≥ 2.33 |

可选：pillow-heif / pillow-avif / pillow-jxl-plugin（多格式），pytesseract（OCR），pypdf + pdf2image（PDF），colorthief（调色板提取），numba（分形 JIT 加速，检测失败自动 fallback 纯 Python）

## 安装与运行

使用 `uv`（推荐）：

```bash
# 克隆 + 安装依赖
cd toolbox
uv sync

# 启动桌面应用
uv run python main.py

# Wayland 环境
QT_QPA_PLATFORM=wayland uv run python main.py

# 无显示环境（测试用）
QT_QPA_PLATFORM=offscreen uv run python -c "from app.main_window import MainWindow"
```

也可以直接用 venv + pip：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python main.py
```

## 测试

```bash
uv run python -m unittest discover -s tests -v
```

当前测试覆盖：263 tests / OK（1 skipped：本机装有 `glslangValidator` 时该「工具缺失」用例跳过）

> 分支模型、CI 流程、必需状态检查与本地复现命令见 [CONTRIBUTING.md](CONTRIBUTING.md)。
> `main` 受保护：只接受 PR 合入且必须通过 CI 检查 `test`。

> 缓存/预设目录会做可写性探测（`processors.utils.ensure_writable_dir`），
> 只读 HOME 或容器环境下自动回退到系统临时目录，而不是抛出裸 `OSError`。

### 重点测试模块

| 模块 | 说明 |
|---|---|
| `tests/test_fractal.py` | 29 项：15 种分形公式注册、参数真生效、CancelToken 中断、progress 回调、3D Mandelbulb smoke、FilterDef/FilterChain/Preset 集成 |
| `tests/test_filter_defs.py` | FilterDef 参数声明式 API、capabilities 推导 |
| `tests/test_filter_chain.py` | FilterChain 组合、禁用/启用、FilterStepError |
| `tests/test_filter_chain_task.py` | 后台 FilterChainWorker、CancelToken、PreviewCache |

## FilterDef 系统

Toolbox 的滤镜系统基于声明式 `FilterDef`：

```python
from processors.filter_defs import FilterDef, FilterParam, FilterCategory
from processors.filter_registry import FilterDefRegistry

# 注册一个滤镜
def my_processor(img, radius=3):
    # img 是 numpy ndarray（H×W×3, uint8）
    return processed_img

fd = FilterDef(
    key="my_blur",
    name="高斯模糊",
    category=FilterCategory.BLUR,
    params=[
        FilterParam(key="radius", label="半径", type="float",
                    default=3.0, min=0.5, max=50.0, step=0.5),
    ],
    processor=my_processor,
    preview_supported=True,
    batch_supported=True,
)
FilterDefRegistry.instance().register(fd)
```

注册后：
- Filter panel 自动显示，参数滑块自动生成
- 可加入 FilterChain（组合多个滤镜一次性执行）
- 可保存为 FilterPreset（JSON 持久化，跨会话恢复）
- 可用于批量处理（BatchFilterChain）
- CancelToken / 后台任务 / 实时 Preview 全部复用

### FilterCategory

当前分类：`BLUR | SHARPEN | ADJUST | COLOR | EFFECT | NOISE | DISTORT | ARTISTIC | UTILITY | FILTER_GEN | BLEND | FILTER_GEN_2 | MULTIFRAME | FILTER_VARIANT | FILTER_SAMPLE | EXPERIMENTAL | FRACTAL`

## Fractal 框架

```python
from processors.fractal import (
    render_fractal, FractalParams, FractalColoring,
    _2D_FORMULAS, _3D_FORMULAS
)

# 渲染 640×480 Julia 分形
result = render_fractal(
    width=640, height=480,
    formula_key="julia",
    params=FractalParams(
        cx=0.0, cy=0.0,
        scale=3.0,
        power=2.0,
        iterations=256,
        bailout=4.0,
        coloring=FractalColoring.SMOOTH,
        julia_c=(-0.8, 0.156),
    ),
    progress_cb=lambda p: print(f"{p}%"),
)
result.image.save("julia.png")   # PIL.Image
result.iterations_array          # np.int32 (H×W)
result.escaped_mask              # bool, 是否有逃逸像素
```

### 2D 公式（15 种）

| key | ImageToolbox 对标 | 说明 |
|---|---|---|
| `mandelbrot` | Mandelbrot | zₙ₊₁ = zₙᵖ + c |
| `multibrot` | Multibrot | 默认 power=3.0 |
| `julia` | Julia | 常数 C 真生效 |
| `burning_ship` | BurningShip | \|Re(z)\| + i\|Im(z)\| |
| `tricorn` | Tricorn | zᵖ 共轭 |
| `multicorn` | Multicorn | zᵖ 共轭，默认 power=3.0 |
| `celtic` | Celtic | \|Re(z)\| + i·Im(z) |
| `buffalo` | Buffalo | \|Re(z)\| - i·\|Im(z)\| |
| `perpendicular_burning_ship` | PerpendicularBurningShip | \|Re(z)\| + i·(-\|Im(z)\|) |
| `phoenix` | Phoenix | zₙ₊₁ = zₙᵖ + c + pc·zₙ₋₁ |
| `newton` | Newton | Newton 迭代吸引盆 |
| `nova` | Nova | + relaxation 参数 |
| `magnet_i` | Magnet I | Julia 变体 |
| `magnet_ii` | Magnet II | Julia 变体 |
| `buddhabrot` | Buddhabrot | 密度渲染轨道热图 |

### 3D 公式（1 种）

| key | 说明 |
|---|---|
| `mandelbulb` | Distance estimator + Ray marching + spherical z↦zⁿ |

### 着色模式

- `SMOOTH` — Nielsen 平滑着色，基于 smooth iteration value
- `BANDED` — 整数迭代 count % 256，产生色带
- `GRAYSCALE` — 灰度映射

### 性能

- 基础路径：纯 Python + `math.sqrt/log`，64×64 Mandelbrot ≈ 10ms
- numba 可选加速：`processors/_jit.py` 的 `maybe_jit(nopython=True)` 装饰器，检测失败自动 fallback（`fractal.py` / `filters.py` 共用）
- 分块渲染：按 row 渲染 + CancelToken 每 row 检查，取消立即终止
- Preview 自动降分辨率（参数预览的降采样源按图像代次缓存；拖动时 384px，停止后自动补 768px）
- 调整链：跳过等于默认值的步骤，点运算（亮度/对比度/曝光/伽马）走 256 项 LUT

完整实测数据（含逐像素等价性校验）见 [docs/code-review-fixes.md](docs/code-review-fixes.md)。

### FilterDef 自动注册

每个 2D 分形公式自动注册一个 `fractal_*` FilterDef，capabilities 动态推导参数（Julia 有 `julia_c_x/y`，Nova 有 `nova_relaxation`，Mandelbrot 没有）。

## 开发指南

### 新增滤镜

1. 在 `processors/` 下实现函数 `def my_filter(img: np.ndarray, **params) -> np.ndarray`
2. 在 `processors/filter_registry.py` 的 `register_curated_filters()` 中添加 FilterDef 注册
3. 写单元测试（参数生效、非法参数抛异常、稳定可重复）

### 新增 2D 分形公式

```python
from processors.fractal import _register_2d_formula, _maybe_jit, FractalParams
import math

@_maybe_jit
def _my_fractal_iter(px, py, iterations, bailout):
    # 独立迭代函数，返回 (escape_iteration, smooth_value)
    zx, zy = float(px), float(py)
    cx, cy = float(px), float(py)
    r2 = 0.0
    for it in range(iterations):
        zx2, zy2 = zx*zx, zy*zy
        r2 = zx2 + zy2
        if r2 > bailout * bailout:
            nu = math.log(math.log(r2) / 2.0) / math.log(2.0)
            return it + 1, it + 1 - nu
        # 你的公式 ...
    return iterations, 0.0

_register_2d_formula(
    key="my_fractal",
    name="我的分形",
    formula=_my_fractal_iter,
    default_power=2.0,
    default_bailout=4.0,
    can_power=True,
    can_bailout=True,
)
```

自动获得：FilterDef 注册、FilterChain 可加入、Preset 可保存、CancelToken、Progress、Preview。

### 新增 3D 分形

在 `processors/fractal.py` 中实现 distance estimator + ray marching。3D 分形通常**不注册为 FilterDef**（从空场景生成 3D 图像，不是"输入图像处理"模型）。

### UI 测试（offscreen）

```bash
QT_QPA_PLATFORM=offscreen uv run python -c "
import sys; from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow
app = QApplication.instance() or QApplication(sys.argv)
w = MainWindow(); w.show(); app.processEvents()
print('MainWindow OK')
w.close(); app.processEvents()
"
```

## ImageToolbox Parity

详见 [docs/parity-audit.md](docs/parity-audit.md)。

| 阶段 | 内容 | 状态 |
|---|---|---|
| A1 | UI 框架 + 主题 + 布局持久化 | ✅ Done |
| A2 | 基础 Processors parity | ✅ Done |
| A3 | FilterDef / FilterChain / TaskQueue / Preview / CancelToken | ✅ Done |
| A4 | FilterPreset + Batch 处理 | ✅ Done |
| A5 | Fractal 分形框架（15 2D + Mandelbulb 3D） | ✅ Done |

### Fractal Parity 对照

| 分类 | ImageToolbox 数量 | Toolbox 实现 |
|---|---|---|
| 2D Escape-time 核心 | ~16 | **15** ✅ |
| 2D Escape-time 扩展（Barnsley/Sine/Sinh/Feather/Tetration 等） | ~27 | 0（escape-time 小变体，后续补充） |
| 2D Density/Attractor | ~15 | 0（Hopalong/Martin/Clifford 等） |
| 3D Distance Estimator | ~3 | **1**（Mandelbulb） |
| 3D Geometric IFS/Quaternion/Attractor | ~12 | 0 |
| Coloring | 4 | **3/4**（缺 OrbitTrap/Angle） |

## 许可

Apache-2.0 — 与 ImageToolbox 保持一致。
