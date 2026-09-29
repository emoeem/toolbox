# 代码审查报告 — Bug 修复与性能优化

审查日期：2026-09-29（第二轮）
分支：`feature/toolbox-parity-ui-overhaul`
审查范围：全仓库约 12.5k 行（`app/` `processors/` `backends/` `tests/`）
原则：只依据当前工作树、可重复命令与实测数据；每条结论附可复现证据。**未实测的推测不写入本报告。**

对应提交见 `CHANGELOG.md` 的「2026-09-29（第二轮）」条目。本文保留完整证据与复现方式。

---

## 0. 结论先行

| 等级 | 数量 | 说明 |
|---|---:|---|
| 致命（图像被破坏 / 崩溃） | 10 | 含 1 个未提交改动引入的 `contrast()` 回归、3 个滤镜几何 Bug、1 个保存必崩、1 个撤销完全失效 |
| 严重（内存泄漏 / 静默错误结果） | 2 | 失败任务永久泄漏全分辨率图；`FilterDef.apply` 吞异常并用默认参数重跑 |
| 性能瓶颈（已量化并修复） | 8 | 含 GUI 线程 2.76 s 冻结、`floyd_steinberg` 24MP 约 220 s |
| 健壮性 | 7 | 只读目录、非原子写、子进程无超时/gmic stdin 挂起、取消未打通等 |
| 测试基线 | — | 223 tests / 9 errors → **262 tests / 261 PASS**（余 1 为 pre-existing GMIC 环境问题） |

本轮同时修复了**测试套件自身的全局单例污染**（一个故意抛异常的测试夹具泄漏到
`FilterDefRegistry` 全局单例，导致其他模块假失败）。

---

## 1. 审查方法

- 逐文件通读 `processors/*.py`、`app/*.py`、`app/panels/*.py`、`backends/*.py`、`tests/`。
- 对每个怀疑点写最小复现实验（numpy 形状/dtype 推理 + `time.perf_counter` 计时），
  与"参考实现"逐像素对比确认是否真的等价。
- 端到端驱动真实 `MainWindow`（`QT_QPA_PLATFORM=offscreen`），逐个点击真实 UI 路径验证
  提交/撤销/保存语义，而不是只读代码。
- 全量滤镜扫描：对注册表内全部滤镜遍历多个尺寸/灰度输入，捕获异常与非法输出。
- 对新增回归测试做**变异验证**：把被测代码换回原来的 buggy 实现，确认测试确实失败。

---

## 2. 致命与严重缺陷

### 2.1 `contrast()` 公式漏除 255（未提交改动引入）

`processors/core.py:17`

```python
# 旧（正确）: f = 259*(v*255+255) / (255*(259 - v*255))   → v=0 时 f=1.0
# 新（错误）: denom = 255.0 - value*255.0                 → v=0 时 f=259
```

对比度系数被放大约 255 倍，图像被压成约 3 个色调。

复现与证据：

```
$ .venv/bin/python -c "... grad = 0..255 ramp; contrast(grad, 0.0) ..."
value= 0.00: in 0..255 -> out   0,  0,128,255,255  unique=3
contrast(img, 0.0) == img ? False
max abs deviation at value=0: 127
```

端到端（真实 `MainWindow`，只拖动"对比度"滑块）：

```
distinct colors before = 89488
distinct colors after  = 20        ← 每通道只剩 4/8/5 个色阶
```

因为 `_apply_adjust_chain` 总是执行全部 9 个调整（包括默认值 0.0 的对比度），
**任何一次"应用调整"都会破坏图像**。

修复（与参考曲线逐像素一致，`max|diff| = 0`）：

```python
f = 259.0 * (value * 255.0 + 255.0) / (255.0 * (259.0 - value * 255.0))
```

顺带删除原新增的除零守卫 —— `value` 已被 `clip` 到 ±0.99，denom 恒在 `[2.55, 502.05]`，
该分支是不可达的死代码。

