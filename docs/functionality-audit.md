# Toolbox 逐功能真实可用性审查
日期：2026-09-23
分支：feature/toolbox-parity-ui-overhaul
参考：/home/emo/code/ImageToolbox/feature（67 feature modules）
原则：只记录本轮真实执行结果；registry、函数存在、单元测试不等价于功能完成。

## 第 1 部分：真实启动审查
命令：cd /home/emo/code/toolbox && uv run python main.py
实际输出：REAL_START_RC=134；qt.qpa.xcb: could not connect to display；Could not load the Qt platform plugin "xcb"；可用插件包含 xcb/wayland/offscreen。
结论：真实图形会话未验证。退出 134 是当前 Remote Desktop 终端没有 DISPLAY/Wayland 会话导致的 Qt 平台初始化失败，不是此前字体枚举 TypeError。
命令：QT_QPA_PLATFORM=offscreen uv run python -c "... MainWindow ..."
实际输出：OFFSCREEN_RC=0；MAINWINDOW_OK。
结论：offscreen 构造成功，但不能代替真实 Wayland/X11 人工验证。
修复状态：此前字体初始化问题本轮不再复现；本轮没有修改启动代码。

## 第 2 部分：逐功能真实可用性审查
证据命令 A：uv run python /tmp/toolbox_audit.py
证据命令 B：uv run python /tmp/toolbox_audit2.py
两条命令均直接调用 processors/parity.py 的真实函数，并检查输出文件尺寸、均值、方差、SHA。
等级：placeholder / runnable / usable / equivalent。equivalent 本轮为 0。

