# Changelog

## 2026-11-07 (Phase 6A — 滤镜系统)

依据总纲 `docs/toolbox-2.0-project-plan.md` §7 Phase 6（滤镜系统与创作工作区）
迁移顺序的第 1-5 项，交付 docs/user-flows.md 流程 2（浏览 → 调参 → 组链 →
预览 → 应用 → 预设保存/加载）的真实滤镜垂直切片；第 6 项 G'MIC 本批仅交付
置灰机制（available/optional_deps → 卡片置灰 + 原因 Tooltip），G'MIC 滤镜库
本体、第 7 项 Batch 与各 Studio 不在本批。状态口径（总纲 §14.2）：本批全部为
**code_complete / static_reviewed**；Linux 目标环境验收清单见
`docs/phase6a-acceptance.md`（流程 2 端到端 / G'MIC 类滤镜置灰 / 预览防抖与
取消，实机项与 CI 已覆盖项分列），未执行任何目标环境运行验证；迁移矩阵
滤镜/滤镜链/LUT 相关行按其状态取值规则保持 **待迁移**
（ui-migration-matrix.md 头部与 Phase 6A 进度备注）。

> **CI 覆盖说明**：逻辑层验证已就位，随既有 CI 机制纳入执行——test job 的
> `unittest discover` 纳入 `tests/test_worker_presets.py`（15 用例：预设四动作
> 全路径——list 空初始/字段裁剪、save 往返/同名覆盖/非法名/非法 steps、load
> 往返/缺失/损坏文件/schema_version 超前、delete 往返/缺失/存储层 OSError，
> 其中 7 个用例为本批覆盖缺口核对后补齐）与既有
> `tests/test_worker_protocol.py` 的 filter.list/filter.preview/filter.apply
> 形状与任务路径；native job 的 CTest 新注册 `filter_model`（7 用例）、
> `filter_chain_model`（10 用例）、`filter_service`（7 用例）三目标。
> 截至本条目撰写 Phase 6A 改动尚未提交推送，推送后实际运行结果以
> GitHub Actions 为准；进程、GUI、QML 组件交互与真实预设目录项不在 CI 覆盖
> 内，必须实机（docs/phase6a-acceptance.md §2-§5）。

### Added（协议与 Worker）

- `docs/ipc-protocol.md`：§3 新增 `filter.presets.list / save / load /
  delete` 四个 sync 动作行 + §3.4（协议形状与错误码锁定；纯新增，
  `protocol` 保持 `1`，§8 兼容性规则；`filter.list` 结果行的
  `category_label` / `preview_supported` / `batch_supported` 字段为既有
  Worker 形状，本批未改动该行——文档行尚未列全这三个字段，如实维持现状）。
- `python_worker/adapters/filter_adapter.py`：预设协议化薄封装——复用
  `processors/filter_presets.py` 既有持久化（路径、原子写、schema_version
  管理原样，不重写存储逻辑）；`list_presets` 只暴露 {name, step_count}，
  `save_preset` 经 `FilterStep.from_dict` 逐项校验（有意不做 FilterDef 参数
  校验：预设允许引用当前环境不可用滤镜，§3.4）、`load_preset` 缺失 →
  `FILE_NOT_FOUND`、损坏/schema 超前 → `ENGINE_ERROR`、`delete_preset` 缺失
  如实 `FILE_NOT_FOUND` 不谎报成功。
- `python_worker/dispatcher.py`：动作表新增四动作（sync 纯接线，模式同
  image.metadata）；无 task_id、不产生任务行、与文档 version 无关（§3.4）。

### Added（C++ 服务与模型）

- `native/models/filter_model.{h,cpp}`：滤镜目录行模型（key/name/
  categoryLabel/paramsJson/available/optionalDeps/description 角色，
  HistoryModel::refreshFrom 同款整表重建模式；available 缺失按不可用处理——
  宁可置灰，不谎称可用；search 对名称与关键词做大小写不敏感包含匹配）。
- `native/models/filter_chain_model.{h,cpp}`：滤镜链行模型，行数据与协议
  steps 元素一一对应（{filter_key, params, enabled}，enabled 缺省 true）；
  编辑入口 replaceFrom/addStep/removeRow/moveUp/moveDown/setEnabled（越界
  静默、同值写入不发射 dataChanged——TaskModel::updateRow 同款防抖纪律），
  stepCount 仅在行数变化时通知。
- `native/services/filter_service.{h,cpp}`：滤镜页 facade（QML 单例，持有
  filterModel/chainModel）：loadFilters（loadingFilters 生命周期）、预设四
  动作 fire-and-forget（presetsList 缓存 + presetsChanged / presetSaved /
  presetLoaded 经 replaceFrom 写入链模型 / presetDeleted）、previewChain/
  applyChain 委托 `DocumentService::applyFilters`（组包 currentChainSteps 按
  链顺序序列化；QML 不 sendAction）。关联模式与 DocumentService 同款
  tracked dispatch，未跟踪帧（image.* 与 filter.preview/apply 的异步受理）
  一律不认领；未绑定后端如实 `filterError(INTERNAL)`，不伪造受理。
- `native/core/document_service.{h,cpp}`：新增 `applyFilters(steps, preview,
  maxSide)`——filter.preview / filter.apply 整链一次提交；空链/无文档本地
  拒绝（错误 + 恰好一次 documentActionFailed，QML 在途门控契约）；预览完成
  只发 previewReady 不改版本（§3.1），全分辨率完成 version+1 置 modified；
  任务行显示名"滤镜链"（预览/应用不分列，提交形态由 actionId 区分）。
- `CMakeLists.txt`：编入 filter_model / filter_chain_model / filter_service
  源文件与四个 AppFilter* QML 文件。

### Added（QML 滤镜页签，流程 2）

- `ui/components/AppFilterCard.qml`：滤镜卡片（名称/分类/可用性）；
  available=false 置灰（40% 口径、光标禁用、点击与 Space/Enter/Return 均
  无效）+ Tooltip 原因（optional_deps，如"缺少可选依赖：gmic"；依赖缺失
  兜底文案不点名具体依赖）；可用卡片 Tooltip 展示描述；选中态 accent 描边；
  基类有意选 Item 而非 AbstractButton（避免无参 clicked() 遮蔽带参信号）。
- `ui/components/AppFilterParameterGroup.qml`：FilterDef 参数定义 JSON →
  控件自动生成（float→AppSliderField、int→AppNumberField、bool→
  AppToggleField、enum→AppSelectField、color→AppColorField、string→
  AppTextField）；currentParams() 返回全部已声明参数（未改键取 default，
  "整表发送、Worker 兜底合并"）；畸形 JSON 清空面板不抛错；未知类型不进
  values（交 Worker 默认值）。
- `ui/components/AppFilterChainItem.qml`：链步骤行——启用开关（AppToggleField
  整行）、滤镜显示名（宿主传 key→名映射，未传如实显示 key）、参数摘要
  （空 params 显示"默认参数"）、上移/下移/删除；行内直调模型编辑入口 +
  clickedRow 信号双通道；拖拽排序未实现（↑/↓ 代替，已知限制）。
- `ui/components/AppFilterInspector.qml`：滤镜页签整体——搜索 + 卡片网格
  （FilterModel.search）→ 选中卡片 → 参数面板 + 加入链 → 链列表 → 预设行
  （保存/加载/删除，防自激闸门：presetsChanged 经 0ms Timer 延迟重读）→
  预览/应用按钮只发信号（防抖与在途门控归宿主页面）；链的任何变化经模型
  信号汇成 chainChanged()。
