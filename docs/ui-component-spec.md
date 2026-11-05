# 组件规格 / API 草案（Phase 1 交付物）

> 状态：`code_complete`（组件 API 草案，供 Phase 4 实现与评审）
> 约定：所有组件实现于 `ui/components/`，命名 `App*` 前缀避免与 Qt Quick Controls
> 冲突；继承/包装对应 Qt Quick Controls 类型；所有样式仅引用 Theme 令牌。
> 未列出的行为遵循 [ui-design-system.md] §4 的通用状态要求。

## 1. 基础组件

### AppButton（包装 Button）

| 成员 | 类型 | 说明 |
|---|---|---|
| `kind` | enum {Primary, Secondary, Danger, Ghost} | Primary 用 accent，仅页面一个主操作 |
| `loading` | bool | 显示 ProgressIndicator 并禁用 |
| `icon.name` | string | 可选左侧图标（Lucide 名） |

信号沿用 `clicked()`。尺寸：高度 32px（sm 28 / lg 40），内边距 `spacing.md`。

### IconButton / ToolButton

| 成员 | 说明 |
|---|---|
| `icon.name` | 必填；`Tooltip.visible` 由 hover 自动管理（延迟 500ms） |
| `checkable` / `checked` | 工具栏选中态用 accent 底 + onAccent 图标 |
| `badge.text` | 可选角标（如任务数） |

### SearchField（包装 TextField）

- 占位符、清除按钮（Esc 清空）、300ms 防抖 `searched(string)` 信号。
- Ctrl+K 聚焦全局命令面板（由 Main.qml 绑定）。

### TextField / NumberField

- NumberField：`value`/`from`/`to`/`decimals`/`step`；支持滚轮步进、
  ↑↓/←→ 微调；输入非法时 error 态 + `errorText`；数字渲染用 `typography.numeric`。

### SliderField（参数滑杆，滤镜/调整的主力控件）

| 成员 | 类型 |
|---|---|
| `label` / `value` / `from` / `to` / `step` | 数值 |
| `defaultValue` | 双击标签重置为默认值 |
| `dragging` | bool（只读）——驱动两级预览：拖动中低清，停止高清 |
| `suffix` | string（如 "°"、"%"） |

布局：标签行（label + 数值 NumberField）+ 滑轨。`valueModified()` 在拖动中节流发出，
`dragFinished()` 在释放时发出。

### SelectField / ColorField / ToggleField / SegmentedControl

- SelectField：包装 ComboBox，弹层用 `surfaceElevated` + `radius.md`。
- ColorField：色块按钮 + 弹出拾色器（hex/RGB 输入 + 常用色板）。
- ToggleField：Switch + label 整行可点击。
- SegmentedControl：互斥选项（如主题 深色/浅色/系统）。

### Tooltip / ContextMenu / Dialog / Toast

- Tooltip：统一延迟 500ms，`typography.small`，深浅主题都带 border。
- ContextMenu：菜单项统一高度 28px，快捷键右对齐显示。
- Dialog：模态 + `overlayScrim`；标题（heading）+ 内容 + 按钮区（主按钮在右）；
  Esc=取消，Enter=默认按钮；不可通过点击遮罩关闭需要明确决定的对�话框。
- Toast：右下角堆叠，5s 自动消失，类型 {info, success, warning, error}；
  error 类型带"复制详情"；最多同屏 3 条。

### ProgressIndicator

- determinate（任务进度）/ indeterminate（加载）两形态；inline 与 bar 两种用法。

## 2. 布局组件

### AppSidebar（NavRail）

| 成员 | 说明 |
|---|---|
| `model` | ToolCatalogModel 的顶层分类 |
| `expanded` | bool（持久化 `layout/navExpanded`） |
| `currentIndex` | 与页面路由双向绑定 |

P2 入口渲染为禁用项 + Tooltip"随 Phase 7 提供"。

### TopToolbar

- 左：文档操作组；中：历史组（撤销/重做）；右：缩放组 + 工作区上下文操作。
- 高度 `layout.toolbarHeight`；按钮用 ToolButton；分组间用 1px `border` 竖线。

### InspectorPanel

