# Phase 6A 验收清单（Linux 目标环境执行）

> 状态口径：Phase 6A = `code_complete` / `static_reviewed`（总纲 §14.2）。本清单
> 通过后才算 `runtime_verified`；通过前迁移矩阵相关行保持 `待迁移`
> （ui-migration-matrix.md 头部状态取值规则：只有 `待迁移` / `已迁移` 两种取值，
> `已迁移` 要求"新 UI 中真实可用并验收"，CI 单测不构成改判依据）。
> 分工口径：§1 为 CI 已覆盖的逻辑层项（实机不重复执行）；§2 起为必须在 Linux
> 目标环境（真实 Worker 进程 + 真实桌面 GUI 会话）执行的项。
> 覆盖范围：总纲 §7 Phase 6（滤镜系统与创作工作区）迁移顺序的第 1-5 项——
> FilterDef 列表与分类、参数定义驱动的 QML 控件、预览、FilterChain、预设保存
> 与恢复（对应 docs/user-flows.md 流程 2 全部节点）；第 6 项 G'MIC（仅置灰
> 机制随本批交付，滤镜库本体属矩阵 §2 的收敛批次）、第 7 项 Batch、第 8-11 项
> 各 Studio **不在本批**，见 §6。
> 依赖：Phase 3/4/5 验收（docs/phase3-acceptance.md、docs/phase4-acceptance.md、
> docs/phase5-acceptance.md）截至本清单撰写均**尚未在目标环境执行**（复选框未
> 回填）。本清单 §2 的端到端项复用 Phase 5 编辑器的打开/画布/历史路径，执行时
> 按 phase5-acceptance.md §2 一并回填。
> 实现锚点：Worker 侧 `python_worker/dispatcher.py`（动作表）与
> `python_worker/adapters/filter_adapter.py`；C++ 侧
> `native/models/filter_model.*` / `native/models/filter_chain_model.*` /
> `native/services/filter_service.*`（tracked dispatch 复用
> `native/core/document_service.cpp` 的 applyFilters 通道）；QML 侧
> `ui/components/AppFilterCard.qml` / `AppFilterParameterGroup.qml` /
> `AppFilterChainItem.qml` / `AppFilterInspector.qml` 与
> `ui/pages/EditorPage.qml`（滤镜页签）。协议形状见 docs/ipc-protocol.md §3.4。

## 准备

```bash
cd ~/toolbox
git fetch origin && git checkout <phase6a 分支>
uv sync --extra dev                       # Worker 依赖沿用现有锁定环境
cmake --preset linux-debug && cmake --build --preset linux-debug
```

## 1. CI 已覆盖（实机不重复执行；推送后以 GitHub Actions 实际结果为准）

> 以下项由 CI 两个 job 的现有机制自动纳入：test job 的 `unittest discover`
> 发现 tests/ 下全部用例（ci.yml:65-67），native job 的 CTest 注册了
> filter_model / filter_chain_model / filter_service 三个新目标
> （tests/native/CMakeLists.txt:127-166）。截至本清单撰写，Phase 6A 改动尚未
> 提交推送——"CI 已覆盖"均指测试已就位并随既有 CI 机制执行，推送后的实际
> 运行结果回填 §6。

- [ ] 预设四动作逻辑单测（Python，`tests/test_worker_presets.py`，15 个用例，
      进程内 Dispatcher + TaskRuntime，存储重定向临时目录）：list 空初始与
      `{name, step_count}` 字段裁剪、save 往返 / enabled 缺省 true / 同名覆盖 /
      非字符串名与空白名与非法 steps（非数组 / 缺 filter_key / 元素非对象 /
      params 形状非法）→ `INVALID_PARAMS`、load 往返 / 缺失 → `FILE_NOT_FOUND` /
      损坏文件与 schema_version 超前 → `ENGINE_ERROR`、delete 往返递减 /
      缺失 → `FILE_NOT_FOUND` / 存储层 OSError → `ENGINE_ERROR`（不谎报成功）
