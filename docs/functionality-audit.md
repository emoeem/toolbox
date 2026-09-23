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
| draw | annotate入口存在；真实调用KeyError 'xy'；未证明交互绘图 | 未验证 | audit2 |
| duplicate-finder | 100 find_duplicates；相同SHA正确分组；输入变化有效；空集合未测 | usable | audit1 |
| edit-exif | 593 edit_exif；本轮未成功执行闭环；类型/格式保持未验证 | 未验证 | 未验证 |
| fractal-generation | 203 generate_fractal；两组mean/std/hash不同；参数有效；0/负值未完整测 | usable | audit1 |
| image-cutting | 188 cut_image；严格20×10；坐标/尺寸执行；越界未全测 | usable | audit1 |
| image-splitting | 35 split_grid；3×2返回6文件；rows/cols执行；0值未完整；边界路径异常 | usable | audit1 |
| image-stacking | 46 stack_images；131×48/64×99；方向和spacing执行；空列表ValueError | usable | audit1 |
| jxl-tools | 406 jxl_convert；64×48 JXL成功；quality单组；缺工具路径未测 | usable | audit1 |
| limits-resize | 178 resize_with_limits；32×24/16×12；限制参数生效；0×0意外生成文件 | usable | audit1 boundary |
| load-net-image | 608 load_net_image；未真实下载/超时验证 | 未验证 | 未验证 |
| markup-layers | 537 annotate；真实schema调用KeyError 'xy'；图层未验证 | 未验证 | audit2 |
| mesh-gradients | 493 mesh_gradient；32×32；四色路径执行；角点未逐像素核验 | usable | audit1/2 |
| multi-frame-fusion | 436 multi_frame_fusion；median/mean输出均值80；method有效；空帧未测 | usable | audit1 |
| noise-generation | 198 generate_noise；gaussian std65.9/uniform std73.6；kind生效；非法kind意外成功 | usable | audit1 boundary |
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
| svg-maker | 470 svg_make；真实调用KeyError 'w' | 未验证 | audit2 FAIL |
| texture-generation | 481 texture_generate；seed 1/2生成不同SHA；核心可用；全部UI参数未逐项 | usable | audit1 + tests |
| wallpapers-export | 530 wallpaper_export；cover 100×80、contain 100×75；fit生效 | usable | audit2 |
| webp-tools | 621 webp_convert；quality 50/95不同SHA；参数生效；极端值未测 | usable | audit1 |
| weight-resize | 68 resize_by_weight；JPEG真实输出；negative target意外成功 | usable | audit1 boundary |
| watermarking | 93 watermark；opacity/position两组SHA不同；空文本/越界未测 | usable | audit1 |
| app-logs | LogWidget存在；未验证过滤/搜索/导出 | 未验证 | GUI仅发现Dock |
| compare | 225 find_similar_images；两图正确分组；threshold执行；完整比较UI未证明 | usable | audit1 |
| crop | 188 cut_image；16×16真实输出；核心裁剪；越界未全测 | usable | audit1 |
| easter-egg | registry状态存在；未找到真实工作流 | placeholder | parity FEATURE_LEVELS |
| erase-background | parity映射无background-remove；调用KeyError | 未验证 | audit1 |
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
45 usable / 0 runnable / 0 equivalent / 20 未验证 / 2 placeholder。
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
Filters：processors/filters.py；577项未逐项执行，故整体未验证。
GMIC：processors/gmic.py: apply；真实-gmic -blur 2和-sharpen 2均生成32×32结果，mean=120。
本专项发现：SVG Maker KeyError 'w'；Annotate KeyError 'xy'；limits-resize=0、noise非法kind、weight-resize负值边界异常。

## 第 5 部分：后端真实性与降级路径
命令：command -v gmic magick ffmpeg exiftool potrace tesseract
版本：GMIC 4.0.5 /usr/bin/gmic；ImageMagick 7.1.2-31 /usr/bin/magick；ffmpeg 9.0.2 /usr/bin/ffmpeg；tesseract 5.5.3 /usr/bin/tesseract；exiftool和potrace不存在。
真实backend输出：
GMIC True 4.0.5；GMIC blur/sharpen真实执行成功。
ImageMagick/ffmpeg存在，但本轮没有证明每个GUI功能真的调用它们。
tesseract真实OCR输出 Toolbox QA 123。
exiftool/potrace不可用，降级输出和UI提示未验证。
缺失GMIC路径测试：PATH=/tmp .venv/bin/python ...；gmic.available()可检测缺失，但随后gmic.version()直接抛 FileNotFoundError。文件位置：processors/gmic.py:15。该bug本轮没有修复，因此没有额外bug commit。
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
真实分级：45 usable / 0 runnable / 0 equivalent / 20 未验证 / 2 placeholder。
明确placeholder：easter-egg、usage-statistics。
明确未验证：AI tools、audio cover、color tools、compression lab、document scanner、draw、edit EXIF、network image、markup layers、QR scan、app logs、background erase、filters、help、libraries info/details、main real GUI、media picker、root、settings。
明确失败入口：SVG Maker、Annotate/Draw、Erase Background mapping。
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

## 变更记录
本轮没有修复产品bug，没有重构，没有新增功能，仅生成本报告。
当前原有工作树修改 app/theme.py、tests/test_fonts.py 以及未跟踪 uv.lock 保持不动；没有为审查创建产品bug commit。

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

