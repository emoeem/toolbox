# UI 功能迁移矩阵（Phase 0 交付）

> 现有 UI 全部功能 → Toolbox 2.0 新 UI 的映射。分类按升级计划 §4.3 的八大工具类，
> 目标 Phase 按升级计划 §7。**状态列只有两种真实取值**：`待迁移`（尚未开始）、
> `已迁移`（新 UI 中真实可用并验收）。禁止用"已注册"充当完成度
> （升级计划 §10 规则 8）。
>
> 现状证据与调用关系见 [architecture.md](architecture.md)。

> **Phase 5 进度备注（2026-11-06）**：核心图像编辑工作流垂直切片（打开/保存/
> 最近文件写入/画布接线/基础调整/撤销重做重置）已在 `phase4-ui-infra` 分支
> 实现，状态口径 `code_complete / static_reviewed`（CHANGELOG Phase 5 条目）。
> 按本文件头部规则，`已迁移` 要求"新 UI 中真实可用并验收"，CI 单测不构成
> 改判依据，故下方相关行状态仍为 **`待迁移`**，括注仅为进度说明而非状态
> 档位；实机验收清单见 docs/phase5-acceptance.md，通过后统一改判
> `已迁移` 并回填验收记录。Phase 列沿用 Phase 0 定稿时的计划分批（4 第一批
> /第三批/第五批），不改列；该批功能对应总纲 §7 现行 Phase 5 定义。

> **Phase 6A 进度备注（2026-11-07）**：滤镜系统垂直切片（滤镜目录浏览与搜索 /
> FilterDef 参数定义驱动控件 / 滤镜链增删排序启停 / 整链预览与应用 / 预设
> 保存加载删除）已在 `phase5-core-editing` 分支实现，状态口径
> `code_complete / static_reviewed`（CHANGELOG Phase 6A 条目）。按本文件头部
> 规则，`已迁移` 要求"新 UI 中真实可用并验收"，CI 单测不构成改判依据，故
> §1 相关行状态仍为 **`待迁移`**，括注仅为进度说明而非状态档位；实机验收
> 清单见 docs/phase6a-acceptance.md（流程 2 端到端 / G'MIC 类滤镜置灰 /
> 预览防抖与取消），通过后统一改判 `已迁移` 并回填验收记录。LUT 未在该批
> 范围（协议无 lut.* 动作）；G'MIC 库本体未在该批（§2 行，置灰机制除外）。
> 预览缓存（流程 2"缓存 key = 链参数指纹"）与链拖拽排序未实现，见
> CHANGELOG Phase 6A 已知限制。

> **Phase 6B 进度备注（2026-11-07）**：批量处理垂直切片（文件/目录导入 →
> 纯格式转换或滤镜链预设 → 输出设置 → 进度/取消 → 逐文件对账）已在
> `phase5-core-editing` 分支实现（协议 batch.start/batch.cancel/gmic.check +
> C++ BatchService/BatchModel + QML AppBatchWizard/BatchPage），状态口径
> `code_complete / static_reviewed`（CHANGELOG Phase 6B 条目）。按头部规则
> §4 相关行状态仍为 **`待迁移`**，括注仅为进度说明；实机验收清单见
> docs/phase6b-acceptance.md，通过后统一改判 `已迁移` 并回填验收记录。
> 该批不含：批量重命名独立 UI（仅其 pattern 占位符语义被批处理命名复用）、
> 智能缩放、覆盖开关 UI（协议固定覆盖）、"打开输出目录"/"失败重试"
> 按钮、G'MIC 库本体（§2 行不变）。

