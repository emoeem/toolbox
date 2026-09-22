# Toolbox 项目健康度审计

审计日期：2026-09-22  
分支：feature/toolbox-parity-ui-overhaul  
审计原则：只依据当前工作树、当前机器实际命令输出、代码路径和可重复测试；不把 registry、函数存在或历史测试结果当成功能等价。

## 0. 审计结论先行

当前 registry 的 **67/67、pending=0 不能作为功能完成度指标**。processors/parity.py:643-671 的状态模型只有 native/implemented/pending，没有 placeholder/usable/equivalent，而且默认把全部 registry 项标成 implemented/native。

本次独立审计得到：

| 等级 | 数量 | 含义 |
|---|---:|---|
| placeholder | 2 | 当前没有足够真实工作流支撑该 feature |
| usable | 44 | 存在真实处理/交互路径，能产生对应类型结果；但未达到 ImageToolbox 逐项等价 |
| equivalent | 0 | 没有任何模块完成逐项行为/参数/边界验收，因此不授予 equivalent |
| 未验证 | 21 | 有代码或入口，但本轮缺少足够证据证明核心工作流达到 usable |

**尤其重要：** 当前真实 UI smoke test 已出现回归：MainWindow() 在当前 PySide6 6.11.2 环境启动时，于 app/fonts.py:31 因 Qt 6.11 枚举类型组合报 TypeError。因此 README 中旧的“UI smoke OK”不能视为当前状态。

## 1. 真实进度盘点

