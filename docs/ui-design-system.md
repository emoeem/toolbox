# UI 设计系统（Phase 1 交付物）

> 状态：`code_complete`（设计规格文档；待维护者确认后作为 Phase 4 组件实现的依据）
> 依据：总纲第 7/8 章；色彩参考 Catppuccin Mocha（深色）+ 中性灰白（浅色）。
> 本文档的令牌值是唯一权威来源；`ui/themes/Theme.qml` 必须与本文档保持一致。
> 页面与组件中禁止出现本文件之外的颜色/字号/间距常量。

## 1. 视觉方向

- 中性、克制的专业创作工具风格：界面退后，图像内容优先。
- 深色主题以 **Catppuccin Mocha** 为基底，**Mauve (#cba6f7)** 仅作为少量强调色
  （选中态、主按钮、焦点环），禁止大面积使用。
- 浅色主题为中性灰白，强调色加深为 **#7c3aed**（Mauve 在白底上的可访问版本，
  对比度 ≥ 4.5:1）。
- 画布外围使用 `canvasBackdrop`（最暗/最中性层），避免界面底色污染对图像颜色的判断。
- 禁止：大面积渐变、荧光色、重阴影、玻璃拟态、装饰性动画。
- 阴影仅用于浮层（Dialog/Toast/Popover）：`shadow.float` 一档，克制使用。
- 动画只用于状态与层级过渡（120–320ms），不做纯装饰动画。

## 2. 设计令牌

### 2.1 颜色

| 令牌 | Dark 值 | Light 值 | 用途 |
|---|---|---|---|
| `color.background` | `#1e1e2e` | `#f7f7fb` | 应用窗口底色 |
| `color.surface` | `#181825` | `#ffffff` | 面板/侧栏/工具栏 |
| `color.surfaceElevated` | `#313244` | `#eef0f6` | 浮起卡片、输入框底、hover 面 |
| `color.border` | `#45475a` | `#d8dbe2` | 分隔线、控件描边 |
| `color.borderStrong` | `#585b70` | `#c2c6d1` | 输入框获得焦点前的高对比描边 |
| `color.textPrimary` | `#cdd6f4` | `#2b2d31` | 主文本 |
| `color.textSecondary` | `#a6adc8` | `#5c6370` | 次要文本、占位符、标签 |
| `color.textDisabled` | `#6c7086` | `#9aa0ad` | 禁用文本 |
| `color.accent` | `#cba6f7` | `#7c3aed` | 选中、主按钮、焦点环 |
| `color.accentHover` | `#b4befe` | `#6d28d9` | 强调色 hover |
| `color.accentPressed` | `#a78bfa` | `#5b21b6` | 强调色按下 |
| `color.onAccent` | `#11111b` | `#ffffff` | 强调色上的文字 |
| `color.success` | `#a6e3a1` | `#1a7f37` | 成功/完成 |
| `color.warning` | `#f9e2af` | `#9a6700` | 警告/降级提示 |
| `color.error` | `#f38ba8` | `#cf222e` | 错误/危险操作 |
| `color.canvasBackdrop` | `#11111b` | `#e8e9ee` | 画布周围中性底 |
| `color.checkerLight` | `#3a3d52` | `#d4d6de` | 透明棋盘格亮格 |
| `color.checkerDark` | `#2a2d42` | `#bfc2cc` | 透明棋盘格暗格 |
| `color.overlayScrim` | `#11111b` 70% | `#2b2d31` 40% | 模态遮罩（含 alpha 的 ARGB 写法见 Theme.qml） |

### 2.2 间距（4px 基准）

| 令牌 | 值 | 用途 |
|---|---|---|
| `spacing.xs` | 4px | 图标与文字微间距、紧凑内边距 |
| `spacing.sm` | 8px | 控件内边距、列表项间距 |
| `spacing.md` | 12px | 组件间标准间距 |
| `spacing.lg` | 16px | 分组间距、面板内边距 |
| `spacing.xl` | 24px | 区块间距、页面边距 |

### 2.3 圆角

| 令牌 | 值 | 用途 |
|---|---|---|
| `radius.sm` | 4px | 输入框、小按钮、复选框 |
| `radius.md` | 6px | 标准按钮、卡片 |
| `radius.lg` | 10px | 面板、对话框 |
| `radius.xl` | 14px | 大浮层、命令面板 |

### 2.4 字体排印

字体族由字体服务解析（见 [architecture.md] §7 与总纲 §11），规格只定义尺寸/字重/行高：

| 令牌 | 尺寸 | 字重 | 行高 | 用途 |
|---|---|---|---|---|
| `typography.title` | 18px | 600 | 24px | 页面标题 |
| `typography.heading` | 15px | 600 | 20px | 区块标题、面板头 |
| `typography.body` | 13px | 400 | 18px | 正文、列表项、按钮 |
| `typography.small` | 11px | 400 | 16px | 辅助说明、状态栏、标签 |
| `typography.numeric` | 13px | 400 | 18px | 数值输入、坐标、缩放比例（tabular 数字） |
| `typography.monospace` | 12px | 400 | 18px | 代码、路径、Checksum（等宽角色） |

### 2.5 动效

| 令牌 | 值 | 用途 |
|---|---|---|
| `motion.fast` | 120ms | hover/按下、控件状态 |
| `motion.normal` | 200ms | 面板显隐、页面切换 |
| `motion.slow` | 320ms | 大浮层、工作区切换 |
| `motion.easing` | `OutCubic` | 统一缓动 |

### 2.6 布局常量（页面规格共用）

| 令牌 | 值 | 用途 |
|---|---|---|
| `layout.navRailWidth` | 56px | 导航栏（仅图标态） |
| `layout.navRailWidthExpanded` | 200px | 导航栏（展开态） |
| `layout.inspectorWidth` | 300px | 右侧检查器默认宽 |
| `layout.toolbarHeight` | 44px | 顶部工具栏 |
| `layout.statusBarHeight` | 26px | 底部状态栏 |
| `layout.minWindowWidth` | 960px | 最小支持窗口宽 |
| `layout.minWindowHeight` | 600px | 最小支持窗口高 |

## 3. 组件体系（索引）

完整 API 见 [ui-component-spec.md](ui-component-spec.md)。三层结构：

- **基础组件**：AppButton、IconButton、ToolButton、SearchField、TextField、
  NumberField、SliderField、SelectField、ColorField、ToggleField、
  SegmentedControl、Tooltip、ContextMenu、Dialog、Toast、ProgressIndicator。
- **布局组件**：AppSidebar、TopToolbar、InspectorPanel、PanelHeader、
  SectionGroup、WorkspaceLayout、StatusBar、TaskQueuePanel。
- **业务组件**：ImageCanvas、ImageThumbnail、FilterCard、FilterParameterGroup、
  FilterChainItem、TaskItem、HistoryItem、ToolCatalogItem。

## 4. 组件状态要求（总纲 §8.4）

所有交互组件必须定义并测试以下状态（状态样式由令牌派生，不得各自定义颜色）：

| 状态 | 视觉规则 |
|---|---|
| Default | `surface`/`border` 基准 |
| Hover | 背景向 `surfaceElevated` 过渡（`motion.fast`） |
| Pressed | 背景加深一档；主按钮用 `accentPressed` |
| Focus | 2px `accent` 外环（键盘焦点必须可见，鼠标点击不显示焦点环） |
| Disabled | `textDisabled` 文本 + 40% 不透明度，不可交互 |
| Loading | 适用时：ProgressIndicator 替换/覆盖内容，控件保持禁用 |
| Error | 适用时：`error` 描边 + 可读错误文本（`typography.small`） |

键盘导航：Tab 顺序遵循视觉顺序；所有可点击组件响应 Space/Enter；滑杆响应
←/→ 微调、PgUp/PgDn 大步进；`Esc` 关闭浮层/取消预览。

## 5. 图标

- 使用单一开源线性图标集（发布前核对许可证，候选：Lucide，ISC），
  统一 1.5px 描边、24px 栅格，渲染尺寸 16/20/24px 三档。
- 不使用 Emoji 作为功能图标（Emoji 仅允许出现在用户文本内容中）。
- 图标颜色跟随 `textPrimary`/`textSecondary`，选中态用 `accent`。

## 6. 主题规则

- 主题仅切换令牌取值，不改变布局与组件结构。
- 主题切换不重置布局持久化、文档状态与任务状态（总纲 §11.4）。
- 深浅主题必须分别通过对比度检查：正文 ≥ 7:1，次要文本 ≥ 4.5:1，
  强调色按钮文字 ≥ 4.5:1。
- 画布预览区域永远使用 `canvasBackdrop`，与面板 `surface` 形成分层。