> **Phase 6C 进度备注（2026-11-07）**：统一 Studio 工作区垂直切片（生成器
> 目录 generate.list → 参数定义驱动控件 → generate.render 渲染预览 →
> 导出编辑器/另存）已在 `phase6b-batch-gmic` 分支工作区实现（协议
> generate.list/generate.render + C++ StudioService/GeneratorModel + QML
> StudioPage/AppStudioPage；截至本备注撰写未提交），状态口径
> `code_complete / static_reviewed`（CHANGELOG Phase 6C 条目）。按头部规则
> §3 渐变/分形/Texture Studio/Shader Studio 行状态仍为 **`待迁移`**，括注
> 仅为进度说明而非状态档位；实机验收清单见 docs/phase6c-acceptance.md
> （选生成器→调参→渲染预览→导出编辑器/另存端到端 / 无依赖生成器置灰路径 /
> 非模态与恢复 / 大尺寸渲染），通过后统一改判 `已迁移` 并回填验收记录。
> 该批不含：三个分 Studio 页分流（FractalPage/TexturePage/ShaderPage 仍为
> 占位页，"创作"入口路由统一 StudioPage）、Shader Studio 本体（GLSL 编辑/
> GL 预览——协议面 shader:preview 恒置灰优雅降级）、Texture Studio 的预设
> 管理/缩略图缓存/平铺预览、另存为（C++ savePreviewAs 未实现，UI 如实提示
> 暂不可用）、photomosaic / fusion（1.0 中为文件→文件工具而非参数驱动的
> 生成器，协议不注册）。

> **Phase 7 进度备注（2026-11-07）**：辅助工具垂直切片（统一工具页：目录
> 浏览 assist.list → 选择工具 → 参数 JSON 提交 → 运行（sync 直答 / async
> 任务）→ 结果呈现/导出编辑器；OCR / PDF×8 / 条形码×3 / ASCII / 对比 /
> 校验和 / 直方图 / LUT / 媒体×2 / EXIF×2 / 水印 / 归档 / 加密×2 /
> Base64×2 / AI×5 共 32 个工具动作 + 新错误码 `DEPENDENCY_MISSING`）已在
> 工作区实现（协议 docs/ipc-protocol.md §3.8 + Worker
> assist_adapter/dispatcher + C++ AssistService/AssistModel + QML
> AppToolsPage/ToolsPage + 一级导航 "files" 接线；截至本备注撰写未提交），
> 状态口径 `code_complete / static_reviewed`（CHANGELOG Phase 7 条目）。按
> 本文件头部规则，§1/§3/§5/§6/§7 相关行状态仍为 **`待迁移`**，括注仅为
> 进度说明而非状态档位；实机验收清单见 docs/phase7-acceptance.md（工具
> 目录浏览→OCR/PDF/小工具逐项→依赖缺失置灰路径 / AI 降级说明 / 实机项与
> CI 项分列），通过后统一改判 `已迁移` 并回填验收记录。该批不含（协议未
> 注册，行内括注逐项如实）：EXIF 按 Tag 编辑、图片→PDF、压缩实验室/
> 按体积压缩、重复/相似图片查找、AI 深度图、DataMatrix（1.0 实现为 QR
> 伪实现，不凭空造实现）、EAN-13 的 PIL 兜底伪条码（依赖缺失即拒绝）；
> AI 模型安装/下载不在动作面（`ai.models.list` 只读）；工具页参数面板为
> 参数 JSON 编辑器（逐工具表单化属后续批次）。

> **Phase 9 进度备注（2026-11-07）**：编辑器补全垂直切片（检查器"变换"
> 页签：裁剪八手柄 + 比例锁定 / 自由旋转防抖预览与应用 / 透视四角校正 /
> 按目标尺寸缩放，经 `image.transform` 新式组合参数；标注画布模式八工具
> 经 `image.annotate`；对比模式 AppCompareSlider；保存选项对话框
> `image.save target_kb`）已在 `phase9-editing` 分支工作区实现（协议
> docs/ipc-protocol.md §3.2/§3.9 Phase 9 增补 + Worker
> image_adapter/dispatcher + C++ DocumentService.applyTransform/applyAnnotate
> + QML EditorPage 变换页签与 AppCropOverlay/AppPerspectiveOverlay/
> AppAnnotateOverlay/AppAnnotateToolbar/AppCompareSlider；截至本备注撰写
> 未提交），状态口径 `code_complete / static_reviewed`（CHANGELOG Phase 9
> 条目）。按本文件头部规则，§0/§1/§3 相关行状态仍为 **`待迁移`**，括注
> 仅为进度说明而非状态档位；实机验收清单见 docs/phase9-acceptance.md
> （变换页签端到端 / 标注八工具 绘制→提交→undo 参数化重放像素一致 /
> 对比滑块 / 目标大小导出实测分步；实机项与 CI 已覆盖项分列），通过后
> 统一改判 `已迁移` 并回填验收记录。该批不含：1.0 批量"按大小压缩"工具
> （保存对话框 target_kb 只覆盖保存时单图 JPEG/WebP 目标大小，压缩实验室
> 系各行不变）；`target_kb` 的 C++ 消费侧请求方向已随 2026-11-08 修复轮
> 接线（saveDocument 第三参，EditorPage 直调三参），响应方向 `documentSaved`
> 仍无 fileSize（保存完成 Toast 无实际大小显示，见 ipc-protocol.md §3.9 末
> 消费侧复查注），目标大小导出实测见 phase9-acceptance.md §5（文件字节以
> `stat` 核对）。