### 2.2 `hue_shift()` 色相环绕用 `% 180`

`processors/core.py:89`

输入被转成 **float32(0..1)** 后送 `cv2.cvtColor(..., RGB2HSV)`。OpenCV 在 float32 下
Hue 量程是 **0..360**，只有 uint8 才是 0..180。`% 180` 把色相环折成一半。

复现（`+60°` 偏移，0..360 量程）：

```
 input -> output | expected
    0  ->   60.0  |   60.0   ok
   90  ->  150.1  |  150.0   ok
  120  ->    0.0  |  180.0   << WRONG
  180  ->   60.5  |  240.0   << WRONG
  240  ->  120.0  |  300.0   << WRONG
6/12 hue bands wrong
```

`+180°`（UI 滑块范围正好是 [-180, 180]）对 H<180 的颜色是**完全无操作**：

```
orig      : [[255,0,0],[0,255,0],[0,0,255],[255,255,0]]
shift +180: [[255,0,0],[0,255,0],[255,255,0],[255,255,0]]   ← 红/绿未变
```

入口：`app/main_window.py` 的"色相"滑块。修复：`% 360`。

### 2.3 `FilterDef.apply()` 吞掉真实 `TypeError` 并用默认参数重跑

`processors/filter_defs.py:195`（原实现）

```python
try:
    return self.processor(image, **merged) if merged else self.processor(image)
except TypeError:                     # ← 捕获面过宽
    return self.processor(image)      # ← 丢掉所有参数重跑
```

`except TypeError` 无法区分"处理器不接受该关键字参数"与"处理器**内部**抛 TypeError"。

复现（滤镜体内出错）：

```
processor invocations: [{'strength': 7}, {'strength': 1}]
-> 内部错误被吞，第二次用默认参数 strength=1 重跑
```

后果：① 滤镜跑两遍；② 若第二次侥幸成功，用户**静默拿到用默认参数算出的错误结果**；
③ 若第二次也失败，抛出的错误与真实原因无关。

修复：用 `inspect.signature`（带 `lru_cache`）预先计算可接受的参数名并过滤；错误立即上抛。
另外对全量 153 个已注册滤镜做了静态审计 —— **声明参数与处理器签名 0 处不匹配**，
说明原 fallback 从来不是为了兜住"参数名写错"，纯粹是在掩盖内部异常。

### 2.4 撤销（Undo）对滤镜/变换路径完全失效

`app/main_window.py`：原先 `_push_history()` 在 `set_display()` **之后**调用，
因此快照的是**新图**，撤销等于空操作。

```python
result = defn.apply(...)
self.preview.set_display(result)     # 已显示新图
self._push_history("应用滤镜")        # 快照的是新图 → undo 无效
```

而 `_apply_adjust_full_res`（同步路径）恰好是"先 push 后 display"，所以只有那条路径的撤销是对的 ——
同一份状态被两种矛盾顺序使用。

修复：统一为 `_commit_image(result, reason)` = 先快照 → 再显示 → 标记已应用。
真实 UI 逐路径验证（11 条）：`changed=True`、`history=1`、`_applied_image` 同步、**undo 全部恢复原图**。

### 2.5 保存崩溃：`ndarray or ndarray`

`app/main_window.py`：`img_to_save = self._applied_image or self.preview.current_image()`

对多元素 ndarray 求布尔值直接抛异常。复现：

```
[save before apply] OK
[save after apply] raised: ValueError The truth value of an array with more than one element is ambiguous.
```

即：**应用过任何编辑后按保存必然崩溃**。修复为显式 `is not None` 判断。

### 2.6 `dither_bayer()` 缺一个冒号

`processors/filters.py:567`

```python
tiled = np.tile(matrix, (h // oh + 1, w // ow + 1))[:h, w]   # 应为 [:h, :w]
```

`[:h, w]` 是单列索引而非切片。后果：`h != w` 时崩溃；`h == w` 时侥幸不崩，
但用**一列 Bayer 阈值广播到所有行**，抖动图案是错的（此时不会报错，属于静默错误输出）。

