# UI 功能迁移矩阵（Phase 0 交付）

> 现有 UI 全部功能 → Toolbox 2.0 新 UI 的映射。分类按升级计划 §4.3 的八大工具类，
> 目标 Phase 按升级计划 §7。**状态列只有两种真实取值**：`待迁移`（尚未开始）、
> `已迁移`（新 UI 中真实可用并验收）。禁止用"已注册"充当完成度
> （升级计划 §10 规则 8）。
>
> 现状证据与调用关系见 [architecture.md](architecture.md)。

## 0. 全局功能（不属于单一工具）

| 现有功能 | 旧入口 | Phase | 状态 |
|---|---|---|---|
| 打开 / 保存 / 另存为 | `app/main_window.py:2253-2310` | 4 第一批 | 待迁移 |
| 拖放打开图像 | `app/preview_widget.py:194-205` | 4 第一批 | 待迁移 |
| 最近文件 | `app/main_window.py:2276-2278`（列表不持久化，属已知缺陷） | 4 第一批 | 待迁移（含持久化修复） |
| 图像信息 | `app/main_window.py:2193`、`4101` | 4 第一批 | 待迁移 |
| 撤销 / 重置 | `app/main_window.py:390, 406` | 4 第五批 | 待迁移（新架构补 Redo） |
| 缩放/平移/适配/100% | `app/preview_widget.py` | 4 第二批 | 待迁移 |
| 透明棋盘格 / 图像比较 | `app/preview_widget.py` / `2740` | 4 第二批 | 待迁移 |
| 工具搜索 Ctrl+K | `app/main_window.py:600` | 3 | 待迁移 |
| 主题 system/dark/light | `app/main_window.py:578` | 3 | 待迁移 |
| 设置（字体/主题/并发/输出/后端诊断） | `app/main_window.py:485-520` | 3 | 待迁移 |
| 任务队列 / 运行日志 Dock | `app/workbench.py:78, 139` | 3 | 待迁移（语义平移到 task_service） |
| 后端状态诊断 | `backends/registry.py:15` | 3（诊断页）/ 7 | 待迁移 |
| ImageToolbox 功能补齐面板（67 项清单 + 60 按钮） | `app/main_window.py:3327-3684` | — | **不迁移**（元功能；真实功能由下列条目吸收，未实现项按 §6 规则明确标注） |

## 1. 图像编辑（新 UI 分类）

| 现有功能 | 旧入口 | processors | 外部依赖 | Phase | 状态 |
|---|---|---|---|---|---|
| 调整（亮度/对比度/饱和度/伽马/曝光/色相/自然饱和度/高光阴影） | `_build_adjust_panel` `app/main_window.py:721` | `core.brightness/contrast/saturation/gamma/exposure/hue_shift/vibrance/highlights_shadows` | numpy/cv2 | 4 第三批 | 待迁移 |
| 裁剪（尺寸/中心/比例） | `1781` | `core.crop/center_crop/aspect_crop` | — | 4 第三批 | 待迁移 |
| 变换（旋转/90°/翻转/缩放） | `1881` | `core.rotate/flip_h/flip_v/scale` | — | 4 第三批 | 待迁移 |
| 滤镜（78 内置，可搜索调参预览） | `944` | `FilterDefRegistry` + `filters.ALL_FILTERS` | opencv/skimage | 4 第四批 | 待迁移 |
| 滤镜链（增删/排序/启停/预设持久化） | `1000-1244` | `filter_chain` + `filter_presets` | — | 4 第四批 | 待迁移 |
| LUT / 色调曲线 | `3096` | `lut.apply_lut/tone_curve`（.cube 加载 UI 未接） | — | 4 第四批 | 待迁移（补 .cube） |
| 高级胶片滤镜（45+） | `4279` | `advanced_filters`（75 函数） | numpy/cv2 | 4 第四批 | 待迁移 |
| 色彩工具（反色/灰度/均衡/CLAHE/暗角/5 色调色板） | `1712` | `core.invert/grayscale/histogram_equalize/clahe/vignette` | — | 4 第三批 | 待迁移 |
| 格式转换（PNG/JPEG/WebP/TIFF/BMP/HEIC/AVIF/JXL/ICO） | `1378` | `utils.save_image` | pillow-heif/avif/jxl 可选 | 4 第一批 | 待迁移 |
| 高级图像工具（按大小压缩/自动裁边/加边框） | `2141` | PIL 循环压缩 + `core.crop/border` | cv2 | 4 第三批 | 待迁移 |