## 0. 全局功能（不属于单一工具）

| 现有功能 | 旧入口 | Phase | 状态 |
|---|---|---|---|
| 打开 / 保存 / 另存为 | `app/main_window.py:2253-2310` | 4 第一批 | 待迁移（Phase 5 编辑器内已实现打开/保存/另存链路，待实机验收） |
| 拖放打开图像 | `app/preview_widget.py:194-205` | 4 第一批 | 待迁移（Phase 5 编辑器画布已接拖放，待实机验收） |
| 最近文件 | `app/main_window.py:2276-2278`（列表不持久化，属已知缺陷） | 4 第一批 | 待迁移（持久化修复与写入/展示已实现；HomePage 行点击打开未接线，待实机验收） |
| 图像信息 | `app/main_window.py:2193`、`4101` | 4 第一批 | 待迁移 |
| 撤销 / 重置 | `app/main_window.py:390, 406` | 4 第五批 | 待迁移（Phase 5 已实现 undo/redo/reset + HistoryModel——"新架构补 Redo"已落地，待实机验收） |
| 缩放/平移/适配/100% | `app/preview_widget.py` | 4 第二批 | 待迁移（ImageCanvas 既有能力，Phase 5 编辑器接线缩放控件，待实机验收） |
| 透明棋盘格 / 图像比较 | `app/preview_widget.py` / `2740` | 4 第二批 | 待迁移（透明棋盘格为 ImageCanvas 既有能力；Phase 9 已实现编辑器对比模式 AppCompareSlider——原图/当前图分割滑块、进入即禁用其他交互、Esc/再点退出，纵横比不同后按各自外接框居中不逐像素对位（辅助视图语义），待实机验收） |
| 工具搜索 Ctrl+K | `app/main_window.py:600` | 3 | 待迁移 |
| 主题 system/dark/light | `app/main_window.py:578` | 3 | 待迁移 |
| 设置（字体/主题/并发/输出/后端诊断） | `app/main_window.py:485-520` | 3 | 待迁移 |
| 任务队列 / 运行日志 Dock | `app/workbench.py:78, 139` | 3 | 待迁移（语义平移到 task_service） |
| 后端状态诊断 | `backends/registry.py:15` | 3（诊断页）/ 7 | 待迁移 |
| ImageToolbox 功能补齐面板（67 项清单 + 60 按钮） | `app/main_window.py:3327-3684` | — | **不迁移**（元功能；真实功能由下列条目吸收，未实现项按 §6 规则明确标注） |

## 1. 图像编辑（新 UI 分类）

