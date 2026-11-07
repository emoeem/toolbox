# Toolbox 2.0.0-alpha.1

Toolbox 2.0 的首个预发布版本：图像处理 + 创作工具箱从单进程 PySide6 应用
**重写为 C++/QML 壳 + Python Worker 双进程架构**（JSON Lines IPC），并完成
核心编辑、滤镜、批处理、创作 Studio 与辅助工具五大能力域的垂直切片。

**这是 alpha 预发布**：三平台安装包由 CI 构建并打包，GUI 端到端的实机验收
仍在进行（见"已知限制"），欢迎试用并到
https://github.com/emoeem/toolbox/issues 反馈。

## ✨ 亮点

- **全新 UI（Qt 6 / Qt Quick）**：NavRail 八大工作区（首页 / 编辑 / 创作 /
  批量 / 分析 / AI / 文件工具 / 设置）+ 全局命令面板（Ctrl+K）+
  Dark/Light/System 主题，布局与设置持久化；UI 主线程零图像计算。
- **核心编辑**：打开 → 画布（缩放/平移/棋盘格）→ 调整滑杆（防抖两级分辨率
  实时预览）→ 应用（后台任务可取消）→ 撤销/重做 → 保存，全链路错误码化。
- **滤镜系统**：78+ 内置滤镜（分类/搜索/依赖置灰），参数面板自动生成，
  **滤镜链**组合/排序/启停，预设保存/加载/删除，预览与应用同一参数语义。
- **参数化 undo**：滤镜链历史只存链参数（从基线重放），大图 undo 内存从
  O(像素×历史) 降到 O(参数)；连续滑杆调整自动合并为单条历史命令。
- **批处理**：文件/目录导入 → 纯转换或滤镜链预设 → 输出设置 → 逐文件进度
  与失败隔离，全程可取消、非模态。
- **创作 Studio**：15 种 2D 分形 + Mandelbulb 3D、纹理、渐变生成器统一
  工作区，产物一键"发送到编辑器"。
- **文件工具页**：32 个工具动作——OCR、PDF×8、条形码×3、ASCII、图像对比、
  校验和、直方图、LUT、媒体、EXIF、水印、归档、加密、Base64、AI×5。
- **依赖诚实**：可选依赖缺失时功能置灰并说明原因（`DEPENDENCY_MISSING`），
  绝不假装可用。

## 📦 下载与安装

| 平台 | 产物 | 说明 |
|---|---|---|
| Linux 通用 | `toolbox-2.0.0-alpha.1-linux-x64.tar.gz` | GLIBC ≥ 2.35（Ubuntu 22.04 / Debian 12+ 等），解压运行 `./toolbox.sh` |
| Linux AppImage | `toolbox-2.0.0-alpha.1-linux-x64.AppImage` | 免安装单文件，`chmod +x` 后直接运行（自动预置后端配置） |
| Arch Linux | `toolbox2-2.0.0.alpha.1-1-x86_64.pkg.tar.zst` | `sudo pacman -U` 安装，命令 `toolbox2`（自动预置 `/opt/toolbox2` 配置） |
| Windows x86_64 | `toolbox-2.0.0-alpha.1-windows-x64.zip` | Win 10+，解压运行 `toolbox.bat` |
| macOS arm64 | `toolbox-2.0.0-alpha.1-macos-arm64.zip` | Apple Silicon (M1/M2/M3)，解压运行 `start.command` |

**首次启动**：所有打包均捆绑 Python 运行时与 Worker 引擎。Linux/Windows/
macOS 压缩包与 AppImage 的启动脚本会在首次运行时自动预置后端配置
（`~/.config/Emo/Toolbox2.conf` 等对应路径的 `backend/python` 与
`backend/repoRoot`），顶栏状态点变绿即引擎就绪；若需手动调整，
入口在 设置 → 后端。Arch 包由 `toolbox2` 启动器自动指向 `/opt/toolbox2`。

源码运行（Linux 推荐，功能最完整）：

```bash
git clone https://github.com/emoeem/toolbox && cd toolbox
uv sync
uv run python main.py
# Wayland: QT_QPA_PLATFORM=wayland uv run python main.py
```

## 🔧 可选依赖（缺失自动降级，置灰并说明原因）

| 依赖 | 启用的能力 |
|---|---|
| `gmic` CLI | G'MIC 滤镜族 |
| `pytesseract` + tesseract | OCR |
| `pdf2image` + poppler | PDF 转图 |
| `qrcode` / `pystrich` / `pyzbar` | 条形码 |
| `cryptography` | 加密/解密工具 |
| AI 模型文件（EDSR/Real-ESRGAN） | AI 超分辨率 |

## ⚠️ 已知限制（alpha 口径）

- GUI 端到端为 **CI 构建 + 静态评审 + 单元/CTest 覆盖**；Linux 桌面实机
  验收清单（`docs/phase*-acceptance.md`）尚未执行完毕；Windows/macOS 包
  仅通过 CI 构建，未做实机验收。
- AI 能力：无模型文件时默认不可用（不虚构推理）；`ai.denoise`/`ai.colorize`
  为 OpenCV 启发式实现。
- G'MIC 滤镜库本体尚未接入（本版本提供 `gmic.check` 诊断与置灰路径）。
- Studio [另存为] 未实现；`shader:preview` 恒不可用（Worker 无 OpenGL 运行时）。
- 工具页参数面板暂为参数 JSON 编辑器（逐工具表单化排入后续批次）。
- EXIF 逐 Tag 编辑、图片→PDF、重复/相似查找等 1.0 辅助能力未迁移
  （完整清单见 `docs/ui-migration-matrix.md` 与 CHANGELOG 已知限制节）。

## 🔄 回滚锚点

每个里程碑有独立标签（`phase6a-complete` … `phase8-complete`），可按标签
回溯任意稳定点；2.0 开发分支模型见 CONTRIBUTING.md。