## 2. 滤镜效果（G'MIC 归本类，Phase 5）

| 现有功能 | 旧入口 | processors | 外部依赖 | Phase | 状态 |
|---|---|---|---|---|---|
| G'MIC 滤镜库（命令行应用 + 帮助） | `1928` | `processors/gmic.py`（未走 backends/ 抽象，双轨之一） | **gmic** | 5 | 待迁移（收敛到 backends/） |

## 3. 图像创作（Phase 5）

| 现有功能 | 旧入口 | processors | 外部依赖 | Phase | 状态 |
|---|---|---|---|---|---|
| 渐变（线性/径向/网格预设） | `2869` | `gradients.linear/radial/mesh` + `MESH_PRESETS` | — | 5（Gradient Studio） | 待迁移 |
| 分形生成器（13 公式/超采样/着色） | `4342` | `fractal.render_fractal` 全家 | numba 可选 | 5（Fractal Studio） | 待迁移 |
| Texture Studio（噪声/图案/G'MIC 纹理/SDF raymarch、预设、缩略图缓存） | `app/panels/texture_studio.py:62` | `texture_studio.*`（自建线程池） | gmic 可选 | 5（Texture Studio） | 待迁移 |
| Shader Studio（GLSL 编辑/高亮/GL 预览/uniform 自动参数/导入导出） | `app/panels/shader_studio.py:97` | `shader_studio.*` | **glslangValidator** 可选 | 5（Shader Studio，真实图形会话验收） | 待迁移 |
| CPU Shader 快捷（invert/posterize/scanlines/vignette） | `3243` | `parity.shader_cpu` | — | 5 | 待迁移 |
| Photomosaic（≥10 素材） | `3273` | `parity.photomosaic` | — | 5 | 待迁移 |
| 多帧融合 | `3285` 附近 | `parity.multi_frame_fusion` | — | 5 | 待迁移 |
| SVG / WebP / JXL / APNG / GIF 帧 | `4111` | `parity.svg/webp/jxl/apng/gif-frames` + `media.convert_animation` | **ImageMagick、ffmpeg**（JXL 动画）；pillow-jxl | 5（SVG）/ 6（动画格式） | 待迁移 |
| 拼接/拼贴（横纵/网格/分割）+ 快速拼图 | `2910`、`4231` | `stitch.*` + `parity.contact-sheet/collage` | — | 5 | 待迁移 |
| 分割/堆叠/切割 | `3763` | `parity.split-grid/stack/cut` | — | 5 | 待迁移 |
| 形状蒙版 | `2643` | `shapes.apply_shape_mask` + `SHAPE_PRESETS` | — | 5 | 待迁移 |
| 绘图/标注（文字/边框/自动裁边/水印） | `3910` | `parity.text/border/auto-crop/watermark` | Pillow | 5（绘图与标注） | 待迁移 |
| 调色板/颜色库（提取/取色/替换/PDF） | `3832` | `parity.palette/color-sample/color-replace/palette-pdf` | reportlab（PDF） | 5 | 待迁移 |

## 4. 批量工具（Phase 5）

| 现有功能 | 旧入口 | processors | 外部依赖 | Phase | 状态 |
|---|---|---|---|---|---|
| 批量处理（目录扫描/滤镜链或转换/覆盖开关） | `2963` | `batch_filter_chain.run_batch_filter_chain`（含取消） | — | 5（Batch） | 待迁移 |
| 批量重命名（模板/预览/执行） | `3298` | `parity.batch_rename/apply_batch_rename`（`processors/batch.py:101` 未接 UI） | — | 5（Batch） | 待迁移 |
| 智能缩放（25 平台预设/自定义/按 KB） | `3139` | `batch.SOCIAL_PRESETS/smart_resize_by_size/resize_to_weight` | Pillow | 5（Batch） | 待迁移 |

## 5. 图像分析（Phase 6）