| 现有功能 | 旧入口 | processors | 外部依赖 | Phase | 状态 |
|---|---|---|---|---|---|
| 调整（亮度/对比度/饱和度/伽马/曝光/色相/自然饱和度/高光阴影） | `_build_adjust_panel` `app/main_window.py:721` | `core.brightness/contrast/saturation/gamma/exposure/hue_shift/vibrance/highlights_shadows` | numpy/cv2 | 4 第三批 | 待迁移（Phase 5 已实现九键 image.adjust + 滑杆预览/应用，待实机验收） |
| 裁剪（尺寸/中心/比例） | `1781` | `core.crop/center_crop/aspect_crop` | — | 4 第三批 | 待迁移（Phase 9 已实现画布交互式裁剪 AppCropOverlay：八向手柄/矩形整体拖动/重新拉框/三分线/比例锁定（自由、1:1、4:3、3:4、16:9、9:16），经 image.transform 组合参数应用；1.0 的尺寸/中心数值式裁剪面板未做，待实机验收） |
| 变换（旋转/90°/翻转/缩放） | `1881` | `core.rotate/flip_h/flip_v/scale` | — | 4 第三批 | 待迁移（Phase 5 已接入旋转90°/水平翻转/垂直翻转；Phase 9 已实现"变换"页签：自由旋转（滑杆 300ms 防抖预览 + expand 两态应用）、透视四角校正（AppPerspectiveOverlay，输出画布 = 四角外接矩形）、按目标尺寸缩放（lanczos/bilinear/nearest/bicubic）——均经 image.transform 组合参数（DocumentService.applyTransform 嵌套线形），待实机验收） |
| 滤镜（78 内置，可搜索调参预览） | `944` | `FilterDefRegistry` + `filters.ALL_FILTERS` | opencv/skimage | 4 第四批 | 待迁移（Phase 6A 已实现滤镜页签：目录浏览/搜索、FilterDef 参数控件、不可用滤镜置灰 + 原因、整链预览与应用；预览缓存未实现，待实机验收） |
| 滤镜链（增删/排序/启停/预设持久化） | `1000-1244` | `filter_chain` + `filter_presets` | — | 4 第四批 | 待迁移（Phase 6A 已实现链增删/↑↓排序/启停与 `filter.presets.*` 四动作保存/加载/删除接线；拖拽排序未实现（↑/↓ 代替），待实机验收） |
| LUT / 色调曲线 | `3096` | `lut.apply_lut/tone_curve`（.cube 加载 UI 未接） | — | 4 第四批 | 待迁移（补 .cube；Phase 7 协议新增 `lut.apply` 动作（.cube 解析失败提交前拒绝）并以工具页条目承载——参数 JSON 提交，逐工具表单化 UI 未做；色调曲线未迁移） |
| 高级胶片滤镜（45+） | `4279` | `advanced_filters`（75 函数） | numpy/cv2 | 4 第四批 | 待迁移 |
| 色彩工具（反色/灰度/均衡/CLAHE/暗角/5 色调色板） | `1712` | `core.invert/grayscale/histogram_equalize/clahe/vignette` | — | 4 第三批 | 待迁移 |
| 格式转换（PNG/JPEG/WebP/TIFF/BMP/HEIC/AVIF/JXL/ICO） | `1378` | `utils.save_image` | pillow-heif/avif/jxl 可选 | 4 第一批 | 待迁移 |
| 高级图像工具（按大小压缩/自动裁边/加边框） | `2141` | PIL 循环压缩 + `core.crop/border` | cv2 | 4 第三批 | 待迁移 |

## 2. 滤镜效果（G'MIC 归本类，Phase 5）

| 现有功能 | 旧入口 | processors | 外部依赖 | Phase | 状态 |
|---|---|---|---|---|---|
| G'MIC 滤镜库（命令行应用 + 帮助） | `1928` | `processors/gmic.py`（未走 backends/ 抽象，双轨之一） | **gmic** | 5 | 待迁移（收敛到 backends/；Phase 6A 滤镜页签交付依赖缺失置灰机制 available/optional_deps，但 G'MIC 滤镜未进入 FilterDefRegistry，库本体未迁移） |

## 3. 图像创作（Phase 5）