```
(32,40) anaglyph=FAIL dither_bayer=FAIL old_tv=FAIL
(64,64) anaglyph=ok   dither_bayer=ok   old_tv=ok
(16,24) anaglyph=FAIL dither_bayer=FAIL old_tv=FAIL
```

修复后 `dither_bayer` 的 4×4 tile 在行、列两个方向都变化（定点断言已加入测试）。

### 2.7 `old_tv()` 扫描线无法广播 —— 所有非正方形图崩溃

`processors/filters.py:730`

```python
scanlines = np.ones((h, 1), dtype=np.float32)
result = img_ * scanlines                 # (h,w,3) * (h,1) → 仅当 h == w 成立
```

```
old_tv (32,40): ValueError: operands could not be broadcast together with shapes (32,40,3) (32,1)
```

修复：`scanlines[..., None]`（同文件 `crt_curvature()` 本来就是这么写的）。

### 2.8 `anaglyph()` 窄图 shift=0 导致空切片赋值

`processors/filters.py:416`：`shift = int(w * 0.02)`，`w < 50` 时 shift 为 0，
于是 `result[:, 0:, 0] = img_[:, :0, 0]` → 把 `(h, 0)` 赋给 `(h, w)`。

```
anaglyph w=8: shift=0    → ValueError: could not broadcast (32,0) into (32,40)
```

修复：`shift = min(max(1, int(w * 0.02)), w - 1)`，并在 `w < 2` 时早退。

### 2.9 其他退化尺寸崩溃

`kaleidoscope` / `mirror_reflection` / `dual_split` / `reduce_colors` / `glitch`：

- 空切片：`img_[:h // 2]`（h=1）、`img_[:, :w // 2]`（w=1）、
  `seg_w = size // segments`（size 小于 segments 时为 0），随后 `cv2.flip` / `np.hstack` /
  `cv2.resize` 行为不一致而报错。
- `reduce_colors`：kmeans 要求 `N >= K`，1×1 图只有 3 个样本却要 8 个簇。
- `glitch`：`rng.integers(0, h - 1)` 在 h=1 时抛 `high <= 0`。

### 2.10 `LineEditor` 的 gutter 在 `updateRequest` 之后才创建

`app/panels/shader_studio.py:24`：`self._gutter` 只在 `resizeEvent` 中惰性创建，
但 `updateRequest` 会先触发，`_update()` 无条件访问 `self._gutter`：

```
AttributeError: 'LineEditor' object has no attribute '_gutter'   （首次布局即出现，反复刷屏）
```

注意 Qt 会**吞掉槽函数中的异常**（只打印回溯、不中断），所以这类缺陷不会让程序退出，
只会静默失效并污染 stderr。修复：构造时创建 gutter。

### 2.11 失败任务永久泄漏（含全分辨率图像）

`app/workbench.py:108`：`Task._all_tasks` 是类级强引用列表，且 `setAutoDelete(False)`；
`_cleanup_task()` 只挂在 `finished` / `cancelled`，**`failed` 没有挂**。

复现（5 个失败 + 3 个成功任务）：

```
Task._all_tasks retained: 5
  names: ['fail0','fail1','fail2','fail3','fail4']
```

真实应用中任务闭包是 `make_filter_chain_worker(img.copy(), chain)`，
即**每次滤镜失败永久泄漏一张全分辨率图**（24MP 约 72MB）+ Task + TaskSignals。

---

## 3. 性能（全部为实测值）

环境：24MP (6000×4000) / 12MP (3000×4000) / 1200×1600，numba 0.67 可用。

