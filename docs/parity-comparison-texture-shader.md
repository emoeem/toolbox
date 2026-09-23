# ImageToolbox / Toolbox 样本对照

日期：2026-09-23
参考：`/home/emo/code/ImageToolbox/feature`
实现：`/home/emo/code/toolbox`

## 1. Texture Studio：Perlin / Pattern

### 参考实现证据

- `texture-generation/.../TextureFilterType.kt`：FastNoise 类型远多于 Toolbox；除 Perlin 类噪声外还有大量 Brick、Cloud、Wood、Fire、Aurora、3D Raymarch、Pattern 等类型。
- `FastNoiseTextureParams.kt`：FastNoise 参数至少包含 `seed`、`scale` 和类型相关 `values/colors`。
- `PatternParams.kt`：Pattern 用户参数包括颜色、类型参数、`frequency`、`offsetX`、`offsetY`、`rotation`，并且参数有明确范围；例如 frequency `0.1..64`、offset `-1..1`、rotation `-180..180`。
- `PatternTextureGenerator.kt`：Pattern 使用 GPU shader，并按参数写入 uniform。

### Toolbox 实际证据

- `processors/texture_studio/presets.py`：当前内置 noise 只有 `perlin/simplex/value/worley/cellular`；pattern 只有 `stripes/rings/checker/dots/grid`。
- `app/panels/texture_studio.py`：Noise 参数为 `scale/octaves/persistence/lacunarity/seed/contrast/brightness/warp`；Pattern 参数为 `size/spacing/angle/anti_alias`，另有颜色。
- 实际运行 `generate('perlin', 128, 96, ...)`：default SHA `1ba26147d428`；seed 改为 99 后 SHA `7963dce2f443`，参数确实生效。
- 实际运行 `pattern:stripes`：angle 0 SHA `5e9412c27038`；angle 90 SHA `08744fc70727`，参数确实影响输出。

| 功能点 | ImageToolbox | Toolbox | 差距 | equivalent |
|---|---|---|---|---|
| Perlin/Noise 基本生成 | 有 FastNoise 纹理体系 | 有 Perlin | 有 | ❌ |
| Noise seed | 有 | 有 | 当前核心路径一致 | ❌（整体条件未满足） |
| Noise scale | 有 | 有 | 参数语义/范围未证明一致 | ❌ |
| Noise 参数体系 | 类型相关 values/colors，类型很多 | 8 个通用参数 | 覆盖不足 | ❌ |
| Pattern 类型数量 | 大量 PatternTextureType | 5 种 | 明显缺失 | ❌ |
| Pattern frequency | 有，0.1..64 | 当前实现没有 frequency UI 参数 | 缺失 | ❌ |
| Pattern offset X/Y | 有，-1..1 | 当前实现没有 offset X/Y | 缺失 | ❌ |
| Pattern rotation | 有，-180..180 | 有 angle | 名称相近但语义未证明相同 | ❌ |
| Pattern colors | 有 colorCount/颜色列表 | 有固定 color_a/b/background | 参数模型不同 | ❌ |
| GPU shader 生成 | 有 | 有 CPU/Numpy 路径及 backend 选择 | 后端/实现不同 | ❌ |

**结论：Texture Studio 样本不能升级 `equivalent`。** 不是输出是否非空的问题，而是参考项目的类型、参数和边界覆盖明显更广。

## 2. Shader Studio：Color Invert / Grayscale / Tint

### 参考实现证据

ImageToolbox 的 `shader-studio` 是**通用 Shader 编辑器/预览器**：

- `ShaderStudioComponent.kt`：创建、编辑、保存、导入、导出、删除 Shader preset。
- `ShaderPresetEditor.kt` / `ShaderLibrary.kt`：编辑器、参数、库、导入/导出/分享/删除路径。
- `ShaderFilter.kt`：对有效 `ShaderPreset` 执行 GPU transformation；非法 preset 回退为原图。
- 本轮没有在 Android runtime 中找到名为 `Color Invert`、`Grayscale`、`Tint` 的参考内置 preset，因此不能把这三个名称假定为 ImageToolbox 的官方固定功能点。

### Toolbox 实际证据

`processors/shader_studio/library.py` 有三个本地 built-in：

- `Color Invert`
- `Grayscale`
- `Tint`

但实际执行 `processors.parity.shader_cpu()` 后：

| preset | 实际执行 | 输出 | 结果 |
|---|---|---|---|
| Color Invert | `effect='invert', strength=0.5` | 32×24，SHA `3f7284ae31e7` | ✅ |
| Grayscale | `effect='grayscale'` | 当前函数未实现该 effect，实际保持原图 | ❌ |
| Tint | `effect='tint'` | 当前函数未实现该 effect，实际保持原图 | ❌ |

另外，`app/panels/shader_studio.py` 已实现 GLSL 编辑、验证、uniform 控件、预览、保存、导入、导出、删除，但本轮没有真实 OpenGL GUI 会话，因此 GUI 闭环不升级为 equivalent。

| 功能点 | ImageToolbox | Toolbox | 差距 | equivalent |
|---|---|---|---|---|
| 自定义 GLSL | 有 | 有 | 核心方向一致 | ❌ |
| GLSL 验证 | 有 `ShaderValidator` | 有 `validate_glsl` | 验证规则未逐项对齐 | ❌ |
| Uniform 参数 | 有 ShaderParam | 有 uniform parser + 控件 | 参数范围规则未逐项对齐 | ❌ |
| 实时预览 | GPU | OpenGL widget | GUI 未真机验证 | ❌ |
| 保存 preset | 有 | 有 | 需逐项比较格式 | ❌ |
| 导入/导出 | 有 | 有 | 格式/错误语义未逐项对照 | ❌ |
| 删除 | 有 | 有 | 有 | ❌ |
| 分享 | 有 | 当前无对应分享动作 | 缺失 | ❌ |
| Color Invert | 本轮未证实为官方内置 preset | 有 | 不能作为参考等价证据 | ❌ |
| Grayscale | 本轮未证实为官方内置 preset | 有名义 preset，但 CPU effect 未实现 | 实际行为缺失 | ❌ |
| Tint | 本轮未证实为官方内置 preset | 有名义 preset，但 CPU effect 未实现 | 实际行为缺失 | ❌ |

**结论：Shader Studio 样本不能升级 `equivalent`。** 其中 Toolbox 的 `Grayscale/Tint` 名义 preset 与 CPU 执行器之间存在实际缺口，这也是本轮发现的 P2/P3 候选问题，但按当前提交策略暂不新增修复，先记录。

## 3. 样本等级变化

- Texture Studio：保持原等级，不升级。
- Shader Studio：保持 `未验证`，不升级。
- `equivalent`：**0 → 0**。

原因不是“差一点也算”，而是两项都存在明确未覆盖或未验证的硬条件。