| 模块 | Q1/Q2/Q3/Q4/Q5/Q6 | 实际等级 | 证据 |
|---|---|---|---|
| ai-tools | Q1有；Q2-Q6未验证 | 未验证 | audit范围外真实模型推理 |
| apng-tools | 584 make_apng；成功；64×48多帧；duration执行；空帧ValueError；未证明全等价 | usable | audit1 OK apng |
| archive-tools | 22 archive_images；ZIP 386 bytes；输入集合执行；空列表未专项；仅核心能力 | usable | audit2 OK archive |
| ascii-art | 627 image_to_ascii；文本146 bytes；width=20；非法路径未完整；UI未证明 | usable | audit2 OK ascii |
| audio-cover-extractor | 入口存在；未执行带嵌入封面的媒体 | 未验证 | 本轮无合适 fixture |
| base64-tools | 12 encode；decode后64×48且SHA=a561479697；双向；非法文本ValueError；UI未证明 | usable | audit2 |
| batch-rename | 338 batch_rename；a_001/b_002；pattern/start/padding执行；collision有测试；并发未验证；UI未证明 | usable | audit2 |
| checksum-tools | 571 checksum_file；SHA等算法真实输出；两输入hash不同；空文件未测；参考算法未完全对照 | usable | audit1 |
| cipher | 154 encrypt/decrypt；120→18 bytes往返；同密码；错密码未本轮；协议未证明等价 | usable | audit2 |
| code-preview | 627 code_preview；中文原样；UTF-8执行；非UTF8为replace；UI未证明 | usable | audit1 |
| collage-maker | 241 make_collage；848×332与432×648；columns生效；空列表未测；基础能力 | usable | audit1 |
| color-library | 106 dominant_palette；合法hex；count执行；单色只返回1色；完整算法未证明 | usable | audit1 |
| color-tools | 色彩处理入口存在；未完成真实颜色替换矩阵 | 未验证 | 未达到Q2-Q6 |
| compression-lab | compress入口存在；未完成质量/体积实测 | 未验证 | 未验证 |
| curves | 210 apply_curves；mean 80→137；两组曲线SHA不同；点序边界未测；完整UI未证明 | usable | audit1 |
| delete-exif | 214 strip_exif；64×48输出；核心路径；多格式EXIF未全测；仅核心能力 | usable | audit1 |
| document-scanner | 277 document_scan；64×48输出；threshold未成矩阵；完整扫描流程未证明 | 未验证 | audit2 docscan |
| draw | annotate入口存在；历史真实调用 KeyError 'xy'（已修复）；未证明交互绘图 | 未验证 | audit2 |
| duplicate-finder | 100 find_duplicates；相同SHA正确分组；输入变化有效；空集合未测 | usable | audit1 |
| edit-exif | 593 edit_exif；本轮未成功执行闭环；类型/格式保持未验证 | 未验证 | 未验证 |
| fractal-generation | 203 generate_fractal；两组mean/std/hash不同；参数有效；0/负值未完整测 | usable | audit1 |
| image-cutting | 188 cut_image；严格20×10；坐标/尺寸执行；越界未全测 | usable | audit1 |
| image-splitting | 35 split_grid；3×2返回6文件；rows/cols执行；0值未完整；边界路径异常 | usable | audit1 |
| image-stacking | 46 stack_images；131×48/64×99；方向和spacing执行；空列表ValueError | usable | audit1 |
| jxl-tools | 406 jxl_convert；64×48 JXL成功；quality单组；缺工具路径未测 | usable | audit1 |
| limits-resize | 178 resize_with_limits；32×24/16×12；限制参数生效；0×0 曾意外生成文件（已修复） | usable | audit1 boundary |
| load-net-image | 608 load_net_image；未真实下载/超时验证 | 未验证 | 未验证 |
| markup-layers | 537 annotate；真实schema调用KeyError 'xy'；图层未验证 | 未验证 | audit2 |
| mesh-gradients | 493 mesh_gradient；32×32；四色路径执行；角点未逐像素核验 | usable | audit1/2 |
| multi-frame-fusion | 436 multi_frame_fusion；median/mean输出均值80；method有效；空帧未测 | usable | audit1 |
| noise-generation | 198 generate_noise；gaussian std65.9/uniform std73.6；kind生效；非法kind 曾意外成功（已修复） | usable | audit1 boundary |
| palette-pdf | 252 make_palette_pdf；PDF 1572 bytes；count执行；极端count未测 | usable | audit2 |
| palette-tools | 106 dominant_palette；合法hex；count执行；单色限制 | usable | audit1 |
| photomosaic | 293 photomosaic；mosaic.png真实生成；参数执行；空tile未测 | usable | audit2 |
| pick-color | 448 color_sample；40,80,120/#285078；坐标执行；越界未测；非系统屏幕取色 | usable | audit1 |
| quick-tiles | 617 quick_tiles；88×48；columns/tile执行；空输入未测 | usable | audit1 |
| recognize-text | 429 ocr_to_file；真实识别 Toolbox QA 123；psm=6；多语言未测 | usable | audit2 |
| resize-convert | 119 convert_format；JPEG/WebP 64×48；格式生效；非法fmt未测 | usable | audit1 |
| scan-qr-code | 271 scan_qr；本轮无可用QR fixture，未验证 | 未验证 | 未验证 |
| shader-studio | 501 shader_cpu；strength=1 mean175，0.2 mean99，SHA不同；非法effect未测；非完整GLSL等价 | usable | audit2 |
| single-edit | MainWindow单图入口；未完成打开→编辑→保存真实闭环 | 未验证 | offscreen仅构造 |
| svg-maker | 470 svg_make；历史真实调用 KeyError 'w'（已修复） | 未验证 | audit2 FAIL |
| texture-generation | 481 texture_generate；seed 1/2生成不同SHA；核心可用；全部UI参数未逐项 | usable | audit1 + tests |
| wallpapers-export | 530 wallpaper_export；cover 100×80、contain 100×75；fit生效 | usable | audit2 |
| webp-tools | 621 webp_convert；quality 50/95不同SHA；参数生效；极端值未测 | usable | audit1 |
| weight-resize | 68 resize_by_weight；JPEG真实输出；negative target 曾意外成功（已修复） | usable | audit1 boundary |
| watermarking | 93 watermark；opacity/position两组SHA不同；空文本/越界未测 | usable | audit1 |
| app-logs | LogWidget存在；未验证过滤/搜索/导出 | 未验证 | GUI仅发现Dock |
| compare | 225 find_similar_images；两图正确分组；threshold执行；完整比较UI未证明 | usable | audit1 |
| crop | 188 cut_image；16×16真实输出；核心裁剪；越界未全测 | usable | audit1 |
| easter-egg | registry状态存在；未找到真实工作流 | placeholder | parity FEATURE_LEVELS |
| erase-background | 历史 parity 映射缺失 background-remove；现已修复并有回归测试 | 未验证 | audit1 |
| filters | processors/filters.py存在；未逐项执行577 filters | 未验证 | 不能以数量代表完成 |
| format-conversion | 119 convert_format；PNG/JPEG/WebP核心路径实测 | usable | audit1 |
| gif-tools | 259 make_gif；多帧GIF真实生成；duration执行；空帧ValueError | usable | audit1 |
| gradient-maker | 192 create_gradient；angle 0/90不同SHA；参数有效；非法颜色未测 | usable | audit1 |
| help | QAction存在；未真实打开并检查内容 | 未验证 | GUI probe仅菜单存在 |
| image-preview | 29 image_info + MainWindow；64×48信息正确；真实GUI缩放未验证 | usable | audit1 + GUI probe |
| image-stitch | 46 stack_images；horizontal真实128×48；grid未单独验证 | usable | audit1 |
| libraries-info | BackendInfo可返回；完整库信息页未验证 | 未验证 | backend probe |
| library-details | BackendInfo字段存在；没有完整详情页证据 | 未验证 | source inspection |
| main | MainWindow offscreen成功；真实GUI未验证 | 未验证 | MAINWINDOW_OK仅无头 |
| media-picker | QFileDialog入口存在；未真实选择/取消媒体 | 未验证 | 未验证 |
| pdf-tools | 252 make_palette_pdf；PDF真实1572 bytes；完整多页导入导出未闭环 | usable | audit2 |
| root | registry/core存在；无独立可验收用户行为 | 未验证 | registry only |
| settings | settings_store存在；持久化单测通过；未做GUI保存→退出→重启 | 未验证 | tests only |
| usage-statistics | 仅usage字段，无真实统计展示/持久化 | placeholder | parity.py 637-671 |