| 现有功能 | 旧入口 | processors | 外部依赖 | Phase | 状态 |
|---|---|---|---|---|---|
| 渐变（线性/径向/网格预设） | `2869` | `gradients.linear/radial/mesh` + `MESH_PRESETS` | — | 5（Gradient Studio） | 待迁移（Phase 6C 已以 gradient:linear/radial/mesh 生成器条目进入统一 Studio 工作区：目录/参数控件（color 发 hex）/渲染预览/导出编辑器接线；独立 Gradient 分页不分流，待实机验收） |
| 分形生成器（13 公式/超采样/着色） | `4342` | `fractal.render_fractal` 全家 | numba 可选 | 5（Fractal Studio） | 待迁移（Phase 6C 已以 fractal:<formula>——`_2D_FORMULAS` 全部 15 个 2D 公式——与 fractal:mandelbulb 生成器条目进入统一 Studio 工作区：公式能力裁剪的参数控件、逐行取消检查点、渲染预览/导出接线；分形 Studio 页的缩放导航/预设未分流，待实机验收） |
| Texture Studio（噪声/图案/G'MIC 纹理/SDF raymarch、预设、缩略图缓存） | `app/panels/texture_studio.py:62` | `texture_studio.*`（自建线程池） | gmic 可选 | 5（Texture Studio） | 待迁移（Phase 6C 已以 texture:noise×5/pattern×5/raymarch:orb/gmic×4 生成器条目进入统一 Studio 工作区：缺省参数取 1.0 内置预设、gmic 缺失时该族置灰 + 原因、同种子可重复；预设管理/缩略图缓存/平铺预览未迁移，待实机验收） |
| Shader Studio（GLSL 编辑/高亮/GL 预览/uniform 自动参数/导入导出） | `app/panels/shader_studio.py:97` | `shader_studio.*` | **glslangValidator** 可选 | 5（Shader Studio，真实图形会话验收） | 待迁移（Phase 6C 仅交付协议面优雅降级：generate.list 的 shader:preview 恒 `available=false` + optional_deps 含 opengl/glslangValidator，Studio 页置灰；GLSL 编辑/GL 预览/uniform 未迁移，真实图形会话验收不变） |
| CPU Shader 快捷（invert/posterize/scanlines/vignette） | `3243` | `parity.shader_cpu` | — | 5 | 待迁移 |
| Photomosaic（≥10 素材） | `3273` | `parity.photomosaic` | — | 5 | 待迁移 |
| 多帧融合 | `3285` 附近 | `parity.multi_frame_fusion` | — | 5 | 待迁移 |
| SVG / WebP / JXL / APNG / GIF 帧 | `4111` | `parity.svg/webp/jxl/apng/gif-frames` + `media.convert_animation` | **ImageMagick、ffmpeg**（JXL 动画）；pillow-jxl | 5（SVG）/ 6（动画格式） | 待迁移 |
| 拼接/拼贴（横纵/网格/分割）+ 快速拼图 | `2910`、`4231` | `stitch.*` + `parity.contact-sheet/collage` | — | 5 | 待迁移 |
| 分割/堆叠/切割 | `3763` | `parity.split-grid/stack/cut` | — | 5 | 待迁移 |
| 形状蒙版 | `2643` | `shapes.apply_shape_mask` + `SHAPE_PRESETS` | — | 5 | 待迁移 |
| 绘图/标注（文字/边框/自动裁边/水印） | `3910` | `parity.text/border/auto-crop/watermark` | Pillow | 5（绘图与标注） | 待迁移（Phase 9 已实现编辑器标注画布模式：pen/text/rect/ellipse/arrow/blur_rect/pixelate_rect/eraser 八工具绘制 → `image.annotate` 全分辨率提交 + 参数化 undo 重放，待实机验收；文字水印此前经 Phase 7 `watermark.text` 工具页条目承载；1.0 的边框/自动裁边未注册） |
| 调色板/颜色库（提取/取色/替换/PDF） | `3832` | `parity.palette/color-sample/color-replace/palette-pdf` | reportlab（PDF） | 5 | 待迁移 |

## 4. 批量工具（Phase 5）

| 现有功能 | 旧入口 | processors | 外部依赖 | Phase | 状态 |
|---|---|---|---|---|---|
| 批量处理（目录扫描/滤镜链或转换/覆盖开关） | `2963` | `batch_filter_chain.run_batch_filter_chain`（含取消） | — | 5（Batch） | 待迁移（Phase 6B 已实现批量向导：目录递归扫描、纯转换/滤镜链预设、命名三态、进度/取消/逐文件对账——覆盖开关未暴露（协议固定覆盖）、打开输出目录与失败重试未实现，待实机验收） |
| 批量重命名（模板/预览/执行） | `3298` | `parity.batch_rename/apply_batch_rename`（`processors/batch.py:101` 未接 UI） | — | 5（Batch） | 待迁移（独立重命名 UI 未迁移；其 pattern 占位符语义被 Phase 6B 批处理命名 pattern 复用） |
| 智能缩放（25 平台预设/自定义/按 KB） | `3139` | `batch.SOCIAL_PRESETS/smart_resize_by_size/resize_to_weight` | Pillow | 5（Batch） | 待迁移 |

## 5. 图像分析（Phase 6）

