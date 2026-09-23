# Toolbox 手动验证清单

日期：2026-09-22  
目标：给人类 QA 一份可以直接执行、并能明确判断成功/失败的验收流程。

> 本文件不是“测试已经通过”的声明。每项都需要实际操作。

## 1. 启动与主工作台

### image-preview
1. 打开“文件”→“打开”。
2. 选择 PNG/JPEG。
3. 点击“适合窗口”“实际大小”“放大”“缩小”。
4. 期望：中央预览按命令变化，比例保持。
5. 失败：黑屏、花屏、比例错误或缩放后图片损坏。

### settings
1. 菜单→“设置”。
2. 修改主题、字体、默认输出目录、最近文件、线程数。
3. 点击“应用”。
4. 完全退出程序。
5. 重新启动。
6. 期望：设置仍存在。
7. 失败：重启后恢复默认。

### single-edit
1. 打开图片。
2. 使用一个调整或滤镜工具。
3. 点击“另存为”。
4. 重新打开输出。
5. 期望：输出能正常打开且修改存在。
6. 失败：输出损坏或参数没有效果。

## 2. Texture Studio

### texture-generation
1. 打开 Texture Studio。
2. 分别进入 Noise、Pattern、GMIC、Raymarch。
3. 修改 Seed、Scale、Contrast。
4. 点击“随机 Seed”。
5. 期望：预览变化；相同参数可复现。
6. 失败：参数无效、旧请求覆盖新结果、UI 卡死。

### fractal-generation
1. 打开“分形生成”。
2. 宽度输入 1024，高度 768。
3. 迭代输入 320。
4. 修改中心 X/Y 和视野尺度。
5. 点击“生成 / 处理”。
6. 期望：输出 Mandelbrot 风格分形。
7. 失败：纯色、尺寸错误、参数无影响。

### noise-generation
1. 打开噪声生成。
2. 选择 gaussian。
3. 记录输出。
4. 改为 uniform。
5. 再生成。
6. 期望：两种噪声统计纹理明显不同。
7. 失败：完全相同或单色。

### mesh-gradients
1. 打开网格渐变。
2. 四角分别输入 #ff0000、#00ff00、#0000ff、#ffffff。
3. 生成 1024×1024。
4. 期望：四角接近指定颜色，中间平滑。
5. 失败：角点顺序错误或出现硬边。

## 3. 文件与批处理

### apng-tools
1. 准备 2 张尺寸相同 PNG。
2. 设置帧间隔。
3. 导出 APNG。
4. 用图片查看器打开。
5. 期望：识别为多帧动画。
6. 失败：只显示第一帧或文件损坏。

### archive-tools
1. 选择多个图片。
2. 创建 ZIP。
3. 运行 unzip -t 输出.zip。
4. 期望：所有条目通过。
5. 失败：缺文件或 ZIP 损坏。

### base64-tools
1. 选择二进制文件。
2. Encode。
3. Decode。
4. 执行 sha256sum 原文件 恢复文件。
5. 期望：hash 完全一致。
6. 失败：任意字节变化。

### batch-rename
1. 选择至少 5 个文件。
2. 模板输入 {original}_{sequence}。
3. 起始序号 1，补零 3。
4. 点击“预览重命名”。
5. 期望：出现 name_001、name_002 等。
6. 点击执行。
7. 期望：实际文件名与预览一致。
8. 失败：冲突、覆盖或序号错误。

### checksum-tools
1. 选择一个文件。
2. 计算 SHA-256。
3. 执行 sha256sum 文件。
4. 期望：两者完全一致。
5. 失败：hash 不同。

### cipher
1. 选择测试文件。
2. 使用密码 Toolbox-Audit-2026 加密。
3. 用相同密码解密。
4. 对原文件和恢复文件计算 SHA-256。
5. 期望：完全一致。
6. 使用错误密码。
7. 期望：明确失败。

### code-preview
1. 打开 UTF-8 文本/代码文件。
2. 使用代码预览。
3. 检查中文和特殊字符。
4. 期望：不乱码。
5. 失败：编码破坏或内容缺失。

## 4. 图片组织

### image-cutting / crop
1. 打开 1920×1080 图片。
2. 选择 800×600。
3. 执行裁切。
4. 期望：输出严格为 800×600。
5. 失败：尺寸或区域错误。