- [ ] 协议与目录形状（Python，`tests/test_worker_protocol.py`）：`filter.list`
      非空且带 key/name/category/params/available 字段、`filter.preview` 写
      临时文件且尺寸受 max_side 约束、`filter.apply` 更新文档像素与 version、
      build_chain 未知 key 拒绝、chain_fingerprint 稳定
- [ ] 引擎层既有覆盖（Python，本批未改动、随 CI 继续执行）：
      `tests/test_filter_chain.py`（链组合/禁用启用/序列化）、
      `tests/test_filter_defs.py`（FilterDef 参数声明）、
      `tests/test_filter_robustness.py`（153 滤镜 × 16 尺寸健壮性）
- [ ] C++ 目录模型（CTest，`tests/native/test_filter_model.cpp`，7 用例，
      QAbstractItemModelTester）：角色名锁定、filter.list 协议形状解析
      （available 缺失按不可用处理）、整表重建、缺 key 条目跳过、搜索
      （标题+关键词、大小写不敏感、空查询返回全部）、越界 data（无效索引
      回答无效值不崩溃）
- [ ] C++ 链模型（CTest，`tests/native/test_filter_chain_model.cpp`，10 用例）：
      角色名锁定、replaceFrom（缺 key 跳过 / enabled 缺省 true / 行数通知）、
      addStep（空 key 忽略）、removeRow 越界静默、moveUp/moveDown 边界拒绝、
      移动后 chainIndex 刷新、setEnabled 同值防抖
- [ ] C++ 服务（CTest，`tests/native/test_filter_service.cpp`，7 用例，信号
      模拟不启动 Worker）：默认态与未绑定后端如实报错零上送、filter.list 填充
      模型与 loadingFilters 生命周期（失败响应同样收标志）、预设本地拒绝
      （空名称）、预设 list→save→load→delete 关联往返与自动刷新（合成响应帧，
      真实预设存储往返归上方 Python 侧条目）、空链/无文档委托拒绝、
      previewChain/applyChain → DocumentService.applyFilters → TaskModel
      任务行"滤镜链" → §3.1 版本落定
- [ ] C++ 文档服务（CTest，`tests/native/test_document_service.cpp` 既有 21
      用例中的 applyFilters 部分）：filter.preview 完成只发 previewReady 不改
      版本、filter.apply 完成 version+1 且置 modified、空链本地拒绝恰好一次
      documentActionFailed、陈旧文档完成丢弃
- [ ] CI 环境边界（为何仍需实机）：ubuntu runner、`QT_QPA_PLATFORM=offscreen`、
      C++ 测试直接 emit BackendManager 信号模拟协议帧（不启动真实进程）、无
      GUI 交互、无真实预设目录读写（QTemporaryDir）。QML 组件
      （AppFilterCard / AppFilterParameterGroup / AppFilterChainItem /
      AppFilterInspector 的交互行为）无 QML 测试机制，全部归 §2-§5。

## 2. 流程 2 端到端（必须实机）

> 对应 docs/user-flows.md 流程 2：浏览 → 调参 → 入链 → 预览 → 应用 → 预设
> 保存/加载。全部经 EditorPage 滤镜页签真实控件操作，不使用测试驱动。前置：
> 已打开一张图像（流程 1 打开项通过，`v0` 显示）。

- [ ] **目录浏览**：检查器切到"滤镜"页签 → 滤镜目录出现（分类中文名 +
      滤镜显示名，排序为分类内按名称）；搜索框输入名称/关键词/分类片段 →
      网格实时过滤；清空搜索恢复全部；目录加载期间显示进行中指示
      （loadingFilters）