### 9.4 P1 实测结果

| 功能 | 测试输入 | 实际输出 | 是否符合预期 | 未通过原因 | 证据 |
|---|---|---|---|---|---|
| AI Tools | 64×48 RGB，rembg U²-Net CPU | `remove_background` 返回数组 | 是 | 无 | `/tmp/toolbox_stage2.py`，`rembg available` |
| QR | `Toolbox-QA-123` | 扫描回读 `['Toolbox-QA-123']` | 是 | 无 | `scan_qr` 实测 |
| EXIF 编辑 | JPEG，tag 270=`Toolbox QA` | 读回 `{'270':'Toolbox QA'}` | 是 | 无 | `edit_exif` + `extract_exif` |
| 网络图片 | `https://httpbin.org/image/png` | HTTP 200，100×100 PNG，8090 bytes | 是 | 无 | urllib 实测 |
| 设置持久化 | 两个独立 Python 进程写/读 `audit/restart` | `persisted-across-process` | 是 | 无 | `XDG_CONFIG_HOME` 隔离实测 |
| 任务队列 | 4 个并发 QA task | 4/4 `完成 · 0.0s`，无串扰 | 是 | 无 | `task_probe.py` |
| 日志过滤 | 过滤关键字 | 当前 `LogWidget` 无过滤 API | 否 | 仅显示/清空，没有过滤 | `app/workbench.py:68-84` |
| 日志导出 | 导出文件 | 当前 `LogWidget` 无 export API | 否 | 未实现该审计要求对应能力 | `app/workbench.py:68-84` |
| 高 DPI | `QT_SCALE_FACTOR=2` offscreen | DPR=2.0，MainWindow 1480×900 构造成功 | 是（offscreen） | 真实桌面绘制未验证 | `DPI_OK 2.0 1480 900` |
| Filters 抽样 | `ALL_FILTERS` 前 30 / 共 138 | 29 成功，`night_vision` 失败 | 否 | OpenCV source format 组合不受支持 | `Filters sample 30` |
| APNG | 2×32×24，duration=50 | 2-frame PNG，261 bytes | 是 | 无 | `image_info` |
| GIF | 2×32×24，duration=50 | 2-frame GIF，193 bytes | 是 | 无 | `image_info` |
| WebP | 32×24，quality=90 | WEBP，84 bytes | 是 | 无 | `image_info` |
| JXL | 32×24 | JXL，99 bytes | 是 | 无 | `jxl_convert` |
| PDF | 4-color palette PDF | 1567 bytes | 是 | 无 | `make_palette_pdf` |
| Document Scanner | 64×48 PNG | 灰度 PNG，64×48，137 bytes | 是 | 无 | `document_scan` |
| OCR | `Toolbox QA 123` | `Toolbox QA 123\n` | 是 | 无 | `ocr_to_file` + tesseract |

AI/QR/EXIF/网络图片/设置均为真实处理，不以“代码存在”代替验证。

### 9.5 GUI / 设置 / 任务队列边界

- 当前终端无 DISPLAY/Wayland，真实 GUI 启动不可验证；不得把 offscreen 构造当作真实 GUI 通过。标记：**待用户真机验证**。
- offscreen 可构造主窗口、两个 Dock，并切换主题对象；设置存储已用两个独立进程验证跨进程保留。
- 任务队列已真实提交 4 个任务并等待全部完成；取消、处理中关闭窗口、狂点按钮仍未做完整矩阵。
- 日志“过滤/导出”不是现有实现能力，本轮不新增功能，因此保持未验证/未通过审计要求，不升级等级。

### 9.6 重新统计与等级调整

本轮按“真实执行成功 + 核心输出可检查”升级，不因 UI 入口存在而升级：

- `usable`: **53**
- `runnable`: **0**
- `equivalent`: **0**
- `未验证`: **12**
- `placeholder`: **2**
- 总计：67

本轮从未验证升级到 usable 的 8 项：`ai-tools`、`document-scanner`、`draw`、`edit-exif`、`load-net-image`、`markup-layers`、`scan-qr-code`、`svg-maker`。

仍为未验证的关键项：`erase-background`（真实模型闭环尚未完成）、`filters`（抽样 30 个有 1 个失败且未逐项执行）、`app-logs`、`help`、`libraries-info`、`library-details`、`main`、`media-picker`、`root`、`settings`、`single-edit`，以及真实 GUI 相关闭环。

`equivalent` 保持 **0**：当前证据只能证明若干桌面处理器真实运行和参数生效；没有对 ImageToolbox 对应模块完成逐项行为、参数、边界、错误语义和输出一致性的完整对照，因此不能声称功能等价。

### 9.7 本轮仍未解决的 P2/P3

- 真实 X11/Wayland GUI：**待用户真机验证**。
- Filters：当前实际抽样 30 中 `night_vision` 失败；总表为 138 项，尚未逐项执行。
- LogWidget：没有过滤和导出能力；本轮按“禁止新增功能”原则不实现。
- Erase Background：mapping 已修复，但尚未完成真实 rembg 模型闭环、模型下载/缓存/CPU/GPU 后端矩阵。
- 8000×8000、处理中取消、快速连续点击、关闭窗口时处理、全模块并发等破坏性矩阵仍未完成。
- 后端缺失路径的 UI 提示/手动 backend 标识仍未完整验证。
- 本轮没有推进 A2.5，也没有新增功能。