| 成员 | 说明 |
|---|---|
| `tabs` | 页签模型（调整/滤镜/信息…） |
| `collapsed` | bool（持久化 `layout/inspectorCollapsed`） |

固定宽 `layout.inspectorWidth`，内部滚动，分组用 SectionGroup。

### PanelHeader / SectionGroup

- PanelHeader：面板标题（heading）+ 右侧动作 IconButton 区。
- SectionGroup：可折叠参数分组（默认展开），折叠状态可选持久化。

### WorkspaceLayout

页面级骨架：提供 `emptyText`/`loading`/`error`/`backendDown` 插槽与
`content` 主区域；统一处理通用页面状态（页面规格 §6）。

### StatusBar

- 左：文档尺寸/色彩/鼠标坐标（numeric）；右：任务摘要（色点 + N 项进行中）。
- 点击任务摘要 → 展开 TaskQueuePanel。

### TaskQueuePanel（底部抽屉）

- TaskItem 列表 + 全局暂停/清按钮；抽屉高度持久化。
- 仅显示未过期任务；已完成任务 30s 后自动收起（可设置关闭）。

## 3. 业务组件

### ImageCanvas（Phase 2 原型已建，Phase 5 完善）

| 成员 | 类型 | 说明 |
|---|---|---|
| `documentId` | string | 当前文档 |
| `zoom` / `minZoom` / `maxZoom` | real | 1.0 = 100%；滚轮以指针为中心 |
| `fitMode` | enum {FitWindow, FitWidth, ActualSize} | |
| `showCheckerboard` | bool | alpha 图像默认 true |
| `mousePosition` | point（只读） | 图像像素坐标 |
| `previewVersion` | int | 显示哪个预览版本（防旧覆盖新） |

信号：`viewChanged()`、`imageDropped(url)`、`previewRequested()`。
实现：C++ QQuickItem + Scene Graph 纹理节点（禁止 QQuickPaintedItem 承载，总纲 §6/§10.2）。

### ImageThumbnail

- 异步加载 + 内存缓存；加载中显示 indeterminate；失败显示占位图标。
- 仅请求 Worker 生成的缩略图路径，不在 UI 线程解码原图。

### FilterCard

- 展示滤镜名/分类/可用性；不可用时置灰 + Tooltip 原因（如"需要 G'MIC"）。

### FilterParameterGroup

- 输入：FilterDef 参数定义 JSON（来自 Worker，类型 {float,int,bool,enum,color,point}）。
- 自动映射控件：float→SliderField、int→NumberField、bool→ToggleField、
  enum→SelectField、color→ColorField。
- 输出：`params` 对象（与协议 filter.preview/apply 的 params 完全一致）；
  任意变更 → `paramsChanged()`。

### FilterChainItem / TaskItem / HistoryItem / ToolCatalogItem

- FilterChainItem：启用开关、名称、参数摘要、上移/下移/删除；拖拽排序（Phase 6）。
- TaskItem：名称、状态色点、进度条、取消按钮；失败展开错误详情。
- HistoryItem：操作名 + 时间；当前节点高亮；点击跳转=连续 undo/redo（Phase 5）。
- ToolCatalogItem：图标、名称、分类徽标、收藏星标；进入对应工具流。

## 4. 组件与协议/模型的对接关系

| 组件 | 数据来源（C++ Model/Service） | 对应 IPC 动作 |
|---|---|---|
| AppSidebar / ToolCatalogItem | ToolCatalogModel | capabilities.list |
| FilterCard / FilterParameterGroup | FilterModel | filter.list / filter.preview / filter.apply |
| ImageCanvas | DocumentService | image.open / image.preview / image.save |
| TaskItem / TaskQueuePanel | TaskModel | task.cancel / task.query / task.progress 事件 |
| HistoryItem | HistoryModel | （C++ 侧记录，随 filter.apply/undo 协议扩展） |
| ImageThumbnail | ImageService | 缩略图文件（Worker 生成） |

> Phase 2 原型阶段仅实现：Theme、Main.qml 骨架、AppSidebar（静态数据）、
> ImageCanvas（本地文件显示）、ToolModel。其余组件随 Phase 4 实现。