| 项目 | 前 | 后 | 等价性 |
|---|---|---|---|
| 调整面板「应用调整」GUI 线程阻塞 | 2760 ms | **1.2 ms**（后台 78 ms） | 输出一致（除下述 ≤1 LSB 项） |
| `floyd_steinberg` 600×800 | 4479 ms | **5.2 ms** | **逐像素一致** |
| `floyd_steinberg` 24MP（外推） | 约 220 s | 约 0.4 s | 同上 |
| `circular_pixelation` 1200×1600 | 204 ms | **21 ms** | **逐像素一致**（266 组合校验） |
| `brightness` 12MP | 65 ms | 13.5 ms | **逐像素一致** |
| `contrast` 12MP | 103 ms | 13.1 ms | **逐像素一致** |
| `exposure` 12MP | 66 ms | 13.2 ms | **逐像素一致** |
| 参数预览降采样（48MP，每次滑块 tick） | 60 ms | 0.018 ms | 按 (identity,size,generation) 缓存 |
| 撤销历史（24MP，30 条） | 2060 MB | ≤ 512 MB | 按总字节预算裁剪 |

关键手法：

1. **跳过默认值步骤**：`_apply_adjust_chain` 原先无条件跑完 9 个调整。先验证了 9 个调整在
   各自默认值下都是恒等（`saturation`/`vibrance` 最多 1 LSB），因此跳过是安全的。
   24MP 实测 `0.81 s → 0.14 s`。
2. **256 项 LUT**：`brightness` / `contrast` / `exposure` 都是逐通道点运算，
   LUT 与浮点路径实测 `max|diff| = 0`。`gamma()` 本来就是 LUT（只需 21 ms），本轮把这个模式推广。
3. **转后台任务**：`_apply_adjust_full_res` 原先在 GUI 线程同步跑完全分辨率链路。
   重构为提交到任务队列（`_on_adjust_full_done`/`_on_adjust_full_failed` 原本是**从未 connect 的死代码**，
   说明这条异步路径此前没接上）。
4. **索引图 dtype**：`np.indices((h, w))` 默认 int64，与 float 运算后升级为 float64。
   `vignette` 因此每次重算 int64 索引网格 + float64 距离图；改为 float32 并按尺寸缓存掩膜。
   同类修正 3 处（`vintage`/`haze`/`wave`）。
5. **向量化替代 Python 逐块循环**：`circular_pixelation` 原为 24 万次 Python 迭代（24MP），
   改为 reshape 归约；对 266 组尺寸/块大小校验**逐像素一致**后才采纳。

> 曾尝试用 `cv2.resize(..., INTER_AREA)` 实现块平均（快 30x），但经 70 组对比发现
> **54 组不一致**（INTER_AREA 用的是缩放面积而非固定块），因此放弃 —— 记在这里避免后人重复踩坑。

未做 LUT 的剩余开销：`saturation`(311ms) / `vibrance`(473ms) / `highlights_shadows`(462~524ms)
/ `hue_shift`(478ms) 属非线性色彩变换，24MP 下单项约 0.3~0.5 s，是调整链剩余主要成本。

---

## 4. 健壮性

| 问题 | 证据 | 修复 |
|---|---|---|
| `mkdir(exist_ok=True)` 对已存在只读目录也成功 | 沙箱下 `~/.toolbox` 只读，`save_preset` 抛裸 `OSError`；（5 个预设测试因此失败） | `ensure_writable_dir()` 用真实临时文件探测；预设/GMIC 缓存回退到临时目录 |
| 预设非原子写 | 崩溃可留半截 JSON；`list_presets` 又 `except: continue` 静默丢弃 | 临时文件 + `fsync` + `os.replace`；`include_errors=True` 暴露损坏项 |
| 外部工具无超时 | `media._run`（magick/ffmpeg）、`parity` cjxl 均无 timeout，且在 UI 线程调用 | 补超时 + `FileNotFoundError`/超时归一为明确 `RuntimeError` |
| **gmic 在 stdin 非终端时读取命令管道并永久阻塞** | `echo -n "" \| gmic -input 16,16,1,1 -noise 5` 挂满 20s 超时；`< /dev/null` 才返回 | 全部 gmic 调用加 `stdin=subprocess.DEVNULL` |
| 取消未真正打通 | `FilterDef.apply` 从不把 `cancel_token` 转发给处理器；`parity.generate_fractal` 的取消检查是死代码 | 转发 `cancel_token`；`floyd_steinberg` 增加分 20 段的取消检查 |
| `QImage` 直接包裹 numpy 缓冲 | 非连续数组 stride 与假定的 `bytesPerLine` 不符 → 图像错位 | `_numpy_to_pixmap` 加 `np.ascontiguousarray` |
| 任务池并发 8 | 单条 24MP float32 流水线中间量约 288MB | 降为 4；`shutdown()` 有界等待，避免退出被最长滤镜卡住 |