- `ui/pages/EditorPage.qml`：检查器增"滤镜"页签（ui-page-spec §2 页签：
  调整|滤镜）；链变化与 [预览] 按钮共用 300ms 防抖（filterPreviewDebounce），
  出口统一做空链/无文档/未就绪门检（换文档自动清链不弹错误 Toast）；应用链
  后链清空（与调整页签"应用后滑杆回中性"同一纪律，防已烘焙结果二次叠加）；
  fullResInFlight 在途门控扩展到 filter.apply（documentActionFailed 白名单
  只加 filter.apply——filter.preview 有意不进白名单：预览失败不触碰历史栈，
  提前解锁会重开竞态窗口，见 EditorPage.qml onDocumentActionFailed 注释与
  filter_service.h 的门控通道说明；preview/apply 本就是不同动作名，无
  "-preview" 后缀，见 document_service.cpp actionId()）；换文档时链
  replaceFrom([]) 作废待提交管线；FilterService.bindBackend
  与滤镜目录/预设缓存的就绪兜底补拉（onRunningChanged / onBackendReady）；
  FilterService 信号 → Toast 呈现。

### Added（测试）

- `tests/test_worker_presets.py`（新文件，15 用例，进程内 Dispatcher +
  TaskRuntime，存储重定向临时目录）：预设四动作全路径——list 空初始与
  {name, step_count} 字段裁剪、save 往返（enabled 缺省 true）/ 同名覆盖 /
  非字符串名 / 空白名 / 非法 steps（非数组 / 缺 filter_key / 元素非对象 /
  params 形状非法）、load 往返（FilterStep 字段一致）/ 缺失
  `FILE_NOT_FOUND` / 损坏文件与 schema_version 超前 `ENGINE_ERROR`、delete
  往返递减 / 缺失 `FILE_NOT_FOUND` / 存储层 OSError `ENGINE_ERROR`；其中
  7 个用例为本批覆盖缺口核对后补齐（非字符串名、同名覆盖、元素非对象、
  load/delete 非法名、损坏文件、schema 超前、存储 OSError）。
- `tests/native/test_filter_model.cpp`（新文件，7 用例，
  QAbstractItemModelTester）：角色名锁定、filter.list 协议形状解析（缺失
  available 按不可用）、整表重建、缺 key 条目跳过、搜索标题+关键词、大小写
  不敏感与空查询、越界 data（负行/越界行/带父索引的查询回答无效值不崩溃，
  TaskModel 同款扁平表契约）。
- `tests/native/test_filter_chain_model.cpp`（新文件，10 用例）：角色名锁定、
  replaceFrom（缺 key 跳过 / enabled 缺省 / 行数通知）、addStep 空 key 忽略、
  removeRow 越界静默、moveUp/moveDown 边界拒绝、移动后 chainIndex 刷新、
  setEnabled 同值防抖。
- `tests/native/test_filter_service.cpp`（新文件，7 用例，信号模拟不启动
  Worker，合成响应帧）：默认态与未绑定后端如实报错零上送、filter.list 填充
  模型与 loadingFilters 生命周期（失败响应收标志）、预设本地拒绝与四动作
  关联往返（真实预设存储往返由 tests/test_worker_presets.py 的临时目录重定向
  锁定）、空链/无文档委托拒绝、previewChain/applyChain →
  DocumentService.applyFilters → TaskModel 任务行 → §3.1 版本落定。
- `tests/native/CMakeLists.txt`：注册 `filter_model` / `filter_chain_model` /
  `filter_service` 三个 CTest 目标。

### Added（文档）

- `docs/phase6a-acceptance.md`：Linux 目标环境验收清单，明确"CI 已覆盖（§1）
  与必须实机（§2-§5）"的分工：流程 2 端到端（浏览/调参/入链/预览/应用/
  撤销/预设保存加载删除/持久化/错误降级/任务行）、G'MIC 类滤镜置灰（机制
  实机演练 + 现注册表无 optional_deps 声明的如实边界）、预览防抖与取消
  （防抖合并/时序、行内取消、同文档旧预览覆盖竞态的如实验收）、大图与
  在途门控。

### 已知限制（如实记录）

- AppFilterParameterGroup 参数类型与 ui-component-spec §3 偏差：规格写
  {float,int,bool,enum,color,point}，实现为 {float,int,bool,enum,color,string}
  ——无 point（当前注册表也无 point 参数），string 为实现补充；规格修订
  留待后续批次（docs/phase6a-acceptance.md §6）。
- 预览缓存未实现：流程 2"缓存 key = 链参数指纹"——Worker 返回 `fingerprint`
  字段但 UI 每次链变化都发新请求，无指纹命中；既有 PreviewCache 未接入
  Worker 管线（功能缺口，非缺陷）。
- 同文档旧预览覆盖竞态：旧预览任务完成可能覆盖新预览（previewReady 无版本
  序丢弃，filter.preview result 不含 version）；验收按 docs/
  phase6a-acceptance.md §4 如实复现或证伪后回填。
- AppFilterChainItem 拖拽排序未实现（↑/↓ 按钮代替，规格标注 Phase 6）。
- Esc 取消在途预览未实现（同 Phase 5 已知限制，取消入口只有任务抽屉行内
  按钮）。
- G'MIC 滤镜库本体未迁移（矩阵 §2 收敛到 backends/）；FilterDefRegistry
  现无 optional_deps 声明——标准环境下滤镜目录无现成置灰卡片，置灰机制以
  CI 合成条目 + 实机演练（临时声明，不提交）为证据。
- 检查器页签内无独立"缓存/指纹"指示（与预览缓存缺口一致）。

## 2026-11-06 (Phase 5 — 核心图像编辑工作流)

依据总纲 `docs/toolbox-2.0-project-plan.md` §7 Phase 5（核心图像编辑工作流，
5A 文件工作流 / 5B 画布接线 / 5C 基础编辑 / 5D 图像状态）交付真实可用的编辑
垂直切片。状态口径（总纲 §14.2）：本批全部为 **code_complete /
static_reviewed**；Linux 目标环境验收清单见 `docs/phase5-acceptance.md`
（垂直切片端到端 / undo 像素回归 / Worker 崩溃后 document_id 失效提示 /
大图不卡 UI / 取消行为），未执行任何目标环境运行验证；迁移矩阵相关行
按其状态取值规则保持 **待迁移**（ui-migration-matrix.md 头部）。

> **CI 覆盖说明**：逻辑层验证已就位，随既有 CI 机制纳入执行——test job 的
> `unittest discover` 纳入 `tests/test_worker_edit.py`（12 用例：adjust 预览/
> 全分辨率、transform 五 op、undo/redo/reset 往返与栈空 `UNREDOABLE` 同步
> 拒绝、history 演进与 redo 分支截断、历史深度淘汰不变量、`UNKNOWN_DOCUMENT`
> 路径、filter.apply 衔接）；native job 的 CTest 注册 `document_service`
> （21 用例：version/modified 状态机、reset 清 modified、异步动作受理登记
> TaskModel 任务行、undo/redo/reset 画布刷新文件、陈旧任务丢弃、HistoryModel
> 契约）。截至本条目撰写 Phase 5 改动尚未提交推送，推送后实际运行结果以
> GitHub Actions 为准；进程、GUI 与交互项不在 CI 覆盖内，必须实机
> （docs/phase5-acceptance.md §2-§6）。

### Added（协议与 Worker）

- `docs/ipc-protocol.md`：§3.1 文档版本（`version`：open=0，全分辨率变更与
  undo/redo/reset 各 +1，预览不递增——预览 `result.version` 为执行时的当前
  版本，与预览所据像素一致）、§3.2 `image.adjust` / `image.transform`
  （九调整键与五 transform op 的参数校验；§2.3 同步限定 undo/redo/reset 才
  携带画布刷新文件，adjust/transform 全分辨率 result 仅 version/width/height）、
  §3.3 `image.undo` / `image.redo` / `image.reset` / `image.history`（历史栈
  语义与 `UNREDOABLE` 提交前同步判定；`reset` 后 `modified=false` 两端一致）、
  §5 新增错误码 `UNREDOABLE`、§7 新动作纳入既有取消语义。`protocol` 保持 `1`
  （纯新增动作 + `filter.apply` 结果新增 `version` 字段，符合 §8 兼容性规则）。
  文档头部 Phase 4 增补注记已改写为既成事实表述（两端实现与两端测试已同步
  落地，"Worker 会按 UNKNOWN_ACTION 拒绝"的旧结论不再成立）。