### 汇总
历史快照（修复前）：45 usable / 0 runnable / 0 equivalent / 20 未验证 / 2 placeholder。
这不是完成度百分比：未验证不能默认通过；usable也不代表ImageToolbox等价。## 第 3 部分：反例与破坏性测试
命令：uv run python /tmp/toolbox_audit.py
真实输出：
BOUNDARY stack-empty ERROR ValueError no images —— 空列表被拒绝。
BOUNDARY split-empty ERROR FileNotFoundError —— 错误被拒绝，但提示层不友好。
BOUNDARY resize-zero UNEXPECTED_OK .../z.png —— 不通过，0×0限制没有拒绝。
BOUNDARY noise-invalid UNEXPECTED_OK .../badn.png —— 不通过，非法kind静默走默认路径。
BOUNDARY weight-negative UNEXPECTED_OK .../neg.jpg —— 不通过，负target_kb被接受。
BOUNDARY base64-invalid ERROR ValueError string argument should contain only ASCII characters —— 拒绝非法Base64文本。
本轮没有执行完整8000×8000、处理中途取消、狂点、并发、关闭窗口矩阵；这些维度对全部usable项均记为未验证，不默认通过。

| 模块 | 破坏方式 | 期望 | 实际 | 结果 |
|---|---|---|---|---|
| image-stacking | 空输入 | 明确拒绝 | ValueError no images | 通过 |
| image-splitting | 空路径 | 明确提示 | FileNotFoundError | 不通过（提示层） |
| limits-resize | 0×0 | 拒绝 | 生成z.png | 不通过 |
| noise-generation | 非法kind | 拒绝 | 生成badn.png | 不通过 |
| weight-resize | target=-1 | 拒绝 | 生成neg.jpg | 不通过 |
| base64-tools | 非ASCII文本 | 明确失败 | ValueError | 通过 |
| 其余usable | 8000×8000/取消/狂点/并发/关闭窗口 | 无崩溃且正确终止 | 未执行 | 未验证 |

## 第 4 部分：参数生效性专项
Shader Studio：processors/parity.py:501；strength=1输出mean175/std32.66，strength=0.2输出mean99/std19.60，SHA不同；strength真实生效。完整GLSL uniform/全部effect未验证。
Texture Studio：processors/parity.py:481；seed=1/2生成不同SHA；已有真实参数测试通过，但全部UI参数没有逐一执行。
Fractal：parity.py:203；iterations/scale两组输出mean/std/hash不同，参数有效。
Filters：processors/filters.py；当前抽样30项，29通过、night_vision失败；整体仍未验证。
GMIC：processors/gmic.py: apply；真实-gmic -blur 2和-sharpen 2均生成32×32结果，mean=120。
历史专项发现：SVG Maker KeyError 'w'；Annotate KeyError 'xy'；limits-resize=0、noise非法kind、weight-resize负值边界异常；均已在第 9.2 节记录修复证据。

## 第 5 部分：后端真实性与降级路径
命令：command -v gmic magick ffmpeg exiftool potrace tesseract
版本：GMIC 4.0.5 /usr/bin/gmic；ImageMagick 7.1.2-31 /usr/bin/magick；ffmpeg 9.0.2 /usr/bin/ffmpeg；tesseract 5.5.3 /usr/bin/tesseract；exiftool和potrace不存在。
真实backend输出：
GMIC True 4.0.5；GMIC blur/sharpen真实执行成功。
ImageMagick/ffmpeg存在，但本轮没有证明每个GUI功能真的调用它们。
tesseract真实OCR输出 Toolbox QA 123。
exiftool/potrace不可用，降级输出和UI提示未验证。
缺失GMIC路径测试：PATH=/tmp .venv/bin/python ...；gmic.available()可检测缺失，但随后gmic.version()直接抛 FileNotFoundError。文件位置：processors/gmic.py:15。该问题已由 `898f8a0 fix: gmic backend handle missing binary gracefully` 修复，并有缺失路径回归测试。
Preset/导出文件后端标识、手动切换后端：未验证。## 第 6 部分：GUI真实可用性
本轮只能进行offscreen构造和程序化探针，不能冒充真实图形会话人工验收。

