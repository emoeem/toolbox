# 产品信息架构（Phase 1 交付物）

> 状态：`code_complete`（待维护者确认）
> 依据：总纲 §4.3/§9 与 [ui-migration-matrix.md](ui-migration-matrix.md)。
> 功能优先级以迁移矩阵为准；本文档定义导航结构与工作区归属。

## 1. 顶层导航

左侧固定 NavRail（56px 图标态，可展开为 200px），7 个一级入口 + 全局搜索：

```
Toolbox 2.0 导航树
│
├── 首页 Home              # 统一入口（总纲 §9.1）
├── 编辑 Editor            # 图像编辑工作区（默认工作区）
│     └── 检查器内含：调整 / 滤镜 / 滤镜链 / 裁剪变换 / 格式与信息
├── 创作 Create            # 生成器工作区
│     ├── Fractal Studio
│     ├── Texture Studio
│     ├── Shader Studio
│     └── Gradient / Photomosaic / Fusion
├── 批量 Batch             # 批处理工作区
├── 分析 Analyze           # P2：直方图 / 比较 / Checksum / 查找
├── AI                     # P2：AI 工具与模型管理
├── 文件工具 Files         # P2：PDF / OCR / EXIF / 水印 / 条码 / 压缩 / 归档 / 加密 / Base64
└── 设置 Settings          # 外观 / 工作区 / 性能 / 后端 / 外部依赖 / 存储 / 关于
```

规则：

- 导航项带真实功能状态徽标：P2 入口在 Phase 4-5 阶段显示"即将支持"
  （禁用态 + 说明），不允许显示可点击但无功能的假入口（总纲 §9.8）。
- 全局搜索（Ctrl+K 命令面板）覆盖：工具、页面、最近文件、滤镜名。
  搜索结果按"页面 > 工具 > 滤镜 > 最近文件"排序，支持关键词/分类/最近使用。
- 旧 UI 的 45 个侧栏工具按迁移矩阵归入上述工作区，不再以长列表形式平铺。

## 2. 页面清单与导航关系

| 页面 | 文件（计划） | 阶段 | 导航入口 | 说明 |
|---|---|---|---|---|
| HomePage | `ui/pages/HomePage.qml` | P0 核心 | 首页 | 最近文件、快速打开、常用工具、后端状态摘要 |
| EditorPage | `ui/pages/EditorPage.qml` | P0 核心 | 编辑 | 画布 + 检查器；文件工作流的宿主 |
| FilterInspector | `ui/components/FilterInspector*.qml` | P0 核心 | Editor 检查器页签 | 滤镜浏览/参数/链（编辑器内嵌，不独立成页） |
| BatchPage | `ui/pages/BatchPage.qml` | P1 | 批量 | 队列、进度、失败重试 |
| FractalPage | `ui/pages/FractalPage.qml` | P1 | 创作 > Fractal | 独立生成器工作区 |
| TexturePage | `ui/pages/TexturePage.qml` | P1 | 创作 > Texture | 独立生成器工作区 |
| ShaderPage | `ui/pages/ShaderPage.qml` | P1 | 创作 > Shader | 编辑器 + GL 预览 |
| GradientPage | `ui/pages/GradientPage.qml` | P1 | 创作 > Gradient | — |
| PhotomosaicPage / FusionPage | 同上 | P1 | 创作 | — |
| AnalysisPage | `ui/pages/AnalysisPage.qml` | P2 | 分析 | 直方图并入 Editor 检查器；比较/Checksum/查找在此 |
| AiPage | `ui/pages/AiPage.qml` | P2 | AI | 功能 + 模型管理 |
| FilesPage | `ui/pages/FilesPage.qml` | P2 | 文件工具 | 统一工具页模板（总纲 §9.9） |
| SettingsPage | `ui/pages/SettingsPage.qml` | P0 核心 | 设置 | 含后端与依赖诊断 |

关系约束：

- 编辑器是"文档中心"工作区：从首页/最近文件/拖放进入，携带当前文档。
- 创作工作区是"参数中心"：从参数生成图像，产物可"发送到编辑器"继续处理。
- 批量工作区是"文件中心"：不依赖当前打开的文档。
- 各工作区共享主题、字体、任务队列、对话框与参数组件（总纲 §13 Phase 6 原则）。

## 3. 主窗口区域划分（总纲 §4.2 的落地）

```
┌──────────────────────────────────────────────────────────────┐
│ TopToolbar（44px）：打开 保存 | 撤销 重做 | 缩放 | 工作区上下文操作 │
├───┬──────────────────────────────────────────────┬───────────┤
│ N │                                              │ Inspector │
│ a │              工作区内容区                     │  (300px,  │
│ v │   （画布 / 生成器预览 / 批量队列 / 设置表单）  │  可折叠） │
│   │                                              │           │
├───┴──────────────────────────────────────────────┴───────────┤
│ StatusBar（26px）：文档尺寸 · 缩放比 · 色彩信息 · 任务摘要      │
└──────────────────────────────────────────────────────────────┘
```

- 任务队列与日志不使用旧 UI 的 Dock 形态：任务摘要进 StatusBar + Toast，
  完整队列作为可展开的底部抽屉（TaskQueuePanel），由用户显式呼出。
- Inspector 仅在有上下文参数的工作区出现（Editor/Studio），首页/设置页隐藏。
- 面板显隐与宽度持久化（SettingsService `layout/*`）。

## 4. 信息架构与旧功能的对应（摘要）

详细逐项映射见 [ui-migration-matrix.md](ui-migration-matrix.md) 第 0-8 节。
本文件只约束"功能住在哪里"，矩阵约束"何时迁移、依赖什么、什么状态"。
两者冲突时，以迁移矩阵更新为准并同步修订本文档（总纲：三者保持一致）。

## 5. P2 入口的真实状态表达

Phase 4/5 交付时，Analyze / AI / Files 三个导航项：

- 显示但禁用，悬停 Tooltip 说明"随 Phase 7 提供"。
- 不渲染占位表单、假按钮、假开关（总纲 §3.4：不以占位实现冒充完成）。
- 对应状态写回迁移矩阵（`planned`），不写"已支持"。