- `python_worker/adapters/image_adapter.py`：`Document` 编辑状态（version /
  source_image / undo_stack / redo_stack / dropped_names）；`HistoryMixin`
  像素快照历史（30 条 + 512MB 预算、非栈顶变更截断 redo 分支，时机约束
  对齐旧 app `_push_history`，`app/main_window.py:346-374`）；淘汰保持 §3.3
  契约——底条目改写为源图共享引用（钉住 open 态，undo 到底恒回 open）、
  深度淘汰的动作名记入 `dropped_names` 供 history() 对齐条目名，redo 分支
  按重做顺序排列；`adjust_chain`（旧 app 调整顺序 + 近默认键剪枝）与
  `apply_transform`（rotate / flip_h / flip_v / scale / crop 直调
  `processors.core`，不重写算法）。
- `python_worker/dispatcher.py`：新增 async 动作 `image.adjust` /
  `image.transform` / `image.undo` / `image.redo` / `image.reset` 与 sync 动作
  `image.history`；参数形状、栈空、crop 越界在提交任务前同步报
  `INVALID_PARAMS` / `UNREDOABLE`；undo/redo/reset 共用恢复任务体（恢复像素 →
  `version`+1 → 写降采样画布刷新文件）；`filter.apply` 进历史并回传
  `version`。
- `python_worker/protocol.py`：新增错误码 `ERR_UNREDOABLE`。

### Added（C++ 服务与模型）

- `native/core/document_service.{h,cpp}`：文档/编辑状态 facade（QML 单例，
  QML 侧 `bindBackend` / `bindTaskModel` 接线）：`openDocument` / `saveDocument` /
  `adjust` / `transform` / `undo` / `redo` / `reset` / `requestHistory`；
  异步动作受理即经 `TaskModel.trackRequest` 登记任务行（任务抽屉/状态栏摘要
  与行内取消对编辑动作生效，§2.3）；version/modified 语义逐条对齐协议
  §3.1/§3.3（reset 完成清 modified，与 Worker 端一致）；`previewReady` 通道
  同时承载预览结果与 undo/redo/reset 的画布刷新文件（§3.3）；陈旧任务按提交
  时 documentId 丢弃（version 是旧任务结果丢弃依据）；新增
  `documentActionFailed(documentId, action)`：已跟踪动作未落定（提交前同步
  拒绝 / task.failed / 异步响应缺 task_id / 后端未绑定）时携带提交上下文，
  action 为协议动作名（预览带 "-preview" 后缀）——`documentError` 保持纯
  用户呈现，QML 在途门控只按 documentActionFailed 的双重上下文（当前文档 +
  全分辨率动作）解锁；未绑定后端 / 未开文档本地拒绝，不伪造受理；打开成功
  写入 `SettingsService.addRecentFile` 并对旧文档发 `image.close` 回收（在途
  豁免，见已知限制）。
- `native/backend/ipc_protocol.h`：稳定错误码表补齐 `kErrUnredoable`
  （与 docs/ipc-protocol.md §5 / python_worker/protocol.py 同步）。
- `native/models/history_model.{h,cpp}`：`image.history` 结果驱动的撤销历史
  行模型（histIndex / histName / histCurrent 角色 + canUndo / canRedo 属性，
  整表重建、空对象兜底清空）；条目名本地化归 QML 侧。
- `CMakeLists.txt`：编入 document_service 与 history_model 源文件及 include
  路径。

### Added（QML 编辑工作流）

- `ui/pages/EditorPage.qml` 由 Phase 2 原型（172 行：打开 + 显示 + 缩放平移）
  重写为真实编辑工作区（ui-page-spec §2）：打开 / 保存 / 另存为 FileDialog 与
  拖放；九滑杆调整检查器（中性基线与 Worker `_ADJUST_STEPS` 一致，gamma 中性
  1.0）；300ms 防抖预览 + dragFinished 立即预览（max_side 768）；应用后滑杆
  回中性基线（防叠加）；旋转 90° / 水平翻转 / 垂直翻转按钮；撤销 / 重做 /
  重置按钮随 HistoryModel canUndo / canRedo 启停，并与撤销/重做/重置/保存
  （含快捷键与另存为）一同受 `!fullResInFlight` 门控——全分辨率任务在途时
  暂停受理，避免多线程任务池下历史栈改写与保存像素的执行时序竞态；门控
  标志在换文档时（onDocumentOpened）显式作废（陈旧完成不发任何信号，旧
  文档 v0 时否则会永久卡死），解锁经 `documentActionFailed` 双重上下文限定
  于"当前文档的全分辨率提交失败"（旧文档失败按 documentId 忽略、同文档
  预览失败按 -preview 后缀忽略，均不得提前解锁）；撤销/重做/重置
  入口（按钮与 Ctrl+Z / Ctrl+Shift+Z）另受 backendReady 门控，Worker 未
  就绪时不再静默空操作；Ctrl+S / Ctrl+Shift+S 经保存对话框的
  ensureBackendReady 校验；状态栏 `宽×高 · vN` 与未保存 `●`；预览 URL 携带
  `?v=` 递增查询强制重载（同路径临时文件覆盖场景的可靠刷新）；Worker 未就绪
  Toast 与检查器降级横幅；任务摘要按钮 + AppTaskQueuePanel 抽屉复用。

### Added（测试）

- `tests/test_worker_edit.py`（新文件，12 用例，进程内 Dispatcher +
  TaskRuntime）：adjust 预览不改文档 / 全分辨率往返（undo→redo→reset 的
  sha256 像素对照）、transform 五 op（crop 改尺寸、scale 预览、flip_h/flip_v、
  rotate 像素变化可撤销）、栈空 undo/redo 同步 `UNREDOABLE`、未编辑文档
  reset、unknown document 的同步与异步错误路径、history 演进与 redo 分支
  截断、历史深度淘汰（底条目钉住源图、条目名对齐、redo 分支按重做顺序）、
  filter.apply 衔接、参数校验。其中 rotate / UNKNOWN_DOCUMENT / 未编辑
  reset / 深度淘汰四个用例为本批补齐（覆盖缺口核对后新增）。
- `tests/native/test_document_service.cpp`（新文件，21 用例，与
  test_task_model 同款信号模拟、不启动 Worker）：DocumentService 打开/保存/
  调整/变换/撤销的 version 与 modified 状态机（reset 清 modified、保存失败
  保持脏标记）、异步动作受理登记 TaskModel 任务行（bindTaskModel）、预览不
  触状态、undo/reset 完成携带画布刷新文件、本地拒绝与协议违约如实上报、
  未落定动作发 documentActionFailed（提交 documentId + 动作标识，预览带
  -preview 后缀）、陈旧任务丢弃、addRecentFile 副作用；HistoryModel 刷新/
  角色名/空历史兜底。
- `tests/native/CMakeLists.txt`：注册 `document_service` CTest 目标。

### Added（文档）

- `docs/phase5-acceptance.md`：Linux 目标环境验收清单，明确"CI 已覆盖
  （§1）与必须实机（§2-§6）"的分工：垂直切片端到端、undo 像素回归（与
  Phase 0 引擎基线的关系与无 GUI sha256 核对脚本）、Worker 崩溃后
  document_id 失效提示、大图不卡 UI、取消行为、最近文件。

### 已知限制（如实记录）

- crop / scale 协议与 Worker 已支持，EditorPage 尚无 UI 入口（本批仅旋转
  90° / 翻转按钮）。
- ui-page-spec §2 的"Esc 取消在途预览"未实现（ImageCanvas 无 Esc 处理）；
  取消入口当前只有任务抽屉行内按钮（TaskModel.cancelTask → task.cancel）。