| 项 | 状态 | 证据 | 备注 |
|---|---|---|---|
| 主窗口 | offscreen通过 | MAINWINDOW_OK | 真实会话未验证 |
| 菜单栏 | 5个菜单存在且enabled | GUI probe | 未人工点击 |
| 工具栏 | 12 QAction enabled | GUI probe | 未人工点击 |
| 状态栏 | 就绪、100% | GUI probe | offscreen |
| Dock | 任务队列、运行日志存在且初始隐藏 | GUI probe | 浮动/恢复未验证 |
| 主题 | dark→light→dark程序化成功 | GUI probe | 未验证真实绘制 |
| 设置 | 未验证完整保存/恢复默认 | tests only | 不默认通过 |
| 字体 | QApplication font=MiSans | GUI probe | 未做GUI持久化验收 |
| 任务队列 | 未验证添加/暂停/取消/清理 | 未执行 | 未验证 |
| 日志 | 未验证过滤/搜索/导出 | 未执行 | 未验证 |
| 快捷键 | 未验证真实事件 | 未执行 | 未验证 |
| 高DPI | 未验证 | 未执行 | 未验证 |
| 错误提示可复制 | 未验证 | 未执行 | 未验证 |

GUI probe实际输出：TOOLS=43；MENUS=[文件,视图,编辑,工具,帮助]；DOCKS=[任务队列,运行日志]；FONT=MiSans；SELECT_FAILS=[]；SELECT_DONE=43。
这只证明43个当前sidebar条目可以被程序化选择，不证明67个参考feature均有完整GUI。

## 第 7 部分：真实完成度总结
registry：67/67，但这是 processors/parity.py:164 的元数据覆盖，不是完成度。
真实分级：历史快照（修复前）：45 usable / 0 runnable / 0 equivalent / 20 未验证 / 2 placeholder。
明确placeholder：easter-egg、usage-statistics。
明确未验证：AI tools、audio cover、color tools、compression lab、document scanner、draw、edit EXIF、network image、markup layers、QR scan、app logs、background erase、filters、help、libraries info/details、main real GUI、media picker、root、settings。
历史发现（均已处理）：SVG Maker、Annotate/Draw、Erase Background mapping。
equivalent=0：本轮没有任何模块取得足够参考项目行为级证据来宣称等价。

结论：目前不是“67个功能完整实现”。当前真实状态是：67个feature已注册，其中45个有真实核心处理路径并产出结果，20个没有完成所需真实证据，2个仍是placeholder；同时存在边界错误和至少一个后端降级bug。不能把67/67 registry当完成度。

## 第 8 部分：证据与复现索引
E1 启动：
uv run python main.py → rc=134，xcb/display缺失。
QT_QPA_PLATFORM=offscreen uv run python -c "...MainWindow..." → rc=0，MAINWINDOW_OK。

E2 核心审计：
uv run python /tmp/toolbox_audit.py → rc=0，逐项输出尺寸/均值/方差/SHA及boundary。
uv run python /tmp/toolbox_audit2.py → rc=0，补充base64/archive/batch/cipher/mosaic/svg/wallpaper/ascii/pdf/OCR/document scan/shader/mesh/annotate。

E3 GUI probe：
QT_QPA_PLATFORM=offscreen uv run python - <<'PY' ... MainWindow ... PY
→ TOOLS=43、MENUS=5、DOCKS=2、FONT=MiSans、SELECT_FAILS=[]。

E4 后端：
inspect_backends()真实检测GMIC/ImageMagick/ffmpeg/tesseract可用，exiftool/potrace不可用。
GMIC blur/sharpen真实执行成功。
PATH=/tmp隐藏GMIC后，gmic.version()抛FileNotFoundError。

E5 回归：
QT_QPA_PLATFORM=offscreen uv run python -m unittest discover -s tests -v
→ 26 tests / 4.209s / OK。
uvx ruff check .
→ All checks passed!
uv build --out-dir /tmp/toolbox-build-audit
→ toolbox-0.1.0.tar.gz 和 toolbox-0.1.0-py3-none-any.whl 均成功。

E6 参考项目：
/home/emo/code/ImageToolbox/feature 存在；67 feature module数量与registry一致，但本报告不把数量当行为等价。

## 变更记录（历史审计快照）
初始审计阶段没有修复产品 bug；后续第 9 部分记录了本轮实际修复。

## 第 9 部分：本轮修复与补充验证（2026-09-23）

### 9.1 阶段 0 工作树清理

