# Toolbox 2.0 — README 重写草稿

> 状态：草稿。Phase 8 仅在旧 README 上追加了下载安装节；本稿是面向 2.0 架构的
> 全量替换版，待 v2.0.0-alpha.1 发布后替换 `README.md`（保留 1.0 文档链接）。

---

# Toolbox

Linux 原生桌面专业图像工具箱：**单图编辑 · 滤镜与滤镜链 · 批量处理 · 生成器
创作（分形/纹理/着色器/渐变）· 文件工具（OCR/PDF/条码…）**。

2.0 版本将 1.0 的单进程 PySide6 应用重写为 **C++/QML 壳 + Python Worker
双进程架构**：界面（Qt 6 / Qt Quick）全程零图像计算，所有处理在独立
Python 引擎进程执行，通过 JSON Lines IPC 通信，支持后台任务、进度、取消
与依赖降级。

## 特性

- **八大工作区**：首页 / 编辑 / 创作 / 批量 / 分析 / AI / 文件工具 / 设置；
  全局命令面板（Ctrl+K）；Dark/Light/System 主题；布局与设置持久化。
- **核心编辑**：画布（缩放/平移/棋盘格/状态栏）、检查器调整滑杆（防抖两级
  分辨率实时预览）、后台应用（可取消）、撤销/重做、保存/另存。
- **滤镜系统**：FilterDef 声明式滤镜目录（78+ 内置，分类/搜索/依赖置灰），
  参数面板自动生成，滤镜链组合与预设（保存/加载/删除），预览与应用同参数语义。
- **参数化 undo**：滤镜链历史只存链参数（从基线重放），大图 undo 内存
  O(像素×历史) → O(参数)；连续滑杆调整自动合并为单条历史。
- **批处理**：文件/目录导入，纯转换或滤镜链，命名规则与质量可控，逐文件
  进度与失败隔离，非模态可取消。
- **创作 Studio**：Fractal（15 种 2D + Mandelbulb 3D）/ Texture / Shader /
  Gradient 统一工作区，`generate.list` 目录 + `generate.render` 渲染，
  产物一键发送到编辑器。
- **文件工具页**：32 个工具动作（OCR、PDF×8、条形码×3、ASCII、对比、
  校验和、直方图、LUT、媒体、EXIF、水印、归档、加密、Base64、AI×5）。
- **依赖诚实**：可选依赖缺失时功能置灰 + 原因说明（`DEPENDENCY_MISSING`），
  不假装可用；G'MIC / tesseract / poppler / AI 模型均为可选。

## 架构

```
┌────────────────────────┐  JSON Lines IPC   ┌──────────────────────┐
│  C++/QML 壳（Qt 6）     │ ◄───────────────► │  Python Worker        │
│  NavRail/页面/组件       │   动作 → 响应/进度  │  dispatcher + adapters│
│  Model/Service (native) │   任务可取消       │  processors/ 处理引擎  │
└────────────────────────┘                    └──────────────────────┘
```

- 协议：`docs/ipc-protocol.md`（动作表、错误码、兼容性规则，`protocol=1`）。
- 组件规格：`docs/ui-component-spec.md`；页面：`docs/ui-page-spec.md`。
- 处理引擎复用 1.0 的 `processors/` 资产（滤镜/分形/批处理/工具族）。

## 下载与安装

预编译包随 [Releases](https://github.com/emoeem/toolbox/releases) 发布（均捆绑 Python 运行时与 Worker 引擎，启动脚本首启自动预置后端配置）：

| 平台 | 产物 |
|---|---|
| Linux 通用 | `toolbox-<ver>-linux-x64.tar.gz`（GLIBC ≥ 2.35，运行 `./toolbox.sh`） |
| Linux AppImage | `toolbox-<ver>-linux-x64.AppImage`（免安装单文件） |
| Arch Linux | `toolbox2-<ver>-1-x86_64.pkg.tar.zst`（`pacman -U`，命令 `toolbox2`） |
| Windows x86_64 | `toolbox-<ver>-windows-x64.zip`（运行 `toolbox.bat`） |
| macOS arm64 | `toolbox-<ver>-macos-arm64.zip`（运行 `start.command`） |

### 从源码运行（Linux 推荐）

```bash
git clone https://github.com/emoeem/toolbox && cd toolbox
uv sync                                   # Python 侧依赖
uv run python main.py                     # 启动（自动拉起 native 壳）
# Wayland: QT_QPA_PLATFORM=wayland uv run python main.py
```

要求：Python ≥ 3.11、Qt ≥ 6.4（native 壳构建）、CMake ≥ 3.24。
可选依赖见下表，缺失自动降级。

| 依赖 | 能力 |
|---|---|
| `gmic` CLI | G'MIC 滤镜族 |
| pytesseract + tesseract | OCR |
| pdf2image + poppler | PDF 转图 |
| qrcode / pystrich / pyzbar | 条形码 |
| cryptography | 加解密 |
| AI 模型文件（EDSR 等） | AI 超分（`model_paths` 配置） |

## 从源码构建 native 壳

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
ctest --test-dir build          # native 单元测试
```

## 测试

```bash
uv run python -m unittest discover -s tests -v    # Python 侧（含 worker 协议/适配器）
ctest --test-dir build                            # native 侧（模型/服务）
```

CI（GitHub Actions）：`test`（Python 全量）+ `native`（Build + CTest）+
`format`（clang-format bot）三关；发布流水线 `release.yml` 三平台矩阵构建
打包（PyInstaller），`build.yml` 平台冒烟。

## 开发

- 分支模型与 CI 要求见 [CONTRIBUTING.md](CONTRIBUTING.md)；里程碑标签
  （`phase<N>-complete`）为回滚锚点。
- QML 组件一律 `App` 前缀（避开 Qt Quick Controls 冲突）；只引用 Theme
  令牌；组件不直接 sendAction（经 Service facade）。
- 协议改动三端同步（文档 / python_worker / native）。

## 文档索引

| 文档 | 内容 |
|---|---|
| [docs/architecture.md](docs/architecture.md) | 2.0 架构设计 |
| [docs/ipc-protocol.md](docs/ipc-protocol.md) | Worker 协议（动作/错误码） |
| [docs/ui-component-spec.md](docs/ui-component-spec.md) | 组件 API 契约 |
| [docs/user-flows.md](docs/user-flows.md) | 核心用户流程 |
| [docs/ui-migration-matrix.md](docs/ui-migration-matrix.md) | 1.0→2.0 迁移矩阵 |
| [docs/competitive-analysis.md](docs/competitive-analysis.md) | 竞品调研与行动项 |
| [docs/phase*-acceptance.md](docs/) | 各阶段验收清单 |

## 状态与许可

当前版本 **2.0.0-alpha.1**（预发布）：三平台 CI 构建通过；GUI 实机验收
进行中（各 phase 验收清单）。已知限制见 Release Notes。

License: Apache-2.0（与 ImageToolbox 一致）。
1.0 文档存档：单进程版说明见 `docs/` 历史版本与 CHANGELOG 2026-09 条目。