- [ ] **调参**：点选任一可用卡片（选中态 accent 描边）→ 参数面板按 FilterDef
      定义自动生成控件（float→滑杆、int→数值、bool→开关、enum→下拉、
      color→色块、string→文本，当前注册表以 float/int/enum/bool 为主）；
      "重置参数"回到默认值；悬停卡片显示描述 Tooltip
- [ ] **入链**：调好参数点"加入链" → 链列表出现一行（滤镜显示名 + 参数摘要
      `k=v · …`，空 params 显示"默认参数"），参数面板回默认；再入链第二个
      滤镜 → 链两行、顺序即应用顺序；行内启用开关停用一步 → 摘要变灰；
      ↑/↓ 调整顺序；✕ 删除；链标题的步数徽标跟随
- [ ] **链预览**：链非空时自动触发 300ms 防抖预览（§4 细项）；完成 → 画布
      刷新为链效果（`?v=` 强制重载）；状态栏 `vN` 不变（filter.preview 不递增
      版本，§3.1）、`●` 不亮、撤销按钮不点亮（预览不进历史）
- [ ] **应用链**：点"应用" → 按钮转装载态；`vN → vN+1`、`●` 出现、历史条目
      `filter.apply` 入栈（撤销按钮点亮）；**链被清空**（与调整页签"应用后
      滑杆回中性"同一纪律：残留链会在下一次预览/应用时把同一链再叠加一遍，
      EditorPage.qml onDocumentVersionChanged 分支）；画布刷新为已应用像素
- [ ] **撤销链应用**：`Ctrl+Z` → 画布回到应用前像素（`version` 仍递增，协议
      §3.1）；重做可前进
- [ ] **预设保存**：链配好后输入名称点"保存" → 成功 Toast"预设已保存"；预设
      下拉出现"名称 · N 步"条目；`~/.toolbox/filter_presets/*.filterchain.json`
      （或 Settings `presets/filter_chain_dir` 覆盖路径）出现同名文件
- [ ] **预设加载**：改乱当前链 → 下拉选中预设 → 点"加载" → Toast 报步数、
      链列表被整体替换（replaceFrom）、随后预览/应用按载入链执行
- [ ] **预设删除**：选中预设点"删除" → Toast、下拉条目消失；再执行删除同一
      名称（陈旧下拉）→ `FILE_NOT_FOUND` Toast，不谎报成功（协议 §3.4）
- [ ] **预设持久化**：保存预设 → 完全退出应用 → 重启 → 滤镜页签预设下拉仍含
      该预设（预设存文件系统、Worker 无状态依赖）
- [ ] **错误与降级路径**：Worker 未就绪打开滤镜页签 → "Worker 未就绪，无法
      加载滤镜目录"提示 + 检查器降级横幅（画布仍可查看）；就绪后目录自动补拉
      （onRunningChanged / onBackendReadyChanged 兜底）；空名称/空链时保存
      按钮禁用（AppFilterInspector enabled 绑定）、加载/删除按钮在无选中预设
      时禁用（服务层空名称本地拒绝 filterError(INVALID_PARAMS) 为防御路径，
      UI 入口已挡住——CI 已覆盖 presetLocalRejections，如实记录）；空链时
      预览/应用按钮禁用、链变化防抖出口被空链门挡下（换文档自动清链不弹
      错误 Toast）
- [ ] **任务行**：链预览与链应用在任务抽屉各有一行"滤镜链"（taskDisplayName，
      document_service.cpp:55-62），大图上进度条随 task.progress 更新，行内
      取消可用（§4）
- [ ] **换文档隔离**：应用链后打开第二张图 → 链保持清空、在途门控标志复位
      （onDocumentOpened 显式作废，旧文档在途全分辨率结果被丢弃）

## 3. G'MIC 类滤镜置灰（必须实机）