### image-splitting
1. 打开 1000×700 图片。
2. 设置 3×2。
3. 执行。
4. 期望：得到 6 个文件且覆盖原图范围。
5. 失败：数量错误或边缘丢失。

### image-stacking
1. 选择 3 张不同高度图片。
2. 选择 horizontal。
3. 设置 spacing。
4. 导出。
5. 期望：三张均出现，没有越界。
6. 失败：缺图、覆盖或裁切。

### quick-tiles
1. 选择多张图片。
2. 设置 4 列。
3. 生成。
4. 期望：每个输入都能在结果中找到。
5. 失败：漏图。

### collage-maker
1. 选择 6 张不同尺寸图片。
2. 设置 3 列。
3. 生成。
4. 期望：6 张图片都存在且没有越界。
5. 失败：漏图或异常裁切。

### image-stitch
1. 选择至少 3 张图片。
2. 分别执行 horizontal、vertical、grid。
3. 期望：输出方向与模式一致。
4. 失败：方向错或图片缺失。

## 5. 颜色与效果

### color-library / palette-tools
1. 打开一张颜色丰富的照片。
2. 提取 5 个主色。
3. 期望：得到 5 个合法 #RRGGBB。
4. 对同一输入再次执行。
5. 期望：结果稳定。
6. 失败：颜色格式错误或结果随机漂移。

### color-tools
1. 打开图片。
2. 选择明显颜色。
3. 输入 source/target/tolerance。
4. 执行替换。
5. 期望：目标区域改变，其余区域基本保持。
6. 失败：全图异常变色。

### curves
1. 打开照片。
2. 修改中间曲线节点。
3. 导出。
4. 期望：中间调明显改变。
5. 失败：节点移动后结果完全不变。

### watermarking
1. 打开图片。
2. 输入 Toolbox Audit。
3. 位置选择 bottom-right。
4. 设置透明度 50%。
5. 导出。
6. 期望：右下角出现半透明文字。
7. 失败：位置或透明度无效。

## 6. 动画与媒体

### gif-tools
1. 准备 3 张 PNG。
2. 生成 GIF。
3. 使用 identify 或图片查看器检查帧数。
4. 期望：至少 3 帧。
5. 失败：单帧或无法打开。

### multi-frame-fusion
1. 创建三个 32×32 灰色图片，像素分别为 40、80、120。
2. 选择 median。
3. 期望输出约 80。
4. 依次测试 mean/max/min。
5. 期望约为 80/120/40。
6. 失败：结果不符合数学定义。

### audio-cover-extractor
1. 准备带嵌入封面的 MP3/FLAC。
2. 执行封面提取。
3. 打开导出图片。
4. 期望：尺寸非零且内容是嵌入封面。
5. 失败：无法识别封面或导出损坏。

### wallpapers-export
1. 打开图片。
2. 输入目标宽高。
3. 选择 cover。
4. 导出。
5. 期望：尺寸严格匹配并保持比例。
6. 失败：图片被拉伸。

## 7. SVG / 格式 / PDF

### svg-maker
1. 打开 SVG 制作。
2. 选择 rect。
3. 输入 X/Y/size。
4. 导出 SVG。
5. 用浏览器打开。
6. 期望：位置和尺寸正确。
7. 分别测试 circle/text。
8. 失败：XML 无法解析或元素缺失。

### format-conversion / resize-convert
1. 打开 PNG。
2. 转换为 JPEG 和 WebP。
3. 重新打开。
4. 期望：格式和尺寸正确。
5. 失败：格式错误或颜色模式异常。

### webp-tools
1. 输入 PNG/JPEG。
2. quality 设置 50、95。
3. 分别导出。
4. 期望：都能打开且存在可解释的压缩差异。
5. 失败：参数无效。

### pdf-tools
1. 选择多页 PDF。
2. 执行当前可见 PDF 导入/导出。
3. 用系统 PDF 阅读器重新打开。
4. 期望：页数和内容保持。
5. 失败：PDF 损坏或页面丢失。

## 8. QA 记录规则

每个项目记录：
- 输入文件 hash
- 软件版本/commit
- 使用参数
- 输出文件
- 成功/失败
- 失败截图和日志

不要用“单元测试通过”替代人工/输出文件验收。


## 0.1 启动回归快速验证

目标：确认 Qt 6.11 下字体初始化不会阻止 MainWindow 创建。