---

## 5. 测试基线变化

```
修复前 : 223 tests / 9 errors
         9 个 error 全部来自只读 ~/.toolbox、~/.cache/toolbox（沙箱限制），非代码缺陷
         （其中 5 个预设测试已由可写性回退修复）
修复后 : 262 tests / 261 PASS / 1 error
         余 1 个 = test_gmic_backend.GmicTests.test_cli_run，pre-existing 环境问题
```

新增测试与验证强度：

- `tests/test_core.py`（19 项）— `processors/core.py` 此前**零覆盖**，这正是 `contrast` 回归能进 UI 的原因。
  **变异验证**：换回原 buggy 实现后 9 项中 7 项失败（`test_identity_at_default`、
  `test_does_not_posterize`、`test_matches_reference_formula`、`test_zero_is_identity`、
  `test_360_is_identity`、`test_rotates_the_whole_hue_circle`、`test_180_actually_inverts_low_hues`）。
- `tests/test_filter_robustness.py`（8 项）— 153 filters × 16 sizes = **2448 runs / 0 失败**
  （修复前 16 处崩溃）；灰度输入 153 项 / 0 失败。
- `tests/test_task_and_history.py`（10 项）— 失败任务回收、`shutdown()`、撤销语义、
  保存不再崩溃、历史字节预算、日志缓冲上限。
- `tests/test_shader_studio.py` — `LineEditorGutterTests`。

同时修正测试套件**自身的全局单例污染**：`tests/test_filter_chain_task.py` 注册的
`_test_boom`（故意抛 `RuntimeError`）会残留在 `FilterDefRegistry` 进程级单例中，
使我的全滤镜扫描在"全量运行"时出现假失败（单独运行则通过）。
新增 `FilterDefRegistry.unregister()` 并在 `tearDownModule` 清理；
`tests/test_filter_defs.py` 同样改为快照/还原。已验证执行顺序无关、运行后注册表无残留夹具。

---

## 6. 本轮仍未解决

1. `test_gmic_backend.GmicTests.test_cli_run`：本机沙箱下 `gmic` 无 `-output` 时行为不稳定。
   `stdin=DEVNULL` 已把"无限挂起"变成"有界返回"，但仍可能超过测试的 5s 超时。
   属 pre-existing 环境问题，未见代码缺陷。
2. 真实 Wayland/X11 GUI 与 Shader OpenGL runtime 仍无法在无显示环境验证
   （`QOpenGLWidget is not supported on this platform`）。
3. 非线性调整（`saturation` / `vibrance` / `highlights_shadows` / `hue_shift`）在 24MP 下
   单项 0.3~0.5 s，未做进一步优化（可用 LUT 化 HSL 近似或降采样预览）。
4. `app/main_window.py` 仍约 4400 行，职责拆分未完成。
5. coverage 工具仍未纳入，覆盖率仍为"未验证"。

---

## 7. 复现命令

```bash
# 全量测试
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests

# UI smoke（含应用/撤销/重置）
QT_QPA_PLATFORM=offscreen .venv/bin/python _smoke_test.py

# 新增回归测试
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_core tests.test_filter_robustness tests.test_task_and_history

# 全滤镜 x 尺寸扫描（2448 runs）
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_filter_robustness -v
```