> 机制（流程 2 节点"不可用滤镜显示置灰 + 原因"；异常路径表"依赖缺失置灰 +
> 不弹错误风暴"）：Worker filter.list 的 `available` / `optional_deps`
> （filter_adapter.py:22-39：`available = not defn.optional_deps`）→
> FilterModel AvailableRole/OptionalDepsRole → AppFilterCard 置灰（40% 不
> 透明度、光标禁用、点击与键盘激活均无效）+ Tooltip 原因（"缺少可选依赖：
> gmic"，AppFilterCard.qml:153-160）。
> **如实边界**：当前 curated 注册表（processors/filter_registry.py）没有任何
> FilterDef 声明 `optional_deps`（G'MIC 滤镜未进入 FilterDefRegistry，属矩阵
> §2 的 G'MIC 收敛批次），故在标准 Linux 环境下目录内全部滤镜可用——本节
> 实机验收的是**置灰机制的呈现**，不是"目录里现成有置灰卡片"：

- [ ] 目录内全部卡片可交互（当前环境无缺依赖滤镜——如实观察，不算失败）
- [ ] 置灰路径实机演练：临时给任一注册滤镜的 FilterDef 声明
      `optional_deps=["gmic"]`（filter_registry.py 的 `_register` 助手不转发
      该参数，需直接改该滤镜的 `register_filter` 调用或 FilterDef——本地验证
      用，不提交）→ 重启应用 → 该卡片置灰、Tooltip 显示
      "缺少可选依赖：gmic"、点击与 Space/Enter 均无效、"加入链"按钮对该卡片
      禁用；恢复声明后卡片复原
- [ ] 置灰条目经搜索路径同样置灰（搜索结果与目录共用 AppFilterCard 委托）
- [ ] CI 合成条目佐证（不重复执行）：test_filter_service.cpp:130-146 的
      available=true/false 双条目与 optional_deps=["gmic"] 形状、
      test_filter_model.cpp 的 unavailable 条目解析
- [ ] G'MIC 滤镜库本体（命令行应用与帮助页）不在本批：矩阵 §2 行保持
      `待迁移（收敛到 backends/）`，验收时不得把置灰机制当作 G'MIC 库已迁移

## 4. 预览防抖与取消（必须实机）

> 防抖纪律：链的任何变化（加入/删除/排序/启停/载入预设）与 [预览] 按钮共用
> 同一 300ms 防抖（EditorPage.qml `filterPreviewDebounce`）；出口
> requestChainPreview 内再做无文档/未就绪/空链门检。

- [ ] **防抖合并**：快速连续加入三个滤镜（间隔 < 300ms）→ 任务抽屉只出现
      一行"滤镜链"预览任务（防抖出口收敛，不是每变化一发）；[预览] 按钮
      连点两次 → 同样只发一次
- [ ] **防抖时序**：单次变化后 300ms 内无新变化才发出请求（可见任务行延迟
      出现）；变化间隔拉长到 > 300ms → 每次变化各发一次
- [ ] **预览中取消**：大图（≥24MP）链预览进行中 → 任务抽屉行内"取消" →
      行变 `cancelling` → Worker 回报后转 `cancelled`（显示"已取消"非
      "失败"）；画布保持当前像素、`vN`/`●`/历史不变，可立即重新预览
- [ ] **应用中取消**：全分辨率链应用进行中取消 → 同上；文档不被半途修改
      （协作检查点抛 CancelledError，协议 §7）；门控按钮在失败/取消上报后
      复位（documentActionFailed 的 filter.apply 白名单，EditorPage.qml:875-893）
- [ ] **已知竞态（如实验收，回填 §6）**：同文档内旧预览任务没有取消/作废
      机制——慢的旧预览（前一个链状态）可能在新的预览之后完成并覆盖画布
      （previewReady 无版本序丢弃，document_service.cpp handleCompleted 仅按
      documentId 丢陈旧；filter.preview 的 result 不含 version）。验收时用
      大图 + 快速改链复现或证伪，把结论写入 §6；流程 1 约束"旧预览被取消/
      废弃，不得覆盖新预览"（user-flows.md:19-21）在滤镜链路径上的实现状态
      以实测为准