| 现有功能 | 旧入口 | processors | 外部依赖 | Phase | 状态 |
|---|---|---|---|---|---|
| 直方图（RGB/Luma/HSV，PIL 绘制） | `2673` | `histogram.*` | Pillow | 6（编辑器集成候选，Phase 4 评估） | 待迁移（Phase 7 协议 `histogram.compute` rgb/luma/hsv 三模式已实现并以工具页 JSON 结果承载；PIL 绘制图表与编辑器集成未迁移） |
| 图像比较（MAE/RMSE/PSNR/NCC/SSIM + 差异图） | `2740` | `compare.compare/difference_image` | scikit-image | 6 | 待迁移（Phase 7 协议 `compare.images` 六指标已实现（非有限值 → null）；差异图未迁移） |
| 文件校验和（MD5/SHA*/CRC32/Blake2） | `2788` | `checksum.all_hashes/file_hashes`（"xxhash"为自实现近似，注意） | — | 6 | 待迁移（Phase 7 协议 `checksum.file` 七算法 + size 已实现并以工具页承载） |
| 查找（重复/相似/信息） | `4055` | `parity.duplicate-finder/similar/image-info` | Pillow | 6 | 待迁移 |
| EXIF（读取/按 Tag 编辑/删除） | `1518` | `parity.edit_exif`（PIL getexif） | Pillow | 6 | 待迁移（Phase 7 协议 `exif.extract` / `exif.strip` 已实现；按 Tag 编辑未注册） |

## 6. AI 工具（Phase 6）

| 现有功能 | 旧入口 | processors | 外部依赖 | Phase | 状态 |
|---|---|---|---|---|---|
| AI 抠图（4 模型/Alpha Matting/换底/人像虚化） | `2335` | `ai.remove_background/composite_on_bg/portrait_bokeh` | **rembg + onnxruntime** 可选 | 6 | 待迁移（Phase 7 协议 `ai.background.remove` 已实现：rembg+onnxruntime+模型文件三重探测，缺失 → 置灰 + `DEPENDENCY_MISSING`；`background` 参数换底；Alpha Matting/人像虚化未注册） |
| AI Upscale（2x-8x；Lanczos/Bicubic/AI） | `2412` | `ai.upscale_*`；AI 路径硬编码 `/usr/bin/upscayl*` | **upscayl** 外部程序 | 6 | 待迁移（Phase 7 协议 `ai.upscale` 已实现：EDSR 模型路径可配置（settings `model_paths`/`TOOLBOX_AI_MODEL_DIR`，OpenCV DNN）优先，否则 upscayl + Real-ESRGAN 系统模型——"路径需可配置"已落地；Lanczos/Bicubic 预设未注册） |
| AI 降噪（NLM/双边/中值/小波） | `2467` | `ai.denoise_*` | cv2 | 6 | 待迁移（Phase 7 协议 `ai.denoise` 已实现（NLM，OpenCV 核心恒可用）；双边/中值/小波变体未注册） |
| AI 深度图（启发式/U²-Net/ISNet） | `2604` | `ai.depth_map/depth_map_rembg` | rembg 可选 | 6 | 待迁移（Phase 7 协议未收深度图动作） |
| AI 色彩化/风格化（纯 numpy 实现，非真 AI 模型） | `2501` | `ai.colorize_transfer/ai_enhance` | — | 6 | 待迁移（Phase 7 协议 `ai.colorize` simple/transfer 已实现——状态仍如实标注为算法模拟非模型） |
| AI 模型管理器（安装/删除/后端切换） | `2539` | `ai_models.registry/install/uninstall/set_backend/detect_backends` | rembg 缓存目录 | 6 | 待迁移（Phase 7 协议 `ai.models.list` 只读视图已实现（注册表真实安装状态/后端探测/模型路径配置）；安装/删除/后端切换不在动作面） |

## 7. 文件工具（Phase 6）