```bash
cd /home/emo/code/toolbox
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "from PySide6.QtWidgets import QApplication; from app.main_window import MainWindow; app=QApplication([]); w=MainWindow(); print('MAINWINDOW_OK'); w.close()"
```

预期：输出 `MAINWINDOW_OK`，且进程以 0 退出。

注意：该命令只证明 offscreen MainWindow 初始化；不能替代真实 Wayland/X11 窗口人工验证。

## 0.2 当前自动回归基线

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
uvx ruff check .
```

当前基线：25 个测试全部通过；Ruff 当前只作为 E9 语法错误 gate。完整风格 lint 尚未完成。


## 0.3 打包元数据快速验证

```bash
uv build --out-dir /tmp/toolbox-build
```

预期：同时生成 `.tar.gz` 与 `.whl`；验证后可删除临时目录。


## 9. 本轮补充验证清单（2026-09-23）

### P0 修复

- SVG Maker：缺少 rect `w`/width 时导出仍成功，检查 SVG 非空且 width 使用默认值。
- Draw / Markup：line/text 缺少 `xy` 时不应 `KeyError`，检查输出图片可打开。
- Erase Background：调用 `background-remove` 不应 `KeyError`；真实 rembg 后端另测。
- GMIC：`GMICBackend(path="/nonexistent/gmic")` 应 `is_available=False` 且 `get_version()==""`。
- limits-resize：`max_width=0` 或 `max_height=0` 必须明确报错。
- noise-generation：`kind=invalid` 必须明确报错；`gaussian` / `uniform` 均应正常生成。
- weight-resize：`target_kb<1` 必须明确报错。

### P1 功能

1. AI Tools：运行 `ai_enhance` 实际 CPU/OpenCV 路径，记录输入/输出尺寸与 SHA；`rembg` 真实抠图模型仍待单独验证。
2. QR：生成 `Toolbox-QA-123`，扫描后必须得到同一字符串。
3. EXIF：写 tag 270，再读回并比对值。
4. 网络图片：使用小型公开 PNG URL，记录 HTTP 状态码和输出尺寸。
5. 设置持久化：进程 A 写值，进程 B 读取，不能只测同一进程。
6. 任务队列：提交 4 个独立任务，确认 4/4 完成且名称/结果不串扰；另测取消。
7. 日志：当前实现只有追加/清空，过滤和导出能力未通过本轮审计。
8. 高 DPI：`QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=2` 构造 MainWindow；记录 DPR；真实桌面绘制仍待真机。
9. Filters：从当前 `ALL_FILTERS` 抽样 30 项逐项运行；记录每个 key 的结果。任何失败都不能把全部 Filters 标成 usable。
10. APNG/GIF/WebP/JXL/PDF/Document Scanner/OCR：各运行一个最小用例并检查实际输出文件。

### GUI 真实性

```bash
printf 'DISPLAY=%s WAYLAND_DISPLAY=%s\n' "$DISPLAY" "$WAYLAND_DISPLAY"
uv run python main.py
```

若 DISPLAY 与 WAYLAND_DISPLAY 均为空，只记录为“待用户真机验证”，不得把 offscreen 结果写成真实 GUI 通过。

### 当前回归基线

```bash
QT_QPA_PLATFORM=offscreen uv run python -m unittest discover -s tests -v
uvx ruff check .
QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=2 uv run python -c 'from PySide6.QtWidgets import QApplication; from app.main_window import MainWindow; a=QApplication([]); w=MainWindow(); print(a.devicePixelRatio()); w.close()'
```

本轮实际结果：36 tests 全部通过；Ruff `All checks passed!`；DPR=2.0 构造成功。


## 10. 本轮最终状态

- 等级：`usable 55 / runnable 0 / equivalent 0 / 未验证 10 / placeholder 2`。
- 真实 GUI：**待用户真机验证**；当前远程终端没有 DISPLAY/Wayland。
- Filters：30 项抽样 29 成功，`night_vision` 失败，不能升级为完整通过。
- 日志：当前只有追加/清空，本轮不新增过滤/导出功能。
- Erase Background：仅修复 mapping 崩溃，真实 rembg 模型闭环仍待验证。
- 破坏性矩阵（8000×8000、取消、快速点击、关闭窗口）仍需后续专门执行。