- [ ] **已知偏差（与 Phase 5 一致）**：Esc 取消在途预览未实现（ImageCanvas 无
      Esc 处理），取消入口只有任务抽屉行内按钮

## 5. 大图与门控（必须实机）

- [ ] ≥24MP 图像：多步滤镜链（如 链 3 步）预览与应用期间拖动窗口、缩放画布、
      切换页签全程无卡顿（像素计算全在 Worker，主线程零像素计算——总纲 §9；
      打开首帧的本地同步解码是 Phase 5 已知例外，见 phase5-acceptance.md §8
      偏差 1）
- [ ] 记录预览 / 应用实测耗时 → §6
- [ ] 全分辨率在途门控：链应用进行中 → 保存/另存为/撤销/重做/重置/变换/
      再应用全部禁用；完成或失败后恢复（与调整页签同一 fullResInFlight 串行化，
      防多线程任务池下历史栈改写竞态）
- [ ] 应用完成后的画布刷新不叠加：应用链 → 画布刷新期间链已清空、调整滑杆
      原样（全默认取回通道 requestDocumentRefresh，EditorPage.qml:264-268），
      画布即"文档当前像素"，无二次滤镜效果

## 6. 偏差与记录（回填）

- **参数类型与组件规格偏差**：ui-component-spec.md §3 AppFilterParameterGroup
  写的类型集为 {float,int,bool,enum,color,point}；实现为
  {float,int,bool,enum,color,string}（AppFilterParameterGroup.qml:72-75）——
  无 point 类型（当前注册表也没有 point 参数），string 为实现补充。规格修订
  与实现取齐留待后续批次；验收时若出现 point 参数滤镜按"控件缺失"如实记录。
- **预览缓存未实现**：流程 2 节点"缓存 key = 链参数指纹"（user-flows.md:53）
  ——Worker 在 filter.preview 结果中返回 `fingerprint`
  （dispatcher.py:226、filter_adapter.py:118-122），但 UI 侧每次链变化都发新
  请求，无指纹命中缓存。既有 processors/filter_chain_task.py 的 PreviewCache
  未接入 Worker 管线。属功能缺口非缺陷，验收按现状记录。
- **拖拽排序未实现**：ui-component-spec.md §3 AppFilterChainItem"拖拽排序
  （Phase 6）"——本批以 ↑/↓ 按钮代替，无拖拽交互。
- **G'MIC 边界**：置灰机制已交付（§3），G'MIC 滤镜库本体/命令行应用未迁移
  （矩阵 §2），FilterDefRegistry 现无 optional_deps 声明——标准环境下无
  现成置灰卡片（§3 如实条款）。
- **同文档旧预览覆盖竞态**：见 §4，实测结论回填此处（复现/证伪 + 复现步骤）。
- **ui-page-spec §2 对应行**：滤镜页签本批交付的形态为
  "搜索 + 卡片网格 + 参数面板 + 链列表 + 预设行 + 预览/应用按钮"；页签内
  无独立"缓存/指纹"指示。若页签规格与实现表述冲突，修订与 §4 竞态结论同批
  进行（该文档不在本批清单）。
- **协议文档既有漂移（本批未改动）**：docs/ipc-protocol.md §3 的 `filter.list`
  结果行未列全 Worker 既有返回字段 `category_label` / `preview_supported` /
  `batch_supported`（python_worker/adapters/filter_adapter.py:21-38，其中
  category_label 已被 FilterModel 与 UI 消费）；该漂移属既有交付，修订不属
  本批清单，验收时以 Worker 实际形状为准。
- 回填项：CI 实际结果链接与结论（test + native 双 job）；§2 逐项勾选；
  §3 演练的置灰截图或文字记录；§4 竞态结论与取消时延；§5 耗时数据；
  实际桌面会话（X11 / Wayland）→ 直接写入本文件对应小节。