| 现有功能 | 旧入口 | processors | 外部依赖 | Phase | 状态 |
|---|---|---|---|---|---|
| 图片→PDF（A4/A3/Letter） | `1422` | PIL 直存 | Pillow | 6 | 待迁移（Phase 7 协议未收图片→PDF 动作） |
| PDF 高级（合并/拆分/旋转/删页/提取文本/加密） | `2033` | `pdf_tools.*` | pypdf；pdf2image 仅声明未使用（PDF→图未实现，UI 仅提示） | 6 | 待迁移（Phase 7 协议 `pdf.merge/split/rotate/remove_pages/extract_text/set_metadata/protect` 已实现；"PDF→图"经 `pdf.to_images` 真实接线（pdf2image + poppler，1.0 仅提示的未实现项落地），工具页承载；1.0 表单化面板未迁移——参数 JSON 提交） |
| OCR（6 语言/4 布局） | `1601` | pytesseract 直调 + `parity.ocr_to_file` | **tesseract** | 6 | 待迁移（Phase 7 协议 `ocr.run`（lang/psm，pytesseract+tesseract 双探测）已实现并以工具页承载；6 语言/4 布局表单化 UI 未做） |
| 压缩/打包（ZIP） | `2111` | stdlib zipfile | — | 6 | 待迁移（Phase 7 协议 `archive.create` 已实现并以工具页承载） |
| 加密/Base64（fernet 文件加密、编码解码） | `3686` | `parity.base64-*/encrypt/decrypt/archive` | cryptography | 6 | 待迁移（Phase 7 协议 `crypto.encrypt/decrypt`、`base64.encode/decode` 已实现——cryptography 缺失时置灰 + `DEPENDENCY_MISSING`） |
| 压缩实验室（JPEG/WebP 质量滑杆/按 KB/格式转换） | `3986` | `parity.compress/webp/weight-resize/convert` | Pillow | 6 | 待迁移（Phase 7 协议未收压缩实验室动作） |
| 尺寸/体积缩放 | `4181` | `parity.limits-resize/weight-resize/convert` | Pillow | 6 | 待迁移 |
| 条形码/二维码（生成 QR/解码） | `2830` | `barcode.generate_qr/decode_qr` | qrcode、pyzbar 可选 | 6 | 待迁移（Phase 7 协议 `barcode.qr.generate/ean13.generate/decode` 已实现——EAN-13 需 pystrich、PIL 伪码兜底不暴露；DataMatrix 未注册） |
| 动画（GIF/WebP/APNG 合成与拆帧） | `1974` | `media.convert_animation/extract_frames` | **ImageMagick、ffmpeg** | 6 | 待迁移（Phase 7 协议 `media.extract_frames/convert_animation` 已实现（magick/ffmpeg 按 fmt 如实探测，缺失置灰）） |

## 8. 设置（Phase 3）

| 现有功能 | 旧入口 | 说明 | Phase | 状态 |
|---|---|---|---|---|
| 字体设置（UI 族/字号/等宽族） | `app/main_window.py:485-520` | Phase 0 已修复强制覆盖；新 UI 按 §5.3 扩展（回退/预览/恢复默认/等宽字号） | 3 | 待迁移 |
| 主题/并发/输出目录/最近文件开关 | 同上 | — | 3 | 待迁移 |
| 后端诊断页 | `app/main_window.py:498-513` | 依赖 `backends/registry` | 3 | 待迁移 |
| 布局持久化 | `app/main_window.py:270-279` | 仅窗口 geometry/state | 3 | 待迁移（扩展面板布局） |

## 统计口径

- 侧栏工具 45 项 + 独立面板 2 个 + 全局功能 13 项；上表逐项对应，无遗漏
  （creator 面板 8 种 kind 已拆入 §3 对应行）。
- 外部依赖汇总（新 UI 需保留诊断能力）：**gmic、ImageMagick(magick)、ffmpeg、
  tesseract、glslangValidator、upscayl(-bin)**；可选 Python 包：rembg、onnxruntime、
  qrcode、pyzbar、cryptography、reportlab、mutagen、numba、pillow-heif/avif/jxl。
- 已知未实现/降级项（迁移时必须保持真实标注）：.cube LUT 加载（Phase 7 已有
  `lut.apply` 协议动作 + 工具页条目，逐工具表单化 UI 未做）、AI 色彩化（算法
  模拟非模型）、批量重命名 `processors/batch.py:101`
  （双实现未接 UI）、`checksum` 的 xxhash 为自实现近似；PDF→图片已由
  Phase 7 `pdf.to_images` 真实接线（pdf2image + poppler——1.0 的"仅提示"
  未实现项落地，缺 poppler 时置灰 + `DEPENDENCY_MISSING`）。