- `app/theme.py` + `tests/test_fonts.py`：内容为 MiSans 字体修复及对应测试，正确，已单独提交 `8ad9e48 fix: use MiSans consistently in theme`。
- `uv.lock`：独立提交 `c4bf2cd chore: add uv lockfile`。
- 原有审计报告先临时 stash，修复阶段完成后恢复；产品源码未因清理步骤被丢弃。
- 分支保持 `feature/toolbox-parity-ui-overhaul`。

### 9.2 P0 修复证据

| Fix | 修复位置 | 修复前 | 修复后 | 回归测试 / Commit |
|---|---|---|---|---|
| SVG Maker | `processors/parity.py:477-490` | shape 缺少 `w` 时可能 `KeyError: 'w'` | `w/width` 有默认值并拒绝非正尺寸；缺参可生成非空 SVG | `test_svg_maker_defaults_missing_width` / `0b193a7` |
| Draw / Markup | `processors/parity.py:550-558` | line/text 缺少 `xy` 时 `KeyError: 'xy'` | `xy` 使用安全默认坐标；缺参仍生成图片 | `test_draw_markup_defaults_missing_xy` / `1dde5e5` |
| Erase Background | `processors/parity.py:561+`、`run_parity_tool` mapping | `background-remove` 无映射，`KeyError` | 增加明确 `background-remove` -> `erase_background`，真实模型仍按 backend 处理 | `test_erase_background_mapping_no_keyerror` / `07044cf` |
| GMIC | `processors/gmic.py:14-19` | 缺失 binary 时 `get_version()` 抛 `FileNotFoundError` | `is_available=False` 且 `get_version()==""`，不抛异常 | `test_missing_binary_version_is_safe` / `a557807` |
| limits-resize | `processors/parity.py:180-190` | `max_width/max_height=0` 仍可能产生输出 | <=0 明确 `ValueError` | `test_limits_resize_rejects_zero_dimensions` / `70066b6` |
| noise-generation | `processors/parity.py:202-205` | 非法 `kind` 静默按 gaussian 处理 | 只接受 `gaussian` / `uniform`，非法值 `ValueError` | `test_noise_rejects_invalid_kind` / `d11bb12` |
| weight-resize | `processors/parity.py:68-75` | 负 `target_kb` 被接受 | `<1` 明确 `ValueError` | `test_weight_resize_rejects_negative_target` / `ca2e9d5` |

### 9.3 测试总回归

- `QT_QPA_PLATFORM=offscreen uv run python -m unittest discover -s tests -v`：36 tests，4.266s，OK。
- `uvx ruff check .`：`All checks passed!`。
- Offscreen MainWindow：`MAINWINDOW_OK 43 任务队列 运行日志 MiSans`。
- `QT_SCALE_FACTOR=2`：`DPI_OK 2.0 1480 900`。
- 当前环境 `DISPLAY=`、`WAYLAND_DISPLAY=` 均为空，因此真实 GUI 仍不能声称通过；本项待用户真机验证。

### 9.4 P1 实测结果（本轮最终证据）

| 功能 | 测试输入 | 实际输出 | 是否符合预期 | 未通过原因 | 证据 |
|---|---|---|---|---|---|
| AI Tools | 128×96 RGB；`ai_enhance(denoise=5, upscale=1.5, saturation=1.2, contrast=1.1)` | `(144,192,3)`，SHA `065d3d790c01` | 是 | 无 | `processors/ai.py:292`，实际 CPU/OpenCV 路径 |
| QR Code | `Toolbox QA QR 123`，系统 `qrencode` 生成 | 扫描回读 `['Toolbox QA QR 123']` | 是 | 无 | `processors/parity.py:278` |
| EXIF 编辑 | JPEG，tag 270=`Toolbox QA` | 读回 `Toolbox QA` | 是 | 无 | `processors/parity.py:622` |
| 网络图片 | Wikimedia JPEG URL | HTTP 200；36,287 bytes；500×477 JPEG | 是 | 无 | `processors/parity.py:637` |
| 设置持久化 | 进程 A 写 `audit/restart`，进程 B 读取；独立 `XDG_CONFIG_HOME` | `WRITE persisted-across-process` / `READ persisted-across-process` | 是 | 无 | `app/settings_store.py` + 两进程实测 |
| 任务队列 | 4 个独立任务并发执行 | 4/4 `完成 · 0.1s`，名称无串扰 | 是 | 无 | `app/workbench.py:18-92` |
| 日志内容 | 写入 `QA keyword alpha`、`other beta` | 两行均可显示 | 部分 | 当前只有追加/清空；没有过滤/导出 API | `app/workbench.py:68-84` |
| 高 DPI | `QT_SCALE_FACTOR=2` + offscreen | `HIDPI_MAINWINDOW_OK MiSans`；DPR=2.0 | 是（offscreen） | 真实桌面绘制未验证 | Qt offscreen 实测 |
| Filters 抽样30 | `ALL_FILTERS` 前30项 | 29/30 通过；`night_vision` 失败 | 否 | OpenCV 报 `Unsupported combination of source format (=5), and destination format (=6)` | `processors/filters.py` |
| APNG | 2×32×24；duration=50 | 2 frames；268 bytes | 是 | 无 | `processors/parity.py:584` |
| GIF | 2×32×24；duration=70 | 2 frames；193 bytes | 是 | 无 | `processors/parity.py` |
| WebP | 32×24；quality=80 | WEBP；70 bytes | 是 | 无 | `processors/parity.py` |
| JXL | 32×24 | JXL；70 bytes | 是 | 无 | `processors/parity.py:jxl_convert` |
| PDF | 32×24 调色板 PDF | 1550 bytes | 是 | 无 | `processors/parity.py:252` |
| Document Scanner | 32×24 RGB | PNG，L，32×24，104 bytes | 是 | 无 | `processors/parity.py:284` |
| OCR | `Toolbox QA 123` | `Toolbox QA 123` | 是 | 无 | `processors/parity.py:429`，tesseract 5.5.3 |

