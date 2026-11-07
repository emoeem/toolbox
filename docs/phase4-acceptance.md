# Phase 4 验收清单（Linux 目标环境执行）

> 状态口径：Phase 4 = `code_complete`。单元级验证（新服务/模型 C++ 测试）已随
> CI 执行，但"设置/字体在真实 GUI 中生效、任务面板随 Worker 事件更新"必须在本
> 清单通过后才算 `runtime_verified`（总纲 §14.2）。
> 依赖：Phase 3 跨进程垂直切片（`docs/phase3-acceptance.md` §3）已通过。

## 1. 构建

```bash
cd ~/toolbox
cmake --build --preset linux-debug
```

- [ ] `toolbox` 可执行文件与全部测试目标编译成功，无警告新增
- [ ] 记录实际 Qt 版本（`toolbox` 关于页/`qtVersion`）与发行版：＿＿＿＿

## 2. CTest 全绿（新增 3 个 Phase 4 目标）

```bash
ctest --preset linux-ci --output-on-failure
```

- [ ] `native_models` / `ipc_protocol` 全部通过（既有）
- [ ] `task_model` 全部通过 —— BackendManager 信号驱动的建行/进度/终态/
      取消/64 条终结保留上限
- [ ] `settings_service` 全部通过 —— 默认值、读写往返、addRecentFile 上限
      10 与去重、resetLayout
- [ ] `font_service` 全部通过 —— resolveFamily 候选链回退（无字体环境自动
      skip）、diagnose 五类覆盖键结构
- [ ] 记录通过/跳过数：＿＿＿＿

## 3. GUI 启动

```bash
./build/linux-debug/toolbox
```

- [ ] 主窗口在目标环境（X11 与 Wayland 各一次）正常启动，无 QML 报错
- [ ] 导航栏 8 个入口可切换页面；P2 入口（分析/AI/文件工具）为禁用态 +
      Tooltip，不出现假控件
- [ ] 状态栏左侧实时显示 Worker 状态（未启动时为 `idle`，不谎称运行中）
- [ ] Ctrl+Q / 窗口关闭正常退出，退出码 0

## 4. 主题设置真实生效（SettingsService → Theme.darkMode）

- [ ] 设置 → 外观：深色/浅色/系统三态切换立即生效（`ui/Main.qml` 监听
      `SettingsService.themeMode`），界面无残留旧配色
- [ ] "系统"跟随桌面深浅偏好；会话内改系统主题后界面跟随
- [ ] 重启应用后主题保持（store：`~/.config/Emo/Toolbox2.conf` 的
      `appearance/themeMode`；非法值回落为 `system`）
- [ ] 切换主题不重置布局持久化与设置页其他表单状态（设计系统 §6）

## 5. 字体设置真实生效（SettingsService + FontService）

- [ ] 设置 → 外观：UI 字体族下拉列出已安装字体；等宽下拉含候选链
      （Maple Mono/JetBrains Mono 等，`FontService.monoCandidates()`）
- [ ] 选择字体并应用 → `FontService.resolveFamily` 解析、
      `applyToApplication` 全局生效，界面文字族/字号立即变化；未安装的族
      回退到候选链下一项，全空回退平台默认
- [ ] 字号非法输入（≤0）回落为默认 11（`resolve_size` 语义）
- [ ] 字体诊断面板：显示 resolved（QFontInfo）与 latin/digit/cjk/symbol/
      emoji 五类覆盖，未覆盖类列出回退族（≤8 项）
- [ ] 重启后字体族/字号保持（store：`font/family`、`font/mono`、
      `font/size`）；"恢复默认"重置字体三项

## 6. 布局持久化（SettingsService layout/*）

- [ ] 设置 → 工作区：显示当前 `layout/navExpanded` / `layout/inspectorCollapsed`
      值；"重置布局"后两者恢复 false 且重启保持
- [ ] 直接改 store 中的键（非法值）后重启，服务回落默认值，不崩溃
- [ ] 已知边界（如实记录）：导航栏展开/检查器折叠的控件尚未读写
      `layout/*` 键（`ui/components/AppSidebar.qml`、AppInspectorPanel 未
      接 SettingsService），折叠交互与写回随对应工作区页面交付；本阶段
      验收以 store 往返 + 设置页读写为准

## 7. 任务面板随 Worker 事件更新（TaskModel → AppTaskQueuePanel）

> **状态：Phase 3 验收后可验。** TaskModel 已由 Application 在启动时接线到
> BackendManager 信号（`application.cpp:16-17`），面板模型绑定
> `Application.taskModel`（`ui/Main.qml`）；但 UI 内暂无发起异步动作的入口
> （`ui/` 无 `sendAction` 调用），端到端行更新依赖 Phase 3 垂直切片可用 +
> 测试驱动构造事件。Phase 5 文件工作流接线后在真实操作流中复核本节。

- [ ] 设置 → 后端：配置 `backend/python` 与 `backend/repoRoot`，"启动后端"
      → 状态栏转 `ready`（Phase 3 验收通过后）
- [ ] 以测试驱动发起一个异步动作（如 `filter.preview`）→ 面板出现新行
      （queued → running → completed），进度条随 task.progress 事件更新
- [ ] 任务完成/失败后行进入终态（completed/failed，失败显示错误详情）；
      cancelled（task.failed + CANCELLED）显示为"已取消"而非"失败"
- [ ] 进行中任务点"取消" → 行变 `cancelling`，随后随 Worker 回报转
      `cancelled`；已完成任务的取消按钮无效
- [ ] 连续完成 65+ 个任务 → 面板保留最近 64 条终态，最早被裁剪
- [ ] Worker 事件停止（Worker 关闭）后面板不再变化，状态栏显示对应错误

## 8. 记录

- 构建/CTest 实际输出摘要、Qt 版本、桌面会话（X11/Wayland）、任务面板
  事件时序观察 → 回填本文件。
- 与 `docs/ui-component-spec.md` 组件规格的偏差逐条列出，并同步修订规格
  （总纲：文档与实现保持一致）。