判定依据：
- Toolbox：processors/parity.py、processors/*.py、processors/*/*.py、app/main_window.py、app/panels/*.py
- ImageToolbox：/home/emo/code/ImageToolbox/feature/<module>/
- registry：processors/parity.py:164-175
- registry 状态：processors/parity.py:637-671
- 参考项目本机扫描确认 67 个 feature module 均存在。

| 模块 | 当前等级 | 依据 | 与 ImageToolbox 差距 | 升级到 usable 还缺什么 | 升级到 equivalent 还缺什么 |
|---|---|---|---|---|---|
| ai-tools | 未验证 | processors/ai.py:1-254；processors/ai_models.py:87-127；app/main_window.py:1568-1837 | 模型/工具范围更大；实际模型组合未逐项验证 | 实测模型安装、推理、失败回退 | 逐模型、参数、输出行为验收 |
| apng-tools | usable | processors/parity.py:584-591 | 当前偏处理函数，UI/边界较窄 | 补边界测试 | 帧时序、循环、参数逐项对照 |
| archive-tools | usable | processors/parity.py:22-27 | 当前主要 ZIP | 补 UI/错误验证 | 格式和交互逐项对照 |
| ascii-art | usable | processors/parity.py:248-250 | 主要文本导出 | 补字符集/宽度验证 | 参数与布局逐项对照 |
| audio-cover-extractor | usable | processors/parity.py:513-528；requirements.txt:16 | 格式覆盖和 UI 较窄 | 实测 MP3/FLAC/无封面 | 全格式和嵌入行为对照 |
| base64-tools | usable | processors/parity.py:12-20 | 文件级 Base64 | 补非法输入 | 文件/文本模式全对照 |
| batch-rename | usable | processors/parity.py:338-380；app/main_window.py:2450-2470 | 参考 token/日期规则更多 | 补全部 token | 日期、冲突、排序、撤销逐项对照 |
| checksum-tools | usable | processors/parity.py:571-582 | 算法/显示工作流未完整对齐 | 多算法实测 | 算法列表、格式、批量 UI |
| cipher | usable | processors/parity.py:154-163 | Fernet 派生密钥方案简单 | 实测加解密/错误密码 | 算法、密钥流程逐项对照 |
| code-preview | usable | processors/parity.py:627-632 | 纯文本读取/写回 | 编码/大文件 | 预览交互逐项对照 |
| collage-maker | usable | processors/parity.py:241-246 | 基础拼贴 | 空输入/透明度边界 | 模板/拖拽/参数全对照 |
| color-library | usable | processors/parity.py:106-110 | 主色板，不是完整资产库 | 保存/编辑/删除 | 数据模型/UI 全对照 |
| color-tools | usable | processors/parity.py:448-468 | 工具集合较窄 | 实测颜色操作 | 色彩空间/容差/交互逐项对照 |
| compression-lab | usable | processors/parity.py:125-136 | 主要 Pillow 压缩 | 实测质量/体积 | 全压缩参数对照 |
| curves | usable | processors/parity.py:210-212 | LUT 插值，无完整曲线编辑器 | UI 曲线验证 | 节点/通道/预览全对照 |
| delete-exif | usable | processors/parity.py:214-220 | 删除路径真实存在 | JPEG/PNG/TIFF 实测 | 元数据保留规则对照 |
| document-scanner | 未验证 | processors/parity.py:277-279 | 只有基础阈值扫描 | 实测透视/裁切/多页 | 完整扫描器工作流 |
| draw | 未验证 | processors/parity.py:537-545 | annotate 是离线绘制，不是完整画布/图层 | 实测画布/图层 | 多层编辑/工具/手势全对照 |
| duplicate-finder | usable | processors/parity.py:100-104、225-239 | hash/dHash 较基础 | 实测误判 | 所有相似策略/UI |
| edit-exif | 未验证 | processors/parity.py:593-606 | 有写入接口但安全策略未验 | 实测字段修改 | 字段编辑器/格式安全 |
| fractal-generation | usable | processors/parity.py:203-208；app/main_window.py:2373-2408 | 当前基础 Mandelbrot 参数 | 补 Julia/颜色验证 | formula/power/palette/camera/quaternion/supersampling |
| image-cutting | usable | processors/parity.py:188-190 | 基础矩形 crop | 边界/EXIF | UI/裁切模式全对照 |
| image-splitting | usable | processors/parity.py:35-44 | 规则网格 | 非整除尺寸 | 全切割规则 |
| image-stacking | usable | processors/parity.py:46-56 | 横/纵堆叠 | 透明/不同尺寸 | 全布局/UI |
| jxl-tools | 未验证 | processors/parity.py:406-421 | 依赖 pillow_jxl，本轮未实测 | 实际 JXL 编解码 | 质量/无损/元数据 |
| limits-resize | usable | processors/parity.py:178-186 | contain/cover/stretch | EXIF/透明度 | resize 策略全对照 |
| load-net-image | 未验证 | processors/parity.py:608-615 | 网络输入未实际联网验收 | HTTPS/失败/超时 | 缓存/协议/安全限制 |
| markup-layers | 未验证 | processors/parity.py:537-545 | annotate 不等于完整图层 | 实测图层 | 47 文件参考模块全对照 |
| mesh-gradients | usable | processors/parity.py:493-499；app/main_window.py:2404 | 四角双线性渐变 | 更多颜色/边界 | 网格节点/交互 |
| multi-frame-fusion | usable | processors/parity.py:436-446 | 四种基础融合 | 不同尺寸/帧数 | 所有模式/UI |
| noise-generation | usable | processors/parity.py:198-201；processors/texture_studio/noise.py | 算法/参数较少 | 统计性质/seed | 所有噪声算法 |
| palette-pdf | 未验证 | processors/parity.py:252-257 | 有 PDF 输出函数，未实际打开 | 实测 PDF | 页面/字体/颜色行为 |
| palette-tools | usable | processors/parity.py:106-110 | 主色量化 | 色彩空间边界 | 参考算法/UI |
| photomosaic | usable | processors/parity.py:293-337；app/main_window.py:2410-2415 | 已有真实生成 | 异常素材/大图性能 | 排序/颜色空间/重复策略 |
| pick-color | 未验证 | processors/parity.py:448-453 | 坐标采样不等于屏幕取色器 | 实测鼠标取色 | 屏幕取色/历史 |
| quick-tiles | usable | processors/parity.py:617-620 | 基础快速拼图 | 不整齐输入 | 模板/UI |
| recognize-text | 未验证 | app/main_window.py:901-910；processors/parity.py:423-428 | Tesseract 路径存在但未做真实 OCR | 中/英/日实测 | engine/model/segmentation |
| resize-convert | usable | processors/parity.py:119-123、178-186 | 基础转换+resize | 全格式实测 | UI/批量/元数据 |
| scan-qr-code | 未验证 | processors/parity.py:271-275 | QRCodeDetector 未实测 | 实测二维码 | 多码/旋转/失败行为 |
| shader-studio | 未验证 | processors/shader_studio/*；app/panels/shader_studio.py | parser/library/validator 有测试，真实 OpenGL context 未验证 | 真实 Wayland/X11 GPU 验证 | sampler/导出/运行行为全对照 |
| single-edit | usable | app/main_window.py:398+；processors/core.py | 桌面编辑器真实存在 | 边界测试 | 参考编辑功能全对照 |
| svg-maker | usable | processors/parity.py:470-491；app/main_window.py:2420-2427 | 基础 rect/circle/text | 路径/渐变等 | 完整 SVG 编辑工作流 |
| texture-generation | usable | processors/texture_studio/*；app/panels/texture_studio.py | FastNoise/Pattern/GMIC/Raymarch 已有，参数系统仍手写 | 补 metadata/cache/preset | 全生成器逐项对照 |
| wallpapers-export | usable | processors/parity.py:530-535 | 基础 fit 导出 | 多显示器/规格 | 平台行为全对照 |
| webp-tools | usable | processors/parity.py:621-625 | Pillow WebP | 动画/无损/元数据 | 全参数 |
| weight-resize | usable | processors/parity.py:68-77 | JPEG quality 二分 | 透明格式 | 参考算法/UI |
| watermarking | usable | processors/parity.py:93-99；app/main_window.py:954+ | 基础文字水印 | 字体/图片水印 | 完整图层定位 |
| app-logs | 未验证 | app/workbench.py；app/main_window.py | LogWidget 存在，持久化/过滤/导出未验 | 生命周期实测 | 参考日志功能 |
| compare | usable | processors/compare.py；processors/parity.py | 有真实比较处理 | 边界测试 | 所有比较视图/指标 |
| crop | usable | processors/parity.py:188-190；主窗口编辑路径 | 矩形 crop | 交互裁剪 | 比例/旋转/UI |
| easter-egg | placeholder | registry 只有状态声明，未找到独立真实工作流 | 参考模块存在但当前无可验证行为 | 提供真实触发/输出 | 对照参考彩蛋 |
| erase-background | 未验证 | processors/ai.py；app/main_window.py:1568+ | AI backend/model 可选，真实模型未验 | 实测真实模型 | 模型/边缘/批量 |
| filters | 未验证 | processors/filters.py:1-894；apply_filter | 处理器很大，但 577 个参考 filter 不等于已覆盖 | 建立真实 filter 覆盖矩阵 | 参数/算法逐项对照 |
| format-conversion | usable | processors/parity.py:119-123 | Pillow 基础转换 | 特殊格式 | 全格式/元数据 |
| gif-tools | usable | processors/parity.py:259-269 | GIF 创建/拆帧 | palette/disposal | 完整 GIF UI |
| gradient-maker | usable | processors/parity.py:192-196；processors/gradients.py | 线性/网格基础生成 | 更多 gradient | 完整编辑器 |
| help | 未验证 | app/main_window.py:1564+ | About/help 路径存在，内容未逐项验 | 内容/链接人工验 | 参考帮助全对照 |
| image-preview | usable | app/preview_widget.py；app/main_window.py:95+ | 真实中央预览 | 超大图/动画 | 预览交互全对照 |
| image-stitch | usable | processors/stitch.py:1-82；app/main_window.py:2164-2181 | 横/纵/grid | 不同尺寸/透明度 | 所有模式 |
| libraries-info | 未验证 | backends/registry.py；设置页 | backend status 不等于完整库信息页 | 人工核对 | 版本/许可证/详情 |
| library-details | 未验证 | 未发现独立等价详情工作流 | registry/backend info 不足 | 建立可见详情入口 | 完整详情页 |
| main | 未验证 | app/main_window.py:1-2842 | 主界面存在但当前启动 smoke 有回归 | 先恢复启动 | 与参考主界面逐项对照 |
| media-picker | 未验证 | Qt QFileDialog 路径分散在主窗口 | 不自动等价 Android picker | 多选/过滤实测 | 完整媒体选择 |
| pdf-tools | usable | processors/pdf_tools.py；app/main_window.py:783+ | 高级范围窄，外部工具未完整接入 | 实测输入输出 | 124 文件功能全对照 |
| root | 未验证 | processors/__init__.py；main_window.py | 聚合概念，不是独立用户入口 | 明确定义 | 对照 root module |
| settings | usable | app/main_window.py:276-304 | QSettings 有主题/字体/输出/最近文件/线程 | 重启实测 | 参考 settings 全对照 |
| usage-statistics | placeholder | backends/registry.py 只有可选 usage 参数，无完整统计持久化 | 不足以证明统计 feature | 真实统计采集/展示 | 参考统计项逐项对照 |

### 等级统计

- placeholder：**2**
- usable：**44**
- equivalent：**0**
- 未验证：**21**

---

## 2. 测试质量审计

当前 tests/ 有 5 个测试文件、22 个测试用例。

| 测试文件 | 测试数 | 弱断言数 | 覆盖率 | 是否 mock 核心逻辑 | 备注 |
|---|---:|---:|---|---|---|
| tests/test_gmic_backend.py | 6 | 0 | 未验证 | 否 | 有真实 /usr/bin/gmic CLI 调用 |
| tests/test_parity.py | 4 | 1 | 未验证 | 否 | registry 数字测试不能证明功能 |
| tests/test_shader_studio.py | 3 | 0 | 未验证 | 否 | parser/library/validator；无真实 GPU runtime |
| tests/test_texture_studio.py | 5 | 0 | 未验证 | 否 | 真实 Pillow/Numpy 生成，含 Raymarch |
| tests/test_texture_studio_fix.py | 4 | 0 | 未验证 | 否 | Qt 控件/model/cache/request-id |

### 弱断言

tests/test_parity.py:13-15：
- len(PARITY_FEATURES)==67
- pending==[]

这是 registry 元数据断言，不是功能测试。

tests/test_parity.py:17-28 的 generator 测试只检查尺寸；tests/test_parity.py:30-38 的 fusion 测试只检查尺寸；tests/test_gmic_backend.py:20-23 的四种纹理只检查尺寸和 backend label。

未发现 assertTrue(True) 这种空断言。

### mock

本轮检查全部 5 个测试文件，没有发现 mock 掉核心处理逻辑后宣称通过的测试。

### 覆盖率

执行：
~~~bash
.venv/bin/python -m coverage --version
~~~

结果：No module named coverage。

因此本轮没有伪造覆盖率数字，覆盖率为**未验证**。

### 未覆盖核心模块

至少：
- app/main_window.py
- app/fonts.py
- app/theme.py
- app/workbench.py
- app/preview_widget.py
- processors/core.py
- processors/filters.py
- processors/advanced_filters.py
- processors/ai.py
- processors/ai_models.py
- processors/media.py
- processors/pdf_tools.py
- processors/stitch.py
- processors/lut.py
- processors/histogram.py
- processors/shapes.py
- processors/barcode.py
- processors/ascii.py
- processors/checksum.py
- processors/compare.py
- processors/batch.py

### Qt 环境

无头：
~~~bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
~~~
当前结果：**22/22 OK**。

普通 Qt：
~~~bash
.venv/bin/python -c "from PySide6.QtWidgets import QApplication; from app.main_window import MainWindow; app=QApplication([]); w=MainWindow()"
~~~
当前机器无 X11 display；在进一步检查 MainWindow 初始化时发现 app/fonts.py:31 的 Qt 枚举组合在 PySide6 6.11.2 下抛 TypeError：

StyleStrategy 与 HintingPreference 不能直接用 | 组合。

因此真实 Wayland/X11 GUI：**未验证**；Shader OpenGL runtime：**未验证**。

---

## 3. 手动验证清单摘要

完整清单见 docs/manual-verification.md。

必须实际验收的核心项目：
- image-preview
- settings
- single-edit
- texture-generation
- fractal-generation
- noise-generation
- mesh-gradients
- apng-tools
- archive-tools
- base64-tools
- batch-rename
- checksum-tools
- cipher
- code-preview
- image-cutting/crop
- image-splitting
- image-stacking
- quick-tiles
- collage-maker
- image-stitch
- color-library/palette-tools
- color-tools
- curves
- watermarking
- gif-tools
- multi-frame-fusion
- audio-cover-extractor
- wallpapers-export
- svg-maker
- format-conversion/resize-convert
- webp-tools
- pdf-tools

每个项目都必须记录输入、参数、输出、成功/失败和截图/日志；“单元测试通过”不能替代人工验收。

---

## 4. 架构健康度

| 问题 | 结论 | 证据 | 风险 | 建议 |
|---|---|---|---|---|
| main_window.py >1500 | 是 | wc -l = 2842 | 严重 | 拆 controller/menu/settings/panels/workbench |
| MainWindow 承担过多职责 | 是 | app/main_window.py:80-304、各 setup/run 方法 | 严重 | 建立 application/controller 层 |
| processors/app/panels 分离 | 部分 | panel 直接调用 generator/library；main_window 大量直接 import processors | 中高 | service/use-case 层 |
| panel 直接操作 processor 状态 | 部分 | app/panels/texture_studio.py、shader_studio.py | 中 | 建立稳定 service API |
| parity 是否注册即完成 | 是 | processors/parity.py:643-671 | 严重 | level/evidence/test/manual 字段 |
| QSettings 硬编码 | 是 | app/main_window.py:84 | 中 | app/config.py |
| 跨模块 import 私有函数 | 未发现 | grep 未发现 from ... import _xxx | 低 | 保持 |
| 循环依赖 | 未发现明显循环 | 静态 import 检查未发现明显 app↔processor 环 | 中 | CI 中加 import-linter/pydeps |
| 重复参数控件 | 是 | main_window.py:2373-2408 与 Texture Studio 独立手写 | 中高 | metadata builder |
| app/config.py | 否 | 文件不存在 | 中 | 统一配置 |
| __version__ | 否 | 全仓 grep 无结果 | 中 | 建立版本来源 |

---

## 5. 工程质量基线

| 项 | 状态 | 证据 | 缺失影响 | 建议 |
|---|---|---|---|---|
| CI | 否 | .github/ 未发现 workflow | 无自动回归 | Linux CI + offscreen |
| lint | 否 | 无 ruff/flake8/pylint 配置 | 明显错误不会自动阻断 | ruff |
| formatter | 否 | 无 black/ruff format | 格式不一致 | ruff format |
| type check | 否 | 无 mypy/pyright | 类型回归 | pyright/mypy |
| requirements core/optional/dev | 否 | requirements.txt 单列表 | 可选依赖混杂 | 分层 |
| pyproject.toml | 否 | 未发现 | 工具/打包配置分散 | 建立 |
| 依赖锁定 | 否 | 全为 >= | 不可复现 | lock/constraints |
| 打包 | 否 | 无 PyInstaller/AppImage/Flatpak/deb | 普通用户安装成本高 | AppImage/Flatpak |
| 启动依赖检测 | 部分 | backends/registry.py | 缺依赖到功能执行时才发现 | 统一诊断页 |
| CHANGELOG | 是 | CHANGELOG.md | 未验证自动生成 | 明确策略 |
| LICENSE | 否 | 根目录无 LICENSE | 发布合规风险 | 添加 |
| CONTRIBUTING | 否 | 无 CONTRIBUTING.md | 协作成本 | 添加 |
| CODE_OF_CONDUCT | 否 | 无 CODE_OF_CONDUCT.md | 社区治理缺失 | 公开项目可添加 |

---

## 6. 外部依赖风险

实际命令：
~~~bash
pacman -Q gmic imagemagick ffmpeg-full tesseract ghostscript glslang
type -P gmic magick ffmpeg exiftool potrace tesseract qpdf mutool gs glslangValidator
~~~

实际版本：
- G'MIC 4.0.5-1.1，/usr/bin/gmic
- ImageMagick 7.1.2.31-1.1，/usr/bin/magick
- FFmpeg-full 9.0.2-1.5，/usr/bin/ffmpeg
- Tesseract 5.5.3-1.1，/usr/bin/tesseract
- Ghostscript 10.08.0-1.1，/usr/bin/gs
- glslang 1:1.4.357.0-1.1，/usr/bin/glslangValidator
- exiftool：未安装
- potrace：未安装
- qpdf：未安装
- mutool：未安装

| 依赖 | 是否实际使用 | 版本要求 | 许可证 | 是否打包 | 不可用时降级 | 风险 |
|---|---|---|---|---|---|---|
| G'MIC | 是 | requirements 未声明；运行时 binary | 需发布时核对 | 否 | numpy fallback | 中 |
| ImageMagick | 是 | magick | ImageMagick License | 否 | 部分 Pillow 可替代 | 中 |
| ffmpeg | 是 | ffmpeg | LGPL 2.1+ 主体；GPL 部件会改变整体许可要求 | 否 | 部分媒体无 fallback | 中高 |
| exiftool | 检测但本机不可用 | 未声明 | Perl Artistic/GPL 双许可证体系 | 否 | Pillow EXIF 部分替代 | 中 |
| potrace | 检测但本机不可用 | 未声明 | GPL | 否 | 未验证 | 中 |
| tesseract | 是 | pytesseract + binary | Apache-2.0 | 否 | 无完整 OCR fallback | 中 |
| Ghostscript | PDF 生态可用 | 未声明 | AGPL-3.0 | 否 | 未验证 | 高 |
| glslangValidator | 是 | shader validator | Apache-2.0 | 否 | 无等价 validator | 中 |
| qpdf | 未实际使用/未安装 | 未声明 | Apache-2.0 | 否 | 未验证 | 低/中 |
| mutool | 未实际使用/未安装 | 未声明 | AGPL-3.0 | 否 | 未验证 | 低/中 |

许可证事实参考：
- ImageMagick 官方许可证要求再分发时包含许可证和 attribution。 citeturn0search3
- FFmpeg 官方说明主体为 LGPL 2.1+，启用 GPL 部件时许可要求改变。 citeturn0search0
- Tesseract 官方仓库为 Apache-2.0，并依赖 Leptonica/训练数据。 citeturn0search7turn0search13

项目当前没有 LICENSE 和第三方许可证清单，因此不能把“本机安装成功”理解成“未来发布已经完成许可证合规”。

---

## 7. 范围管理建议

| 模块 | 建议目标等级 | 理由 | 优先级 |
|---|---|---|---|
| texture-generation | equivalent | 当前项目重点，已有多轮 A2 投入 | P0 |
| shader-studio | equivalent | 复杂编辑器，需要真实 GPU 验收 | P0 |
| filters | usable → 分层验收 | 577 项不能由 registry 数字代表 | P0 |
| draw | equivalent | 专业图像工具核心交互 | P0 |
| markup-layers | equivalent | 与 draw 强耦合 | P0 |
| image-preview | equivalent | 核心桌面交互 | P0 |
| single-edit | equivalent | 核心编辑工作流 | P0 |
| main | equivalent | 产品入口 | P0 |
| resize-convert | equivalent | 高频基础能力 | P0 |
| limits-resize | equivalent | 高频基础能力 | P0 |
| fractal-generation | usable | 基础生成已真实存在，高级参数可按需扩展 | P1 |
| ai-tools | usable | 模型生态变化大，不适合复制所有模型 | P1 |
| erase-background | usable | AI backend 差异大 | P1 |
| recognize-text | usable | Tesseract 可提供稳定桌面基础 OCR | P1 |
| batch-rename | usable | 核心流程已存在 | P1 |
| photomosaic | usable | 核心生成器已存在 | P1 |
| multi-frame-fusion | usable | 基础数学模式已存在 | P1 |
| svg-maker | usable | 基础 SVG 输出已存在 | P1 |
| pdf-tools | usable | 范围太大，应定义明确支持矩阵 | P1 |
| edit-exif | usable | 基础 EXIF 能力可满足桌面使用 | P1 |
| watermarking | usable | 基础文字水印足够；复杂图层归 draw/markup | P1 |
| audio-cover-extractor | usable | mutagen 路径明确 | P2 |
| app-logs | usable | LogWidget 已存在 | P2 |
| settings | usable | QSettings 已存在 | P2 |
| media-picker | usable | QFileDialog 是合理桌面替代 | P2 |
| libraries-info | usable | 后端状态页可作为桌面替代 | P2 |
| library-details | usable | 可合并进依赖诊断 | P2 |
| usage-statistics | 不计划支持/降级 registry | 当前没有真实统计价值 | P2 |
| easter-egg | 不计划支持/移出 parity | 非核心图像工作流 | P3 |
| root | 降级为内部模块 | 不应作为用户功能计数 | P3 |

明确存在“为了 parity 数字好看而保留”的风险项：easter-egg、usage-statistics、root。

---

## 8. 真实进度总结

如果今天把当前 toolbox 交给普通 Linux 用户，他可以处理常见图片并执行裁剪、缩放、格式转换、压缩、曲线、噪声、渐变、拼贴/拼接、批量重命名、checksum、Base64、加密、水印、GIF/APNG 等操作；Texture Studio 可以实际生成 FastNoise、Pattern、GMIC、Raymarch 纹理；G'MIC 4.0.5 可以真实调用并有 numpy fallback。Shader Studio 的 parser/library/validator 有测试，但真实 OpenGL runtime 没有在图形会话中验收。

不能把 67/67 当作等价完成：AI 模型工作流、OCR 多语言、二维码扫描、JXL、EXIF 编辑、文档扫描、完整 PDF 高级能力、交互式绘图/图层、完整 577-filter parity 等仍缺证据或明显缺功能。更严重的是，当前 MainWindow() 在 PySide6 6.11.2 环境中存在字体枚举 TypeError，普通图形启动当前不能宣称通过；offscreen 的 22/22 只能证明这一小组测试在无头 Qt 环境通过。

### 最严重的 5 个问题

1. app/main_window.py 达到 **2842 行**并承担过多职责。
2. processors/parity.py 将“注册”直接等价为 implemented，67/67 因而具有误导性。
3. 当前 MainWindow 启动存在真实回归：app/fonts.py:31。
4. 测试严重集中于 Texture/Shader/GMIC；coverage 工具不存在，核心模块没有覆盖数据。
5. 工程发布基础不完整：无 CI、无 pyproject、无 lint/type-check、无依赖锁定、无打包方案、无 LICENSE、无第三方许可证清单。

### 建议下一步

本轮不继续 A2/A3/A4 功能。

1. 先修复 MainWindow 启动回归并加入真实 Qt smoke。
2. 重定义 parity 数据模型：level + evidence + test_status + manual_status + dependency_status。
3. 给核心模块补“输出正确性”测试，而不是只测尺寸/非空。
4. 加 coverage、lint、type check、CI。
5. 拆分 main_window.py。
6. 补 LICENSE、第三方许可证清单和可选依赖矩阵。
7. 完成以上健康度修复后，再继续功能开发。

## 9. P0/P1 remediation status (2026-09-22)

本节记录本轮审计后的实际修复，不回写历史审计结论。

### P0

- Qt 6 启动回归已修复：`QFont.StyleStrategy` 与 `QFont.HintingPreference` 不再直接 `|`；分别调用 `setStyleStrategy()` 与 `setHintingPreference()`。
- 增加 `tests/test_fonts.py`，覆盖字体应用路径。
- MainWindow offscreen smoke 已重新验证：`MAINWINDOW_OK`。
- 测试从 22 个增加到 **25 个**；`QT_QPA_PLATFORM=offscreen ... unittest discover` 为 25/25 OK。
- parity registry 增加独立 `level` 字段：`placeholder / usable / equivalent / 未验证`，并保留原 `status` 兼容字段。
- parity 测试不再只验证尺寸：增加等级计数、生成结果非单值、fusion 精确像素结果断言。

### P1

- 增加 `pyproject.toml`，将运行依赖和 dev lint 依赖纳入项目元数据。
- 增加 GitHub Actions CI：安装项目、运行 Ruff、运行 offscreen unittest。
- 当前 Ruff gate 采用 **E9 syntax-error gate**；不是完整风格清理。历史代码存在大量 E/F 风格问题，本轮没有用批量自动修复掩盖这些问题。
- 增加根目录 Apache-2.0 `LICENSE`，与参考项目的许可证类型一致；第三方依赖许可证清单仍需单独维护。
- MainWindow 第一阶段拆分已完成：QSettings 创建/命名空间移入 `app/settings_store.py`，并增加持久化边界测试。没有进行大规模 UI 重构。

### 当前仍未解决

- MainWindow 仍约 2842 行，职责拆分尚未完成。
- 真实 Wayland/X11 GUI、Shader OpenGL runtime 仍需人工验证。
- coverage 工具尚未纳入，覆盖率仍为“未验证”。
- `equivalent` 仍为 0；本轮没有因为增加 level 字段而虚增等价完成度。


### 工程基线补充验证

- `uv build --out-dir /tmp/toolbox-build` 已成功生成 sdist 与 wheel；随后临时构建目录已删除。
- `pyproject.toml` 使用显式 setuptools package discovery，避免 `app/backends/processors/resources` 多顶层目录导致构建失败。