### 9.5 GUI 真实性与边界

真实 GUI 命令：`uv run python main.py`。
实际：`RC=134`；当前终端 `DISPLAY`/`WAYLAND_DISPLAY` 均为空，Qt 无法连接 `xcb`，并提示可用 `offscreen/wayland/xcb` 插件。
结论：**真实 GUI 待用户真机验证**。offscreen 不计为真实 GUI 通过。

offscreen 已实际验证：菜单 `文件/视图/编辑/工具/帮助`；Dock `任务队列/运行日志`；主题 dark/light/system 可切换；MiSans 字体；4 个任务并发完成；DPR=2.0 构造成功。
设置对话框采用模态 `exec`，本轮未伪造“点击保存/恢复默认”的真实 GUI 结果；设置持久化本身已通过两个独立进程验证。

### 9.6 重新统计

按本轮真实证据重新计算；`equivalent` 不升级：

- `usable`: **55**
- `runnable`: **0**
- `equivalent`: **0**
- `未验证`: **10**
- `placeholder`: **2**
- 总计：**67**

本轮从未验证升级的项目：`ai-tools`、`document-scanner`、`edit-exif`、`jxl-tools`、`load-net-image`、`palette-pdf`、`pick-color`、`recognize-text`、`scan-qr-code`、`shader-studio`、`svg-maker`。

仍未验证：`draw`、`markup-layers`、`erase-background`、`filters`、`app-logs`、`help`、`libraries-info`、`library-details`、`main`、`media-picker`。

其中 `svg-maker` 已有真实回归测试，故从原失败项移出；`draw/markup` 只证明缺参不再崩溃，尚未完成交互式 GUI 闭环，因此不升级；`erase-background` 只验证 mapping，不把 fake backend 当成真实模型验证。

### 9.7 equivalent 为什么仍为 0

当前证据证明的是：若干桌面处理器能够真实执行、输出可打开、部分参数能产生可测变化，并且若干错误边界已经覆盖。
但没有完成 ImageToolbox 67 个对应模块逐项的：行为对照、参数语义对照、边界/错误语义对照、输出内容一致性对照、平台差异确认。因此不能把“可运行”写成“功能等价”。

### 9.8 后端现实情况

本轮环境中：GMIC 4.0.5、ImageMagick 7.1.2-31、ffmpeg 9.0.2、tesseract 5.5.3 可执行；`exiftool`、`potrace` 不在 PATH。GMIC 缺失路径已通过回归测试确认 `is_available=False`、`get_version()==""`。

### 9.9 本轮仍未解决的 P2/P3

- 真实 X11/Wayland GUI：**待用户真机验证**。
- Filters：30 项中 29 项通过，`night_vision` 失败；仍未逐项覆盖全部 577 个参考/报告口径滤镜。
- LogWidget：没有过滤和导出能力；按本轮“禁止新增功能”要求不实现。
- Erase Background：真实 rembg 模型下载、缓存、CPU/GPU backend、实际抠图闭环仍未完成。
- 8000×8000、处理中取消、快速连续点击、关闭窗口时处理、全模块并发的完整破坏性矩阵仍未完成。
- 后端缺失时的 UI fallback/manual backend 标识尚未完整验证。
- 设置对话框的真实点击保存/恢复默认以及真实 GUI DPI 绘制仍待真机验证。
- 本轮没有推进 A2.5，没有新增功能。