- Worker 崩溃后 BackendManager 不反向清空 DocumentService.currentDocumentId
  （document_service.cpp 未连接 errorOccurred）：崩溃到下一次操作之间 UI 仍
  显示旧文件名与旧状态，旧 document_id 的失效提示依赖下一次操作的
  `UNKNOWN_DOCUMENT` 错误兜底（docs/phase5-acceptance.md §4 如实验收）。
- HomePage 最近文件行为只读展示（点击打开未接线，打开入口在 EditorPage）。
- 非 crop 的 `image.adjust` / `image.transform` 遇未知 document 在任务体内
  才失败，任务运行时把任务体异常统一归一为 `ENGINE_ERROR`
  （WorkerError.code 不进 task.failed 事件）；undo/redo/reset/history 与
  crop 的未知文档为提交前同步 `UNKNOWN_DOCUMENT`。测试按现状断言
  （tests/test_worker_edit.py test_unknown_document_rejected_for_edit_actions）。
- 检查器仅"调整"页签（含伽马共 9 个滑杆；ui-page-spec §2 列 8 个、无伽马）；
  检查器内无[重置]按钮——重置为工具栏入口、语义为 §3.3 重置到源图，
  ui-page-spec §2 的检查器[重置]"回滚到已应用状态"未实现且语义不等价；
  ui-page-spec §2 对应行修订与加载态表述修订同批进行
  （docs/phase5-acceptance.md §8 如实记录）；滤镜页签（流程 2）随 Phase 6
  滤镜系统交付。
- 换文档时的 `image.close` 回收有在途豁免：旧文档仍有在途任务（如在途
  保存）时跳过本次回收（close 会把合法任务打成 `UNKNOWN_DOCUMENT` 失败），
  被跳过的旧文档随下次切换或 Worker 退出回收
  （docs/phase5-acceptance.md §8 偏差 2）。
- 大图打开首帧为 GUI 线程本地同步解码（ImageCanvas::setSource），40MP 级
  阻塞可达秒级；预览/应用/撤销阶段保持主线程零像素计算。打开链路异步化与
  ui-page-spec §2 加载态表述修订留待后续批次
  （docs/phase5-acceptance.md §5/§8 偏差 1）。

## 2026-11-06 (Phase 4 — 新 UI 基础设施与应用壳)

依据总纲 `docs/toolbox-2.0-project-plan.md` Phase 4 任务清单完成：统一 UI
系统、基础组件库、设置/字体服务与任务队列。状态口径（总纲 §14.2）：本批
全部为 **code_complete / static_reviewed**；Linux 目标环境验收清单见
`docs/phase4-acceptance.md`，其中"任务面板随 Worker 事件更新"在 Worker 未
接入前如实标注 **Phase 3 验收后可验**，未执行任何目标环境运行验证。

> **CI 状态更新（同日后续）**：`phase4-ui-infra` 分支已达 **双 job 全绿**
> （test：307 Python 测试 + ruff；native：Build 零错误 + CTest 5/5 +
> clang-format 通过）。过程中 CI 实证修复：5 处编译错误（头文件路径、const
> 正确性、qmltyperegistrations include）、2 处运行期模型缺陷（TaskModel 空
> 变化发射、SettingsService 测试隔离失效——`setPath(IniFormat)` 不影响
> NativeFormat 实例，已改为显式 IniFormat 构造）、3 个 low 评审发现（mono
> 候选链补齐、Ctrl+Q 快捷键、NumberField 悬停穿透）。另：旧测试套件退出期
> heap corruption 经 gdb 与 main 对照组证实为 **main 既有缺陷**，以
> tearDownModule 收集 + CI 端 os._exit 绕过处理；CI 增设 clang-format
> 自动格式化机器人（PointerAlignment 修正为 Right）。Linux 实机 GUI 验收
> 仍待 `docs/phase4-acceptance.md` 执行。

### Added（C++ 服务与模型）

- `native/services/settings_service.{h,cpp}`：QSettings("Emo","Toolbox2")
  扁平键值外观（QML 单例）。键位与默认值见头文件键表：主题模式
  dark/light/system（默认 system，非法值归一化）、布局持久化
  layout/navExpanded 与 layout/inspectorCollapsed、字体 font/family 与
  font/mono 与 font/size（默认 11，镜像 app/fonts.py resolve_size）、
  preview/quality、tasks/concurrent、backend/python 与 backend/repoRoot
  （`Application::startBackend()` 经 value() 读取）。每次写入后 sync()；
  `addRecentFile` 最近文件去重置顶、上限 10；`resetLayout` 仅复位布局组；
  破损存储值回落默认而不传播。
- `native/services/font_service.{h,cpp}`：字体角色解析与诊断（QML 单例），
  镜像 app/fonts.py 语义——空族=平台默认、UI 走 SansSerif+抗锯齿+完全
  hinting、等宽走 Monospace hint；`resolveFamily` 候选链回退（sans/mono
  候选链内置于服务，与设置页共享）；`applyToApplication` 全局应用字号
  （非正值回落 11）；`diagnose` 返回 ui/mono 两段的 requested/resolved/
  size/coverage/fallback，coverage 固定五类（latin/digit/cjk/symbol/
  emoji），未覆盖类给出 ≤8 项回退族。
- `native/models/task_model.{h,cpp}`：Worker 驱动的任务行模型
  （QAbstractListModel）。trackRequest 记录 request_id→任务名；成功响应
  携带 result.task_id 建行（未跟踪/失败/同步响应不建行）；task.progress
  更新进度（夹取 0-100）；task.completed / task.failed 终态，CANCELLED
  呈现为 cancelled 而非 failed；cancelTask 将活跃行置 cancelling 并转发
  BackendManager，终态行本地拒绝（协议 §7）；终态行保留上限 64、FIFO
  裁剪且永不裁剪活跃行。角色名 taskTaskId/taskName/taskStatus/
  taskProgress/taskError 与 AppTaskItem.qml 契约一致。
