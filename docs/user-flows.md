# 核心用户流程（Phase 1 交付物）

> 状态：`code_complete`（待维护者确认）
> 定义三条 P0 核心流程（总纲 §13 Phase 1 任务 3）。流程中的每个节点都对应
> Phase 3-5 的可验收行为；节点标注（组件/动作）与组件规格、页面规格互相引用。

## 流程 1：单图编辑（打开 → 调整 → 应用 → 保存）

```
[首页/OS] --打开文件/拖放--> [EditorPage 画布显示]
    │ 文件：QFileDialog / dropEvent；Worker: image.open → document_id
    │ 失败：Toast 显示稳定错误码（UNSUPPORTED_FORMAT / FILE_NOT_FOUND）
    ▼
[画布查看] 缩放/平移/适配/100%/棋盘格（ImageCanvas）
    │ 状态栏：尺寸 · 缩放比 · 鼠标坐标
    ▼
[检查器·调整] 拖动亮度/对比度/饱和度/曝光/色相滑杆
    │ SliderField 变更 → 180ms 防抖 → filter.preview(低清 384px)
    │ 拖动停止 → 高清预览(768px)；预览带 version/request 标识
    │ 旧预览任务被取消/废弃，不得覆盖新预览
    ▼
[应用] 点击"应用" → filter.apply(document) → 全分辨率处理
    │ 后台任务；TaskItem 显示进度；可取消
    │ 完成 → HistoryModel 记录一步（可撤销）
    ▼
[撤销/重做] Ctrl+Z / Ctrl+Shift+Z
    │ HistoryModel：undo/redo/reset；大图快照受内存预算约束
    ▼
[保存] Ctrl+S / Ctrl+Shift+S
    │ image.save(document, path, format, quality)
    │ 成功：is_modified=false；失败：错误码 + 重试入口
    ▼
[结束] 关闭文档 → 未保存修改 → 确认对话框（保存/放弃/取消）
```

关键约束：

- 全程 UI 主线程零图像计算（总纲 §9）；预览与应用调用相同参数语义（§10.3）。
- 打开新文档/关闭工作区时，在途预览任务必须被取消或作废（document/version 关联检查）。

## 流程 2：滤镜处理（浏览 → 调参 → 组链 → 应用）

```
[检查器·滤镜页签] 分类浏览 + 搜索（FilterCard 网格）
    │ 数据：Worker capabilities.list / filter.list → FilterModel
    │ 不可用滤镜（缺依赖）显示置灰 + 原因
    ▼
[选择滤镜] FilterParameterGroup 按参数定义自动生成控件
    │ 实时预览（同流程 1 的防抖/两级分辨率/缓存）
    ▼
[加入滤镜链] FilterChainItem 列表（启用/禁用/排序/删除）
    │ 链预览：整链作为一次 filter.preview 调用（缓存 key = 链参数指纹）
    ▼
[应用链] filter.apply(chain) → 一次全分辨率执行
    │ 中途取消：处理器协作检查点（复用 CancelToken 语义）
    ▼
[预设] 保存当前链为预设 / 加载预设
    │ 预设持久化沿用 ~/.toolbox/filter_presets 语义，迁移到 SettingsService 管理的路径
    ▼
[结束] 应用结果进入历史；可继续叠加或撤销
```

关键约束：

- 预览结果、应用结果、取消行为三者一致（总纲 §9.3）；取消后 UI 回到应用前状态。
- 滤镜参数定义来自 Worker（FilterDef），UI 不硬编码任何滤镜参数表。

## 流程 3：批量处理（导入 → 配置 → 运行 → 检查结果）

```
[BatchPage] 导入目录/多选文件 + 拖放
    │ 文件列表：ImageThumbnail + 名称 + 状态（待处理/处理中/完成/失败/取消）
    ▼
[配置] 操作类型：格式转换 / 滤镜链（选择预设或现配）
    │ 输出目录、命名规则、格式与质量、覆盖策略
    ▼
[运行] 任务入队（TaskService）
    │ 整体进度 + 单项进度；单项取消 / 整队取消
    │ 失败项保留原因（错误码 + 消息），支持重试
    ▼
[完成] 摘要：成功 N / 失败 M / 取消 K
    │ "打开输出目录"入口；失败详情面板
    ▼
[结束] 页面状态持久化（最近输出目录）
```

关键约束：

- 批量任务在 Worker 内逐文件执行，UI 只消费进度/状态事件（节流）。
- Worker 崩溃时：未完成项标记"中断"，UI 提供重启 Worker 后重试（总纲 §6.5）。

## 异常路径（三条流程共用）

| 场景 | 行为 |
|---|---|
| Worker 未启动/崩溃 | 顶栏状态点变红；Toast 说明；提供"重试连接"；文档数据可从源文件重开的入口 |
| 任务失败 | TaskItem 显示错误码 + 可读消息；可复制详情 |
| 取消 | 状态 → cancelling → cancelled；UI 恢复到任务前状态 |
| 依赖缺失（G'MIC 等） | 相关功能置灰 + 诊断页指引；不弹错误风暴 |
| 大图（>100MP） | 预览强制降采样；应用任务提示预计耗时 |
| 不支持的格式 | 打开失败，错误码 UNSUPPORTED_FORMAT，无部分加载状态 |