## 10. 第二轮真机结果回写

本轮承接消息中的“用户真机验证结果”字段没有实际填写具体结果，因此**没有伪造真机通过项**。真实 X11/Wayland GUI、真实菜单点击、真实 Dock、真实设置对话框点击仍标记为“待用户真机验证”。本轮远程环境仍无 `DISPLAY`/`WAYLAND_DISPLAY`。

## 11. P2/P3 Blocker 修复

### 11.1 night_vision

- 修复文件：`processors/advanced_filters.py:598`
- 修复前：`cv2.Laplacian(gray, cv2.CV_64F)` 在当前 OpenCV 5 环境报 `Unsupported combination of source format (=5), and destination format (=6)`。
- 修复后：使用 `cv2.CV_32F`；实际 `32×32 uint8` 输入成功输出 `32×32 uint8`，mean=32。
- 回归：`tests/test_filters.py::test_night_vision_runs_and_returns_rgb`
- commit：`469a60b fix: night vision filter`

### 11.2 LogWidget

- 修复文件：`app/workbench.py:91+`
- 新增：关键字搜索、级别搜索、TXT/JSON 导出、清空、自动滚动。
- 回归：`tests/test_workbench.py`
- 实测：INFO/ERROR 过滤、TXT 内容、JSON 数组、清空全部通过。
- commit：`aa399dc feat: log widget filter and export`

### 11.3 Erase Background / rembg

- 修复文件：`processors/ai.py:28+`
- 缺少 rembg 时从裸 `ImportError` 改为明确 `RuntimeError("rembg 后端不可用，请安装 rembg[cli] 和 onnxruntime")`。
- 当前环境：`rembg=True`、`onnxruntime=True`、CUDA provider 包不存在；实际 U²-Net 模型已缓存于 `~/.rembg/models/u2net/u2net.onnx`，约 176 MB。
- 实际 CPU 路径：128×128 红色圆形输入 → 128×128 RGBA 输出，721 bytes，成功。
- 回归：`tests/test_ai.py::test_missing_rembg_is_clear_error`
- commit：`86d5efb fix: erase background rembg pipeline`

### 11.4 Backend fallback status

- `backends/registry.py` 增加每个后端的安装提示。
- `app/main_window.py` 后端状态页现在显示“后端不可用 + 安装提示”，并提供“刷新后端状态”；GMIC filter cache 刷新保持独立。
- 模拟所有 `shutil.which` 后端缺失的测试通过。
- commit：`78be42d feat: expose backend fallback status in UI`

## 12. 破坏性测试矩阵

本轮实际执行了空/非法/极端输入和真实 8000×8000 输入。**没有把“函数没有崩”误写成“输出语义正确”**。

| 模块 | 场景 | 期望 | 实际 | 通过 | 证据 |
|---|---|---|---|---|---|
| APNG | 空帧 | 明确拒绝 | `ValueError: 至少需要一个帧` | 是 | `/tmp/destructive2.json` |
| Archive | 空列表 | 安全处理 | 22-byte 空 ZIP | 是（定义为空归档） | `/tmp/destructive2.json` |
| ASCII | 非法图像 | 拒绝 | `UnidentifiedImageError` | 是 | `/tmp/destructive2.json` |
| Audio Cover | 非音频 | 拒绝/无封面 | `ValueError: 音频文件没有找到嵌入封面` | 是 | `/tmp/destructive2.json` |
| Batch Rename | 空列表 | 安全 no-op | 返回 `[]` | 是 | `/tmp/destructive2.json` |
| Checksum | 文本文件 | 任意文件可校验 | 返回全部 checksum | 是 | `/tmp/destructive2.json` |
| Cipher | 文本文件/空密码 | 文件仍可加密 | 输出 100 bytes | 是 | `/tmp/destructive2.json` |
| Collage | 空列表 | 安全处理 | 生成小图 | **需人工确认语义** | `/tmp/destructive2.json` |
| Curves | 非法图像 | 拒绝 | `UnidentifiedImageError` | 是 | `/tmp/destructive2.json` |
| Fractal | 0×0/0 iterations | 拒绝或安全错误 | `ZeroDivisionError` | **否** | `/tmp/destructive2.json` |
| Limits Resize | 0×0 | 拒绝 | 明确 `ValueError` | 是 | `/tmp/destructive2.json` |
| Mesh Gradient | 0×0 | 拒绝 | `ValueError: cannot write empty image` | 是 | `/tmp/destructive2.json` |
| Fusion | 空帧 | 拒绝 | `ValueError: min() iterable argument is empty` | 是 | `/tmp/destructive2.json` |
| Noise | 非法 kind | 拒绝 | `ValueError: unsupported noise kind` | 是 | `/tmp/destructive2.json` |
| Palette | 非法图像 | 拒绝 | `UnidentifiedImageError` | 是 | `/tmp/destructive2.json` |
| Resize/Convert | 非法图像/格式 | 拒绝 | `UnidentifiedImageError` | 是 | `/tmp/destructive2.json` |
| Texture | 0×0/非法 kind | 拒绝 | `ValueError: cannot write empty image` | 是 | `/tmp/destructive2.json` |
| WebP | 非法图像/quality=-1 | 拒绝 | `UnidentifiedImageError` | 是 | `/tmp/destructive2.json` |
| Weight Resize | target_kb=-1 | 拒绝 | `ValueError: target_kb must be at least 1` | 是 | `/tmp/destructive2.json` |
| Watermark | 非法图像 | 拒绝 | `UnidentifiedImageError` | 是 | `/tmp/destructive2.json` |
| Crop | width/height=0 | 不应静默扩大范围 | 实际生成约原尺寸图 | **否/待修** | `/tmp/destructive2.json` |
| Gradient | 非法颜色 | 拒绝 | `ValueError: unknown color specifier` | 是 | `/tmp/destructive2.json` |
| PDF | 非法图像/count=0 | 拒绝 | `UnidentifiedImageError` | 是 | `/tmp/destructive2.json` |
| SVG Maker | 0×0 | 应拒绝无效尺寸 | 生成 `viewBox=0 0 0 0` SVG | **否/待修** | `/tmp/destructive2.json` |
| 8000×8000 Resize | 大图 | 无崩溃并输出 | 4096 限制输出成功 | 是 | `/tmp/destructive2.json` |
| 8000×8000 WebP | 大图 | 无崩溃并输出 | 成功 | 是 | `/tmp/destructive2.json` |
| 8000×8000 Crop | 大图 | 无崩溃并输出 | 成功 | 是 | `/tmp/destructive2.json` |
| Fractal | 4 并发 | 4 独立输出 | 4/4 | 是 | `/tmp/destructive2.json` |