- `Application` 扩展：暴露 taskModel/settingsService/fontService 属性与
  `startBackend()`（从 SettingsService 读取 backend/* 后配置并启动
  BackendManager）。

### Added（QML 组件库与应用壳接线）

- `ui/components/` 28 个 App 前缀组件（基础/布局/业务三层，全部仅引用
  Theme 令牌）：AppButton、AppIconButton、AppToolButton、AppTextField、
  AppNumberField、AppSliderField、AppSelectField、AppColorField、
  AppToggleField、AppSegmentedControl、AppSearchField、AppTooltip、
  AppContextMenu、AppDialog、AppToast、AppProgressIndicator、
  AppPanelHeader、AppSectionGroup、AppInspectorPanel、AppSidebar、
  AppTopToolbar、AppStatusBar、AppWorkspaceLayout、AppTaskItem、
  AppTaskQueuePanel、AppHistoryItem、AppImageThumbnail、
  AppToolCatalogItem。
- `ui/Main.qml`：SettingsService.themeMode 驱动 Theme.darkMode；状态栏
  实时显示 BackendManager 状态；AppTaskQueuePanel 底部抽屉绑定
  Application.taskModel。
- `ui/pages/SettingsPage.qml`：外观（主题三态、字体族/字号、字体诊断）、
  工作区（布局持久化状态 + 重置布局）、后端（python/repoRoot 配置、
  启动按钮、Worker 状态）四个分区真实读写服务；HomePage 接入
  SettingsService.recentFiles 最近文件（只读展示）。

### Added（测试）

- `tests/native/test_task_model.cpp`：以真实 BackendManager（不启动
  Worker）直接 emit responseReady/taskEvent 信号模拟协议事件，覆盖建行
  条件、进度夹取、终态/取消呈现、cancelTask 转发与终态拒绝、64 条终结
  保留上限与活跃行保护；角色名断言锁定 QML 契约。
- `tests/native/test_settings_service.cpp`：QTemporaryDir 隔离 store 的
  默认值、读写往返、信号去重、破损存储回落、主题归一化、addRecentFile
  空值/去重/上限 10、resetLayout 仅动布局组。
- `tests/native/test_font_service.cpp`：resolveFamily 候选链回退（无字体
  环境 QSKIP，镜像 tests/test_fonts.py 口径）、diagnose ui/mono 五类覆盖
  键结构与回退列表上限、非正字号回落 11、applyToApplication 全局应用。
- `tests/native/CMakeLists.txt` 注册 task_model / settings_service /
  font_service 三个 CTest 目标（与既有两目标同一模式：被测源文件直接
  编入测试目标）。

### Added（文档）

- `docs/phase4-acceptance.md`：Linux 目标环境验收清单（构建、CTest 全绿、
  GUI 启动、主题/字体设置真实生效、布局持久化、任务面板随 Worker 事件
  更新——Worker 未接前如实标注 Phase 3 验收后可验）。

### 已知限制（如实记录）

- 任务面板行更新在真实操作流中不可验：UI 内尚无发起异步动作的入口，
  端到端复核依赖 Phase 3 垂直切片可用，接线随 Phase 5 文件工作流完成。
- AppSidebar/AppInspectorPanel 尚未读写 layout/* 键（折叠交互随对应
  工作区页面交付），本阶段布局持久化以 store 往返与设置页读写为准。
- 设置测试的 store 隔离依赖 Linux 原生格式为 INI（QSettings::setPath
  重定向）；Windows 原生格式为注册表，重定向不生效。

## 2026-11-06 (Phase 1-3 — 设计系统、Qt Quick 原型与 Worker/IPC)

依据总纲 `docs/toolbox-2.0-project-plan.md` 完成三个阶段的代码/文档工作。
状态口径（总纲 §14.2）：本批全部为 **code_complete / static_reviewed**；
Linux 目标环境验收见 `docs/phase2-acceptance.md`、`docs/phase3-acceptance.md`，
未执行任何目标环境运行验证。

### Phase 1（设计交付物，全部为文档）

- `docs/ui-design-system.md`：设计令牌定稿（Catppuccin Mocha 深色 + 中性浅色、
  Mauve 强调色的可访问浅色变体）、间距/圆角/字排/动效/布局常量、组件状态与
  可访问性要求。
- `docs/product-information-architecture.md`：导航树、页面清单与导航关系、
  主窗口五区布局、P2 入口的诚实状态表达。
- `docs/user-flows.md`：三条 P0 核心流程（单图编辑/滤镜处理/批量处理）+
  共用异常路径。
- `docs/ui-page-spec.md`：P0 四页与 P1 Studio 页的布局规格与状态定义。
- `docs/ui-component-spec.md`：组件库 API 草案（基础/布局/业务三层）及与
  IPC 动作的对接关系。
- `docs/toolbox-2.0-project-plan.md`：总纲存档（附录 A 指定路径）。

### Phase 2（C++ / Qt Quick 技术原型，code_complete）

- 构建体系：根 `CMakeLists.txt`（Qt ≥ 6.4 下限 / C++20 / 预留 Phase 3 backend
  源）+ `CMakePresets.json`（linux-debug / linux-release / linux-ci）。
- C++：`native/app/`（main.cpp、Application QML 单例：导航/工具目录/页面路由/
  版本信息）、`native/models/`（ToolModel + NavModel，QAbstractListModel +
  QAbstractItemModelTester 契约测试）、`native/graphics/`（ImageCanvas：
  QQuickItem + QSGSimpleTextureNode，滚轮指针锚定缩放/拖动平移/双击适配/
  100%/图像空间棋盘格合成，纹理仅在 updatePaintNode 上传）。
- QML：`ui/themes/Theme.qml`（与设计系统文档逐令牌对应的单例）、
  `ui/Main.qml`（令牌驱动的应用壳 + Loader 路由）、`ui/components/AppSidebar.qml`
  （P2 项禁用 + 阶段标注）、`ui/pages/`（Home/Editor 真实骨架；Batch/Fractal/
  Shader/Texture/Planned 为诚实计划状态页；Settings 含可用的主题切换）。
- 质量工具：`.clang-format`（Qt 风格）、`.clang-tidy`（保守基线）。
- 测试：`tests/native/test_models.cpp`（模型契约 + QML 角色名锁定）。

### Phase 3（Python Worker 与 IPC 垂直切片，code_complete）

- 协议：`docs/ipc-protocol.md`（JSON Lines、消息形状、动作表、错误码、
  握手/崩溃恢复/取消语义、版本策略、临时文件数据传递规则）。
- Python 侧 `python_worker/`：`protocol.py`（编解码/校验/错误码）、
  `task_runtime.py`（线程池 + queued/running/completed/failed/cancelling/cancelled
  状态机 + 100ms 进度节流 + 复用 processors.cancellation.CancelToken）、
  `dispatcher.py`（同步/异步动作表：worker.hello/shutdown、capabilities.list、
  image.open/close/metadata/save、filter.list/preview/apply、task.cancel/query）、
  `adapters/`（DocumentStore 文档表 + FilterDefRegistry/FilterChain 协议化，
  import processors 仅发生在适配层）、`main.py`（stdin 主循环、双运行方式
  bootstrap、信号优雅退出；stdout 只写协议消息，日志走 stderr）。
- C++ 侧 `native/backend/`：`ipc_protocol.{h,cpp}`（消息构造/分类/校验/错误码）、
  `python_worker.{h,cpp}`（QProcess + 行分帧 + stderr 尾部留档）、
  `backend_manager.{h,cpp}`（握手超时 5s、崩溃检测与 ≤3 次自动重启、
  Stopped 状态不误报崩溃、request_id 关联）。
- 测试：`tests/test_worker_protocol.py`（编解码/分发/异步任务/取消/节流，
  纯进程内、CI 可跑）、`tests/native/test_ipc_protocol.cpp`（消息形状锁定）。
- CI：新增 `native` job（ubuntu + 发行版 Qt 6 开发包：CMake preset 构建、
  clang-format 门禁、clang-tidy 咨询性检查、CTest）。

### 已知限制（如实记录）

- C++/QML 代码未在任何环境编译运行（Windows 侧无 Qt 工具链，按总纲 §15.3
  不搭建）；编译期错误风险由 CI `native` job 兜底。
- 垂直切片的 QML 交互接线（编辑器按钮直接调用 BackendManager）未实现——
  Phase 3 验收允许以 C++ 测试驱动，QML 全面接线归 Phase 4。
- Worker `image.open` 当前为同步动作（大图打开会占一个任务线程直至完成），
  异步化列入 Phase 4 任务清单。

## 2026-11-05 (Phase 0 — 字体系统修复与迁移基线)

Toolbox 2.0 升级的 Phase 0（升级计划见 `docs/upgrade-plan.md`）：修复字体
强制覆盖体系，建立 UI 迁移所需的架构文档与引擎行为基线。

### Changed（字体系统）

- **删除 QSS 全局字体强制**（`app/theme.py`）：浅色/深色两处
  `* { font-family: "MiSans"...; font-size: 13px }` 移除。此前该规则覆盖
  `QApplication.setFont()`，导致设置中的字体族与字号均不生效。
- **删除启动时全目录字体扫描**（`app/fonts.py`）：`ensure_packaged_misans()`
  每次启动对 `~/.local/share/fonts`、`/usr/share/fonts`、`~/.fonts` 递归
  `rglob` 查找 MiSans 的逻辑整体移除。
- **`app/fonts.py` 重写**：默认字体改为系统默认（空 family → 平台
  fontconfig/平台解析），MiSans 不再硬编码为首选与默认值；等宽字体新增
  `mono_font()`（候选链 Maple Mono/JetBrains Mono 等 → `QFont.Monospace`
  hint 系统等宽回退），并新增诊断接口 `glyph_coverage()` /
  `fallback_candidates()` / `diagnose()`（基于 QFontInfo/QRawFont，可查询
  中文/英文/数字/符号/Emoji 的实际解析与回退，对应"字体最终解析结果可诊断"）。
- **等宽字体设置真正生效**：Shader Studio 代码编辑器由硬编码
  `QFont('Maple Mono',11)`（`app/panels/shader_studio.py`）改为接收
  `mono_font(settings)` 解析结果。
- **设置对话框**（`app/main_window.py`）：字体/等宽下拉框新增"(系统默认)"
  项（存空值）；保存改用 `currentData()`，修复选中具体字体时误存显示文本的
  隐患；"恢复默认"现在同时重置字体三项（此前遗漏字体）。

### Fixed（测试）

- `tests/test_fonts.py` 重写：删除"QSS 必须含 MiSans"的强制断言；改为断言
  主题不强制字体族/字号/不含 MiSans，并新增系统默认解析、显式族应用、缺失
  回退、等宽 hint/应用、五类字符覆盖与诊断结构的真实解析测试（无字体环境
  自动 skip，兼容 CI 容器）。

### Added（迁移基线）

- `tools/make_test_samples.py`：4 张确定性测试样本（渐变/棋盘/噪声/合成，
  固定参数与种子，不依赖外部图片）。
- `tests/test_engine_baseline.py`：核心引擎行为基线 —— 样本哈希 + 42 个
  core 算子输出 + save/load 往返的 sha256 对照（`TOOLBOX_REGEN_BASELINE=1`
  重新生成；平台标签含 Python 版本与 numba 状态，环境不一致时 skip 不误报）。
  首次在 Linux 虚拟机运行后提交 `tests/baselines/engine_baseline.json`。
- `docs/architecture.md`：现状架构分析（MainWindow 上帝对象、4 种 processors
  调用模式、线程/取消体系、撤销、持久化、已知隐患，全部带 file:line 证据）。
- `docs/ui-migration-matrix.md`：全部 UI 功能 → 2.0 八大工具类 → 目标 Phase
  的迁移矩阵，含外部依赖汇总与未实现功能真实状态标注。

## 2026-09-29 (第三轮 — 手工运行发现的崩溃)

实际运行 `main.py` 时暴露的一批"点击才触发"的缺陷。这类问题不会被单元测试
发现，因为没有任何测试会去点那些按钮 —— 已补充静态与生命周期回归测试。

### Fixed

- **`self.preview.get_image()` 不存在（14 处调用点，13 个功能全部报
  `AttributeError`）**。`ImagePreview` 的访问器是 `current_image()`，
  `get_image()` 从未存在过。受影响：图像对比、差异图、图像校验和、条码/二维码
  解码、形状遮罩、直方图、拼接/拼贴/分割、LUT 预设、曲线预设、智能缩放
  （preset/custom/size）。全部改为 `current_image()`。
- **3 处 `NameError`（模块未导入）**：
  - `_apply_lut_preset()` 使用裸 `lut.`，但只导入了 `LUT_PRESETS`，且 `lut`
    仅在**另一个**函数里局部导入 —— 运行时 `NameError: name 'lut' is not defined`；
  - `_make_mesh_grad()` 使用裸 `gradients.`（同样只导入了 `MESH_PRESETS`）；
  - 批量转换的 `conv_worker()` 使用裸 `utils.load_image/save_image`，改用模块级
    已导入的 `load_image` / `save_image`。
- **撤销 / 重置在切换工具后崩溃**
  `RuntimeError: libshiboken: Internal C++ object (QListWidget) already deleted`。
  面板在切换工具时通过 `setParent(None)` + `deleteLater()` 销毁，但 Python
  属性仍指向已析构的 C++ 对象；`undo()` / `reset_all()` 是跨面板可达的
  （前者还有全局快捷键），因此 `_refresh_chain_list()` 与
  `filter_param_widget.reset_to_defaults()` 会踩到已删除对象。
  原有 `hasattr(self, '_refresh_chain_list')` 这类守卫是无效的 —— 方法一直存在，
  需要检查的是 **widget 本身是否还活着**。新增 `_widget_alive()`
  （基于 `shiboken6.isValid`）并在两处加守卫。

### Added — Tests

- `tests/test_main_window_static.py`（5 项）：
  - `test_every_preview_method_used_exists` —— 扫描 `main_window.py` 里所有
    `self.preview.<名字>`，断言它们在 `ImagePreview` 上真实存在（可捕获本次
    14 处同类缺陷）；
  - `test_main_window_module_references_are_imported` —— AST 逐函数分析，
    断言函数内用到的 `processors` 子模块在该作用域可见（可捕获本次 3 处
    `NameError`，且能区分"在别的函数里导入过"这种假阴性）；
  - 生命周期用例：切换面板销毁 Filter panel 后 `undo()` / `reset_all()` 不得抛错，
    以及从未构建 Filter panel 时 `reset_all()` 可用（preview 的 Esc 快捷键路径）。

两个静态用例都做过变异验证：把 `get_image()` 或未加守卫的
`self._chain_list.clear()` 放回去，对应用例立即失败。

### Verification

- `QT_QPA_PLATFORM=offscreen TOOLBOX_NO_NUMBA=1 .venv/bin/python -m unittest discover -s tests`
  → **268 tests / OK（1 skipped）**
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_fractal tests.test_filter_robustness tests.test_core` → 56 tests / OK
- `_smoke_test.py` → ALL SMOKE TEST PASSED
- 逐个驱动真实 UI 处理函数验证（对比 / 差异图 / 校验和 / 条码 / 直方图 /
  形状遮罩 / 拼接 / 拼贴 / 分割 / LUT / 曲线 / 智能缩放 x3）均已通过。

---

## 2026-09-29 (第二轮 — 代码审查 / Bug 修复 / 性能优化)

审查范围：全仓库约 12.5k 行。所有结论均由可重复命令或实测数据支撑；详见
[`docs/code-review-fixes.md`](docs/code-review-fixes.md)。

### Fixed — 严重正确性

- **`processors/core.py` `contrast()` 公式漏除 255**（未提交改动引入）：对比度系数被放大约 255 倍，
  把图像压成约 3 个色调。实测 89488 色 → 20 色；任何"应用调整"都会破坏图像。
  修复后与参考曲线**逐像素完全一致**。
- **`processors/core.py` `hue_shift()` 用 `% 180` 环绕**：输入为 float32 时 OpenCV hue 量程是
  0..360（uint8 才是 0..180），导致色相环被折半 —— `+180°` 对红/绿完全无效，H≥120 的色相全部错位。
  改为 `% 360`，12 个色相带 × 6 种偏移全部校验通过。
- **`processors/filter_defs.py` `FilterDef.apply()` 吞掉真实 `TypeError`**：`except TypeError`
  无法区分"处理器不接受该关键字参数"与"处理器内部抛 TypeError"，会把滤镜**用默认参数重跑一遍**，
  静默产出错误结果。改为用 `inspect.signature` 过滤参数，错误立即上抛（调用次数 2 → 1）。
- **撤销（Undo）对滤镜/变换路径完全失效**：`_push_history()` 在 `set_display()` 之后调用，
  快照的是**新图**，撤销等于空操作。重构为 `_commit_image()`（先快照 → 再显示 → 标记已应用），
  11 条真实 UI 路径已验证撤销可恢复。
- **保存崩溃**：`self._applied_image or self.preview.current_image()` 对 ndarray 求布尔值，
  应用过任何编辑后保存必抛 `ValueError: truth value of an array is ambiguous`。
- **`processors/filters.py` `dither_bayer()` 缺一个冒号**：`[:h, w]` 实际是单列索引，
  非正方形图直接崩溃，正方形图则用单列广播抖动。修正为 `[:h, :w]`。
- **`processors/filters.py` `old_tv()` 扫描线无法广播**：`(h, 1)` 对 `(h, w, 3)` 只在 h == w 时成立，
  **所有非正方形图都崩溃**。改为 `scanlines[..., None]`。
- **`processors/filters.py` `anaglyph()` 窄图 shift=0**：`w < 50` 时 shift 为 0，
  产生空切片赋值 `ValueError`。改为 `max(1, ...)` 并夹取边界。
- **退化尺寸崩溃**：`kaleidoscope` / `mirror_reflection` / `dual_split` / `reduce_colors` / `glitch`
  在 1×1、2×2、5×3、3×200 等尺寸下抛异常（空切片、kmeans 簇数 > 样本数、`randint(0, 0)`）。
- **`app/panels/shader_studio.py` `LineEditor`**：`_gutter` 只在 `resizeEvent` 中惰性创建，
  而 `updateRequest` 会先触发，首次布局即产生 `AttributeError` 回溯。改为构造时创建。
- **`app/workbench.py` 失败任务永久泄漏**：`Task._all_tasks` 是类级强引用列表，
  只有 `finished`/`cancelled` 会调用 `_cleanup_task()`，`failed` 不会。每次滤镜失败都会永久泄漏
  Task 对象及其闭包捕获的**全分辨率图像**（24MP 约 72MB/次）。实测 5 个失败任务 100% 残留。

### Fixed — 健壮性

- **只读目录被误判为可用**：`mkdir(exist_ok=True)` 对**已存在的只读目录也会成功**，
  因此不能用来决定缓存/预设目录。新增 `processors.utils.ensure_writable_dir()`（用真实临时文件探测），
  预设目录与 GMIC 缓存目录在只读 HOME / 容器 / NFS 下会回退到系统临时目录，而不是抛裸 `OSError`。
  这同时让 5 个原本失败的预设测试转为通过。
- **预设非原子写**：改为临时文件 + `fsync` + `os.replace`；`list_presets()` 不再静默丢弃损坏预设
  （新增 `include_errors=True`）。
- **外部工具无超时且可能挂起**：`processors/media.py`（magick/ffmpeg）、`processors/parity.py`（cjxl）、
  `processors/gmic.py` 补上超时。另外发现 **`gmic` 在 stdin 非终端时会读取命令管道并永久阻塞**
  （管道输入下无限挂起、`< /dev/null` 才返回），已对全部 gmic 调用加 `stdin=subprocess.DEVNULL`。
- **滤镜链取消未真正打通**：`FilterDef.apply()` 从不把 `cancel_token` 转发给处理器，
  因此声明了 `cancel_token` 的处理器（如 `parity.generate_fractal`）内部检查全是死代码。
- **`preview_widget`**：`_numpy_to_pixmap()` 现在对非连续数组做 `ascontiguousarray`
  （`QImage` 直接包裹 numpy 缓冲，stride 不符会导致图像错位）；`paintEvent` 不再调用会触发
  `update()` 的 `fit_image()`；空状态提示里的 `\\n` 是字面反斜杠而非换行；删除死代码 `_dark_background()`。
- **任务池并发 8 → 4**：单条 24MP float32 流水线中间量约 288MB，8 条并发峰值可达数 GB；
  关窗时 `TaskQueueWidget.shutdown()` 有界等待，避免退出被最长滤镜卡住。
- **测试套件全局单例污染**：`tests/test_filter_chain_task.py` 注册的 `_test_boom`（故意抛异常）
  会泄漏到 `FilterDefRegistry` 全局单例，影响其他模块（已实测导致假失败）。
  新增 `FilterDefRegistry.unregister()` 并在 `tearDownModule` 中清理，已验证执行顺序无关。

### Performance

实测环境：24MP (6000×4000) / 12MP / 1200×1600，numba 0.67 可用。

| 项目 | 优化前 | 优化后 | 说明 |
|---|---|---|---|
| 调整面板「应用调整」（GUI 线程阻塞） | 2760 ms | **1.2 ms** | 跳过默认值步骤 + LUT + 转后台任务；后台 78 ms 完成，约 35x |
| `floyd_steinberg` | 4479 ms (600×800)，24MP 约 220 s | **5.2 ms**，24MP 约 0.4 s | numba JIT + 分行；**逐像素一致**，约 550x |
| `circular_pixelation` | 204 ms (1200×1600) | **21 ms** | 向量化 + 删除死代码；**逐像素一致**，约 10x |
| `brightness` / `contrast` / `exposure` | 65 / 103 / 66 ms (12MP) | **13~15 ms** | 256 项 LUT；**逐像素一致**，4~8x |
| `vignette` | int64 索引图 → float64 距离图，每次重算 | 中间量减半 | 改 float32 并按尺寸缓存掩膜 |
| 参数预览：每次滑块 tick 重算降采样 | 60 ms/次 (48MP) | **0.018 ms** | 按 (identity, size, generation) 缓存 |
| 撤销历史内存 | 30 张全分辨率副本 ≈ **2.1 GB** (24MP) | ≤ 512 MB | 按总字节预算裁剪，同时保留 30 条上限 |
| `LogWidget` 日志 | 每条消息重建全文，O(n²) | 增量追加 | 缓冲上限 5000 条 |

- `processors/_jit.py` — 抽出共享 `maybe_jit`，`fractal.py` 与 `filters.py` 共用（numba 缺失时自动降级）。
- 修正 `filters.py` 中 3 处 `np.indices()` 未指定 dtype 导致 int64 → float64 的问题
  （`vintage` / `haze` / `wave`）。
- 滤镜参数原先被重复校验最多 3 次（`make_filter_chain_worker` → `validate_all` → `FilterStep.apply`
  → `FilterDef.apply`），已消除其中一层。

### Changed — 行为变更（升级注意）

- `MainWindow._apply_adjust_full_res()` 现在是**异步**的（提交到任务队列）。
  `_smoke_test.py` 已相应加入 `wait_apply()` 等待。需要同步结果的调用方请改用任务信号。
- 提交新结果的正确写法是 `self._commit_image(result, "原因")`；
  不要再用 `set_display()` 紧跟 `_push_history()` 的顺序（那会让撤销失效）。
- 滤镜参数预览原先恒定 384px（`else 768` 是死分支，因为 `_is_dragging_sliders` 恒为真）；
  现在拖动时用 384、停止后自动补一次 768。
- `dither_bayer()` 输出会变化 —— 之前是崩溃或错误的单列图案，现在才真正应用 4×4 Bayer 矩阵。
- `vignette()` / `wave()` 中间量由 float64 改 float32，输出最多 **±1 LSB**；
  调整链中 `saturation(0)` / `vibrance(0)` 现在被跳过，省掉一次有损 HSV 往返（≤1 LSB）。
- `floyd_steinberg()` 新增可选 `cancel_token` 参数（按行分 20 段检查）。
- `TaskQueueWidget` 线程池由 8 降为 4。

### Added — Tests

- `tests/test_core.py`（19 项）— 覆盖此前**零覆盖**的 `processors/core.py`：
  `contrast` 默认值恒等 / 不posterize / 与参考曲线一致、`hue_shift` 全色环正确性、
  LUT 与浮点路径逐像素一致、`vignette`/`border`、`ensure_writable_dir` 只读回退。
  已做变异验证：换回原 buggy 的 `contrast`/`hue_shift` 后，9 项中 7 项失败。
- `tests/test_filter_robustness.py`（8 项）— **153 个滤镜 × 16 种尺寸 = 2448 次运行，0 失败**
  （修复前 16 处崩溃）；另含针对缺冒号 / 广播 / 空切片缺陷的定点断言。
- `tests/test_task_and_history.py`（10 项）— 失败任务回收、`shutdown()`、
  撤销语义、保存不再崩溃、历史字节预算、日志上限。
- `tests/test_shader_studio.py` — 新增 `LineEditorGutterTests`（gutter 必须在
  `updateRequest` 之前存在）。

### Verification

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests`：
  **262 tests / 261 PASS**（1 GMIC `test_cli_run` timeout，pre-existing 环境问题）。
  本轮开始前为 223 tests / 9 errors（9 个全部来自只读 `~/.toolbox`、`~/.cache/toolbox` 沙箱限制，
  其中 5 个预设测试已由可写性回退修复）。
- `QT_QPA_PLATFORM=offscreen .venv/bin/python _smoke_test.py`：**ALL SMOKE TEST PASSED**
  （init / 快速拖动 / 应用 / 撤销 / 二次应用 / 重置）。
- 全滤镜扫描：153 filters × 16 sizes = 2448 runs，**0 失败**（灰度输入另测 153 项，0 失败）。
- 真实 UI 提交路径逐一驱动验证（反色/灰度/直方图均衡/CLAHE/暗角/旋转×3/翻转×2/缩放/裁剪×3/
  水印×2/边框/自动裁剪）：`changed=True`、`history=1`、`_applied_image` 同步、**undo 全部恢复原图**。

### Known Issues（本轮未解决）

- `test_gmic_backend.GmicTests.test_cli_run` 在本机沙箱中超时：`gmic -input 16,16,1,1 -noise 5`
  在无 `-output` 时行为不稳定（`stdin=DEVNULL` 已把无限挂起转为有界返回，但该 sandbox 下
  仍可能超过测试的 5s 超时）。属于 pre-existing 环境问题。
- 真实 Wayland/X11 GUI、Shader OpenGL runtime 仍无法在无显示环境验证（`QOpenGLWidget is not
  supported on this platform`）。
- `saturation` / `vibrance` / `highlights_shadows` 仍需完整 HSV/亮度变换（非线性），未做 LUT；
  24MP 下单次约 310~520 ms，是调整链剩余的主要开销。
- `MainWindow` 仍约 4400 行，职责拆分未完成。

---

## 2026-09-29

### Added — A3/A4 FilterDef / FilterChain / TaskQueue / Preview / FilterPreset

- `processors/filter_defs.py` — 声明式 FilterDef / FilterParam / FilterCategory 系统
- `processors/filter_registry.py` — FilterDefRegistry + curated 自动注册管线
- `processors/filter_chain.py` — FilterChain / FilterStep / FilterChainError，可组合、可禁用/启用、可序列化
- `processors/filter_chain_task.py` — FilterChainWorker（QThread 后台渲染）+ PreviewCache（命中/跳过）
- `processors/filter_presets.py` — FilterPresetManager（JSON 持久化，跨会话恢复）
- `processors/batch_filter_chain.py` — BatchFilterChain（多文件批处理）
- `processors/cancellation.py` — CancelToken（可链式传递到后台任务）
- `app/widgets/filter_parameter_widget.py` — FilterDef 参数 → Qt widget 自动生成（滑块/下拉/颜色选择器）
- `app/main_window.py` FilterPanel / BatchPanel / Preview 重构为 FilterDef 驱动
- 新增 FilterCategory：BLUR / SHARPEN / ADJUST / COLOR / EFFECT / NOISE / DISTORT / ARTISTIC / UTILITY / FILTER_GEN / BLEND / FILTER_GEN_2 / MULTIFRAME / FILTER_VARIANT / FILTER_SAMPLE / EXPERIMENTAL / **FRACTAL**

### Added — A5 Fractal 分形框架

- `processors/fractal.py` — 完整分形渲染框架（879 行）
  - FractalColoring 枚举：SMOOTH（Nielsen 平滑）/ BANDED / GRAYSCALE
  - FractalParams dataclass：cx, cy, scale, power, iterations, bailout, julia_c, phoenix_c, nova_relaxation
  - FractalResult：image (PIL.Image), iterations_array (np.int32), escaped_mask
  - **15 种 2D escape-time 公式**（全部真实数学实现，非 alias）：
    Mandelbrot / Multibrot / Julia / Burning Ship / Tricorn / Multicorn / Celtic / Buffalo / Perpendicular Burning Ship / Phoenix / Newton / Nova / Magnet I / Magnet II / Buddhabrot（密度渲染）
  - **1 种 3D 公式**：Mandelbulb（distance estimator + ray marching + spherical z↦zⁿ）
  - smooth coloring 用 Nielsen 平滑着色，escape_radius 真参与逃逸判断
  - `render_fractal(width, height, formula_key, params, cancel_token, progress_cb)` — 统一入口
  - CancelToken 按 row 分块检查，取消立即终止；progress 0→100 单调递增
  - numba 可选加速（`_maybe_jit` 装饰器），import 失败自动 fallback 纯 Python
  - 每个 2D 公式自动注册为 `fractal_*` FilterDef，capabilities 动态推导参数

### Tests

- `tests/test_fractal.py` — 29 项：15 种公式注册、参数真生效（Julia const diff=28.7, Multibrot power diff=19.6, center/zoom diff=49.9）、CancelToken 中断、progress 单调、3D Mandelbulb smoke、FilterDef/FilterChain/Preset 集成
- `tests/test_filter_defs.py` — FilterDef 参数声明式 API、capabilities 推导
- `tests/test_filter_chain.py` — FilterChain 组合、禁用/启用、FilterStepError
- `tests/test_filter_chain_task.py` — 后台 FilterChainWorker、CancelToken、PreviewCache
- `tests/test_imports.py` — 模块导入稳定性

### Verification

- `uv run python -m unittest discover -s tests -v`：**222/223 PASS**（1 GMIC timeout，pre-existing）
- `uv run python -m unittest tests.test_fractal -v`：**29/29 PASS**
- PySide6 offscreen MainWindow smoke：创建 OK → 15 fractal filters 可见于 filter_list → FilterDef apply OK → CancelToken 传播 OK → closeEvent 无 crash
- numba 可选加速：检测到环境可用时自动启用；无 numba 时 fallback 纯 Python

### Changed

- `app/main_window.py` — +1112/-384 行，FilterPanel/BatchPanel/Preview 全面重构为 FilterDef + FilterChain + TaskQueue 架构
- `processors/__init__.py` — 新增 filter_defs / filter_registry / filter_chain / filter_presets / batch_filter_chain / fractal 导出

### Known Issues

- Creator Fractal panel 仅 Mandelbrot/Julia 下拉，全部分形公式通过 Filter panel 访问
- 2D escape-time 扩展公式 ~27 种未实现（Barnsley 系 / Sine / Sinh / Feather / Tetration / Spider 等，escape-time 小变体，模式完全一致，后续可批量补充）
- 2D Density/Attractor 15 种未实现（Hopalong / Martin / Clifford 等，独立随机迭代吸引子）
- 3D Geometric IFS / Quaternion / Attractor 12 种未实现
- OrbitTrap / Angle coloring 未实现
- Mandelbulb 未注册为 FilterDef（3D 从空场景渲染，非"输入图像处理"语义）
- Magnet I/II 公式的圆吸收条件可能需要对照标准 Julia 变体验证

---

## 2026-09-22

### Added

- 建立 `feature/toolbox-parity-ui-overhaul` 开发分支与 Git 基线。
- 增加 ImageToolbox 67 个 feature 的桌面 parity 审计矩阵。
- 增加专业参数面板：分形、纹理、网格渐变、Shader、SVG、Photomosaic、多帧融
  合、动画转换。
- 增加批量重命名预览与安全执行。
- 增加可停靠任务队列、进度、暂停/继续、取消和运行日志。
- 增加窗口布局保存、恢复和重置。
- 增加 Dark / Light / System 主题与持久化设置。
- 增强 OCR：语言、页面布局和结果保存。
- 增强 EXIF：读取、编辑、删除。
- 增加 parity processor 回归测试。

### Verification

- `python -m unittest discover -s tests -v`：4/4 通过。
- PySide6 offscreen UI smoke：通过。
- `python -m py_compile app/*.py processors/*.py main.py`：通过。