| 现有功能 | 旧入口 | processors | 外部依赖 | Phase | 状态 |
|---|---|---|---|---|---|
| 直方图（RGB/Luma/HSV，PIL 绘制） | `2673` | `histogram.*` | Pillow | 6（编辑器集成候选，Phase 4 评估） | 待迁移 |
| 图像比较（MAE/RMSE/PSNR/NCC/SSIM + 差异图） | `2740` | `compare.compare/difference_image` | scikit-image | 6 | 待迁移 |
| 文件校验和（MD5/SHA*/CRC32/Blake2） | `2788` | `checksum.all_hashes/file_hashes`（"xxhash"为自实现近似，注意） | — | 6 | 待迁移 |
| 查找（重复/相似/信息） | `4055` | `parity.duplicate-finder/similar/image-info` | Pillow | 6 | 待迁移 |
| EXIF（读取/按 Tag 编辑/删除） | `1518` | `parity.edit_exif`（PIL getexif） | Pillow | 6 | 待迁移 |

## 6. AI 工具（Phase 6）

| 现有功能 | 旧入口 | processors | 外部依赖 | Phase | 状态 |
|---|---|---|---|---|---|
| AI 抠图（4 模型/Alpha Matting/换底/人像虚化） | `2335` | `ai.remove_background/composite_on_bg/portrait_bokeh` | **rembg + onnxruntime** 可选 | 6 | 待迁移 |
| AI Upscale（2x-8x；Lanczos/Bicubic/AI） | `2412` | `ai.upscale_*`；AI 路径硬编码 `/usr/bin/upscayl*` | **upscayl** 外部程序 | 6 | 待迁移（upscayl 路径需可配置） |
| AI 降噪（NLM/双边/中值/小波） | `2467` | `ai.denoise_*` | cv2 | 6 | 待迁移 |
| AI 深度图（启发式/U²-Net/ISNet） | `2604` | `ai.depth_map/depth_map_rembg` | rembg 可选 | 6 | 待迁移 |
| AI 色彩化/风格化（纯 numpy 实现，非真 AI 模型） | `2501` | `ai.colorize_transfer/ai_enhance` | — | 6 | 待迁移（状态如实标注为算法模拟） |
| AI 模型管理器（安装/删除/后端切换） | `2539` | `ai_models.registry/install/uninstall/set_backend/detect_backends` | rembg 缓存目录 | 6 | 待迁移 |

## 7. 文件工具（Phase 6）

| 现有功能 | 旧入口 | processors | 外部依赖 | Phase | 状态 |
|---|---|---|---|---|---|
| 图片→PDF（A4/A3/Letter） | `1422` | PIL 直存 | Pillow | 6 | 待迁移 |
| PDF 高级（合并/拆分/旋转/删页/提取文本/加密） | `2033` | `pdf_tools.*` | pypdf；pdf2image 仅声明未使用（PDF→图未实现，UI 仅提示） | 6 | 待迁移（如实标注未实现项） |
| OCR（6 语言/4 布局） | `1601` | pytesseract 直调 + `parity.ocr_to_file` | **tesseract** | 6 | 待迁移 |
| 压缩/打包（ZIP） | `2111` | stdlib zipfile | — | 6 | 待迁移 |
| 加密/Base64（fernet 文件加密、编码解码） | `3686` | `parity.base64-*/encrypt/decrypt/archive` | cryptography | 6 | 待迁移 |
| 压缩实验室（JPEG/WebP 质量滑杆/按 KB/格式转换） | `3986` | `parity.compress/webp/weight-resize/convert` | Pillow | 6 | 待迁移 |
| 尺寸/体积缩放 | `4181` | `parity.limits-resize/weight-resize/convert` | Pillow | 6 | 待迁移 |
| 条形码/二维码（生成 QR/解码） | `2830` | `barcode.generate_qr/decode_qr` | qrcode、pyzbar 可选 | 6 | 待迁移 |
| 动画（GIF/WebP/APNG 合成与拆帧） | `1974` | `media.convert_animation/extract_frames` | **ImageMagick、ffmpeg** | 6 | 待迁移 |

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
- 已知未实现/降级项（迁移时必须保持真实标注）：PDF→图片（仅提示）、.cube LUT 加载
  （无 UI）、AI 色彩化（算法模拟非模型）、批量重命名 `processors/batch.py:101`
  （双实现未接 UI）、`checksum` 的 xxhash 为自实现近似。