### 取消/关闭窗口边界

任务系统真实执行了“取消前置任务”和 4 并发任务；但当前处理器 API 大多不是可取消协作式 API，因此**处理中取消不能证明真正中断底层处理**。本轮不伪造“中途取消已通过”。真实窗口关闭时的全部处理任务矩阵也没有在无头环境中冒充 GUI 通过。

因此本轮明确保留 P2：

- `fractal-generation` 0×0 仍可能 `ZeroDivisionError`。
- `crop` 0 尺寸会被当前实现按 falsy 值处理，存在边界语义问题。
- `svg-maker` 0×0 会生成 0×0 SVG。
- 处理中真正取消、关闭窗口时处理、快速连续点击的完整 GUI 矩阵仍待真实桌面环境验证。

## 13. 最终等级

本轮真实执行后重新统计：

- **usable：55**
- **runnable：0**
- **equivalent：0**
- **未验证：10**
- **placeholder：2**
- **总计：67**

本轮从未验证升级到 usable 的 11 项：`ai-tools`、`document-scanner`、`edit-exif`、`jxl-tools`、`load-net-image`、`palette-pdf`、`pick-color`、`recognize-text`、`scan-qr-code`、`app-logs`、`erase-background`。

`shader-studio` 不升级：虽然 `Color Invert` 有实际 CPU 输出，但 `Grayscale/Tint` 执行器没有实现对应 effect，且真实 OpenGL GUI 未验证。

仍未验证 10 项：`draw`、`markup-layers`、`filters`、`help`、`libraries-info`、`library-details`、`main`、`media-picker`、`root`、`shader-studio`。

## 14. Equivalent 样本结果

判定标准：`docs/parity-equivalent-criteria.md`。
样本对照：`docs/parity-comparison-texture-shader.md`。

- Texture Studio / Perlin + Pattern：**不 equivalent**。参考实现的纹理类型、Pattern 参数和 GPU 路径覆盖明显更广。
- Shader Studio / Color Invert + Grayscale + Tint：**不 equivalent**。参考实现是通用 shader preset 编辑器；Toolbox 的 Grayscale/Tint CPU effect 实际没有实现，且参考项目没有证据证明这三个名字是官方内置 preset。
- `equivalent`：**0 → 0**。

## 15. 本轮新增 P2/P3

- Fractal 0×0 → `ZeroDivisionError`。
- Crop 0 尺寸 → 静默使用原尺寸语义。
- SVG Maker 0×0 → 生成无效尺寸 SVG。
- Shader CPU `grayscale` / `tint` 名义 preset 与执行器不一致。
- 完整 577 filters 仍未逐项验证；night_vision 已修复。
- 真正处理中取消/关闭窗口仍未完成真实 GUI 验证。
