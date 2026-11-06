# Phase 6B 验收清单（Linux 目标环境执行）

> 状态口径：Phase 6B = `code_complete` / `static_reviewed`（总纲 §14.2）。本清单
> 通过后才算 `runtime_verified`；通过前迁移矩阵 §4 批处理行保持 `待迁移`
> （ui-migration-matrix.md 头部状态取值规则：`已迁移` 要求"新 UI 中真实可用
> 并验收"，CI 单测不构成改判依据）。
> 分工口径：§1 为 CI 已覆盖的逻辑层项（实机不重复执行）；§2 起为必须在 Linux
> 目标环境（真实 Worker 进程 + 真实桌面 GUI 会话）执行的项。
> 覆盖范围：总纲 §7 Phase 6（滤镜系统与创作工作区）迁移顺序的**第 7 项
> Batch Processing**——协议 `batch.start` / `batch.cancel`（docs/ipc-protocol.md
> §3.5）与 `gmic.check`（§3.6）的 Worker 侧交付、C++ 侧 BatchService/BatchModel
> 消费、QML AppBatchWizard + BatchPage 导航接线。G'MIC 库本体仍**不在本批**
> （矩阵 §2 收敛到 backends/ 的批次）；§3 只验收"依赖不可用置灰路径"的呈现与
> `gmic.check` 诊断动作本身，不得把置灰机制当作 G'MIC 库已迁移。
> 依赖：Phase 6A 验收（docs/phase6a-acceptance.md）截至本清单撰写**尚未在目标
> 环境执行**（复选框未回填）。批量页的滤镜链入口是"套用预设"
> （FilterService.presetsList / loadPreset，与编辑页签共享同一预设存储与
> FilterService 单例），§2 的预设路径执行时按 phase6a-acceptance.md §2 的预设
> 项一并回填；批量页不提供逐滤镜调参与入链（那是编辑页签的职责）。
> 实现锚点：Worker 侧 `python_worker/dispatcher.py`（动作表 dispatcher.py:52-64、
> `_batch_start_job`/`_batch_cancel`/`_gmic_check` dispatcher.py:207-287）与
> `python_worker/adapters/batch_adapter.py`（build_batch_plan / scan_inputs /
> run_batch_plan，batch_adapter.py:48-244）；复用 1.0 资产——
> `processors/batch_filter_chain.py` `run_batch_filter_chain`（逐文件
> load → 链 → save 与逐项记账，本批仅补 quality/output_name_fn 可选参数）、
> `processors/batch.py` `batch_rename` 的 pattern 占位符语义、
> `processors/cancellation.py` `CancelToken`、`processors/gmic.py` `check`
> （gmic.py:26-39）。C++ 侧 `native/models/batch_model.*`（行模型）与
> `native/services/batch_service.*`（facade）；QML 侧
> `ui/components/AppBatchWizard.qml` 与 `ui/pages/BatchPage.qml`（宿主），
> 导航接线 `native/app/application.cpp`（navModel "batch" → BatchPage.qml，
> application.cpp:72-74）与 `ui/Main.qml`（Loader 路由，Main.qml:94-95）。
> 协议形状见 docs/ipc-protocol.md §3.5/§3.6（Phase 6B 复查后口径：
> batch.start 受理回执为 `{task_id, status, total}`）。

## 准备

```bash
cd ~/toolbox
git fetch origin && git checkout <phase6b 分支>
uv sync --extra dev                       # Worker 依赖沿用现有锁定环境
cmake --preset linux-debug && cmake --build --preset linux-debug
```

测试素材：准备一个 ≥20 张图片的目录（含至少一层子目录与一个非图片文件）、
3-5 张单图、一张损坏图片（如把文本文件改名 .png）、一个已保存的滤镜链预设
（编辑页签保存，见 phase6a-acceptance.md §2 预设项）。

## 1. CI 已覆盖（实机不重复执行；推送后以 GitHub Actions 实际结果为准）

> 以下项由 CI 两个 job 的现有机制自动纳入：test job 的 `unittest discover`
> 发现 tests/ 下全部用例（ci.yml，`unittest.TestLoader().discover("tests")`），
> native job 的 CTest 注册了 batch_model / batch_service 两个目标
> （tests/native/CMakeLists.txt:185-216）。截至本清单撰写，Phase 6B 改动尚未
> 提交推送——"CI 已覆盖"均指测试已就位并随既有 CI 机制执行，推送后的实际
> 运行结果回填 §6。Phase 6B 覆盖核对后补齐的用例见 §6 首条。

- [ ] 批处理协议全路径（Python，`tests/test_worker_batch.py`，29 用例，
      进程内 Dispatcher + TaskRuntime(max_workers=1)，PIL 现场生成小图，
      gmic.check 用 mock 不要求 CI 机器装 G'MIC）：capabilities.list 注册
      batch.start/batch.cancel/gmic.check；目录递归扫描计数与扩展名过滤
      （大小写不敏感、非图片忽略）、显式文件与目录去重只计一次、缺失路径
      `FILE_NOT_FOUND` 且不产生任务、空目录与显式不支持扩展名文件
      `FILE_NOT_FOUND`；命名三态（keep 源 stem + 输出扩展名 / suffix
      `_batch` / pattern `{name}{ext}{i}{index}` 3 位补零按扫描序、无扩展名
      自动补齐）、JPEG 规范化为 .jpg 扩展名；纯格式转换（steps 缺省/空数组）
      像素主色与尺寸核对、滤镜链批次（禁用步骤不生效的灰度断言）、单文件
      失败不中断批处理（failed 记账 + error 上送 + output_path 省略 + failed
      逐文件终态帧）、format 小写（UI 契约）、quality 显式转发
      save_image(quality=…) 与缺省不注入；进度帧字段集（聚合 done/total/
      current + 逐文件 file/state/progress/output_path，节流合并下首帧必发、
      items 全量对账）；取消（滤镜检查点阻塞 → batch.cancel →
      task.failed(CANCELLED) + 零输出落盘 + 迟到取消如实 `cancelled:false`、
      未知 task_id `UNKNOWN_TASK`、缺 task_id `INVALID_PARAMS`）；提交前同步
      INVALID_PARAMS 全参数面（paths 空/非数组/元素非字符串/空白、output_dir
      空、format 空/不支持、quality 越界/非数值/非整数/布尔、pattern 占位符
      非法、steps 非数组/元素非 dict/缺 filter_key/未知 key/params 非 dict，
      均不产生任务）；gmic.check 四路径（无 gmic → `{available: false,
      version: "", source: null}` 不抛错、CLI 可用 → source:"cli"、python
      绑定回退 → source:"python"、无 `__version__` → "unknown"）
- [ ] C++ 行模型（CTest，`tests/native/test_batch_model.cpp`，8 用例，
      QAbstractItemModelTester）：角色名锁定（batchFile/batchState/
      batchProgress/batchError/batchOutputPath）、resetFrom 缺省 pending 与
      progress 越界收敛、非对象/空 file 条目跳过、updateFrom "存在才更新"
      与空操作不发射、无 file/未知 file 忽略、markActiveAs 只清扫
      pending|running 行、clear、summaryCounters 随状态联动
- [ ] C++ 服务（CTest，`tests/native/test_batch_service.cpp`，11 用例，信号
      模拟不启动 Worker）：默认态与未绑定后端如实报错零上送、本地拒绝
      （空 paths/空 outputDir）恰好一次 batchError、受理建 pending 行并交付
      batchStarted、提交前同步拒绝不动模型、成功响应缺 task_id 按协议违约
      上报、逐文件进度映射行、completed items 整表刷新、CANCELLED 失败清扫
      skipped、非 CANCELLED 失败行保持、单活动批次迟到事件按 task_id 忽略、
      cancelBatch 提交号→task_id 翻译转发
- [ ] CI 环境边界（为何仍需实机）：ubuntu runner、`QT_QPA_PLATFORM=offscreen`、
      C++ 测试直接 emit BackendManager 信号模拟协议帧（不启动真实进程、
      不产生真实文件读写）、无 GUI 交互（FileDialog/FolderDialog、任务表
      交互、Toast、导航离开/重进的恢复语义全不可测）、gmic.check 不触达
      真实 `shutil.which("gmic")`、AppBatchWizard.qml 组件无 QML 测试机制。
      批次的跨进程全链路（QProcess + JSON Lines + 真实文件系统批量读写）
      必须实机（§2）。

## 2. 批处理端到端（必须实机）

> 按工作流顺序执行：添加文件/目录 → 选操作（滤镜链）→ 输出设置 → 开始 →
> 进度 → 取消 → 结果核对。全部经 BatchPage 真实控件操作，不使用测试驱动。
> 前置：Worker 已在设置页启动（应用顶部无降级横幅）。

- [ ] **导航入口**：侧栏点"批量"（application.cpp navModel）→ BatchPage 出现
      向导（右上"添加文件/添加目录"、左任务表、右"输出设置/滤镜链（可选）"
      配置、底部总进度 + 开始/取消）
- [ ] **添加文件**："添加文件"多选对话框（过滤 png/jpg/jpeg/webp/bmp/tif/
      tiff/gif）→ 清单逐行显示文件名与路径；重复添加同一文件不重复入清单
      （appendPaths 去重）；行内"移除"可删单行；清单计数"待处理清单 · N 项"
      跟随
- [ ] **添加目录**：目录以 `[目录] 名称（递归扫描）` 呈现，路径列显示完整
      路径；UI 不做扩展名判定（展开与过滤由 Worker 扫描完成，协议 §3.5）；
      子目录内容计入批次
- [ ] **选操作（滤镜链预设）**：默认"跳过（纯格式转换）"；下拉选中已保存
      预设 → "载入预设中…" → "已选预设：名称（N 步）"；选回"跳过"→ 清链；
      **编辑器链不受影响**（选择预设前后的编辑页签链原样——向导经
      Instantiator 探针快照还原，AppBatchWizard.qml:284-316）；预设列表与
      编辑页签共享（同一 FilterService.presetsList 缓存）
- [ ] **输出设置**：浏览选输出目录（只读文本框回显）；格式下拉
      PNG/JPEG/WebP/BMP/TIFF——选 JPEG/WebP 时质量滑杆可用（缺省 92），
      选无损格式时滑杆禁用；命名三态（保留原文件名 / 追加后缀 _batch /
      自定义命名模式）；选"自定义命名模式"出现 pattern 行（默认
      `{name}{ext}` + 占位符说明），pattern 清空时 [开始] 禁用
- [ ] **Worker 未就绪降级**：设置页停止 Worker → 批量页出现警告横幅
      （"Worker 未就绪（state）——无法开始批处理；添加文件与配置不受影响"）；
      此刻点 [开始] → "后端未就绪" Toast、无上送；重新启动 Worker → 横幅
      消失、预设下拉自动补拉（onRunningChanged 兜底）
- [ ] **开始（纯格式转换）**：显式文件清单 + 输出目录就绪 → [开始] → 运行态
      （配置列整体禁用、添加文件/目录禁用、[开始] 禁用、[取消] 点亮）；
      任务表出现批次行（受理后全部"待处理"色点）；受理前短暂显示
      "等待 Worker 受理…"
- [ ] **进度（显式文件）**：文件行逐个实时翻转（待处理 → 处理中 → 已完成，
      完成行显示"输出：<路径>"）；底部总进度条与"完成 n / N · 失败 m ·
      跳过 k"同步推进；≥100ms 节流下快速小批次可能跳帧（§7），行状态最终
      以完成时的 items 对账为准
- [ ] **进度（目录批次）——已知限制如实观察**：目录条目在批次明细中只有
      一行（提交清单原样上送，AppBatchWizard.qml:53-55），逐文件进度帧的
      行键是展开后的源文件路径，与目录行键不匹配 → 目录行运行期间保持
      "待处理"、总进度条不动；完成时 items 全量对账把明细整表刷新为逐文件
      行（batch_model.cpp updateFrom 对未知 file 不造行 + completed
      resetFrom(items)）。实测记录实际表现与观感结论 → §6
- [ ] **取消**：多文件批次（建议 ≥30 文件大图）进行中点 [取消] → 按钮
      "取消中…"且禁用 → 残余行收尾为"已跳过"（已完成行保持）、Toast
      "批处理已取消（完成 n / N）"；核对输出目录：只有已完成项落盘、
      无半途损坏文件；取消后的批次可立即重新开始
- [ ] **结果核对（格式）**：纯转换批次逐文件核对——输出存在、格式正确
      （JPEG 扩展名 .jpg）、尺寸与源一致、像素未被改动（与源图对比）
- [ ] **结果核对（滤镜链）**：套用预设的批次逐文件核对链效果（与编辑页签
      单图应用同预设的效果一致）
- [ ] **结果核对（命名三态）**：keep → `{源 stem}.{输出扩展名}`；suffix →
      `{源 stem}_batch.{输出扩展名}`；pattern `{name}_{i}{ext}` → 3 位补零
      序号按扫描序（1 起）；输出目录即输出目录文本框所选路径
- [ ] **结果核对（失败文件不中断）**：清单混入损坏图片 → 该行"失败"，
      点击行展开错误详情且可复制，其余文件正常完成（Toast 报
      "批处理完成：N 项，其中失败 n、跳过 k"）；failed 行无输出路径
- [ ] **输出覆盖语义**：对同一清单重复运行（同名输出）→ 旧输出被覆盖
      （协议 §3.5 固定覆盖，与 1.0 面板缺省一致）；suffix 命名 + 输出目录
      选源目录 → 源图不被覆盖
- [ ] **同步拒绝路径（如实演练）**：批次运行中经文件管理器删除/更名输入
      文件后提交 → Worker `FILE_NOT_FOUND` Toast（code · message）、批次
      明细保持现状、不产生任务；服务层本地拒绝（空 paths/空输出目录）为
      防御路径——UI 入口已禁用 [开始]，如实记录即可（CI 已覆盖
      localRejections，不强行构造）
- [ ] **整体失败与中断态**：输出目录指向无写权限路径 → 任务失败
      task.failed(ENGINE_ERROR) → 中断态持久提示行（"上次批处理未完成……"）
      + 错误 Toast；行保持最后已知状态、[开始] 重新可用
- [ ] **单活动批次**：运行中 [开始] 不可点（配置锁定）；完成后再次 [开始]
      → 新批次整表替换旧明细（受理覆盖旧跟踪，更早批次迟到事件按 task_id
      忽略）

## 3. G'MIC 不可用时滤镜 available 置灰路径（必须实机）

> 机制与 Phase 6A §3 同源：Worker `filter.list` 的 `available` /
> `optional_deps`（filter_adapter.py:32-33，`available = not
> defn.optional_deps`）→ FilterModel → AppFilterCard 置灰 + Tooltip 原因。
> `gmic.check`（§3.6）是**独立诊断动作**，不是置灰路径的数据源；截至本批
> 它没有 C++/QML 消费方（设置页"外部依赖"分组的规划数据源
> ui-page-spec.md §4，尚未接线——如实记录，见 §6）。
> **如实边界**：当前 curated 注册表（processors/filter_registry.py）没有任何
> 滤镜声明 `optional_deps`（`_register` 助手不转发该参数，
> filter_registry.py:22-31），标准 Linux 环境下目录内全部滤镜可用——本节
> 实机验收的是**置灰机制的呈现**与**批量路径对不可用滤镜的行为**，不是
> "目录里现成有置灰卡片"：

- [ ] 编辑页签目录内全部卡片可交互（当前环境无缺依赖滤镜——如实观察，
      不算失败；机制呈现细节按 phase6a-acceptance.md §3 执行）
- [ ] 置灰演练（本地验证，不提交）：临时给任一注册滤镜的 FilterDef 声明
      `optional_deps=["gmic"]`（直接改该滤镜的 `register_filter` 调用或
      FilterDef）→ 重启应用 → 编辑页签该卡片置灰、Tooltip
      "缺少可选依赖：gmic"、点击与键盘激活无效——该滤镜无法经编辑器入链，
      即不会经由编辑页签工作流进入批处理
- [ ] **批量页对不可用滤镜的行为**：用上述置灰滤镜构造预设文件
      （预设是持久化用户状态，协议有意不做 FilterDef 校验——§3.4 允许
      引用当前环境不可用滤镜的链；可用手工构造
      `~/.toolbox/filter_presets/*.filterchain.json` 或在声明 optional_deps
      前保存）→ 批量页该预设可正常选择与提交（无置灰标记、无前置拒绝）
      → 批处理执行结果如实记录 → §6。注意：临时声明的滤镜其实现并不调用
      gmic 本体（当前注册表全部为 numpy/cv2 实现），预期批次成功——本项
      演练锁定的是"提交不前置拒绝"的现状；真实依赖失败（解码/写盘/未来
      真 gmic 滤镜）的逐文件失败呈现由 §2 失败文件项覆盖
- [ ] **gmic.check 协议级实机验证**（UI 无消费方，手工发一条请求）：
      ```bash
      echo '{"protocol":1,"request_id":"req-g1","action":"gmic.check","params":{}}' | \
        uv run python python_worker/main.py --repo-root .
      ```
      未装 gmic 的机器 → `{"available": false, "version": "", "source": null}`
      且进程不崩、不抛错；装有 gmic CLI 的机器 →
      `{"available": true, "version": "<x.y.z>", "source": "cli"}`（版本号
      无法解析时如实 "unknown"）
- [ ] CI 合成路径佐证（不重复执行）：test_worker_batch.py GmicCheckTests
      四路径（mock available/sys.modules）与 test_batch_service.cpp 的
      available=true/false 双条目形状；实机条目补的是真实 CLI 探测
- [ ] G'MIC 滤镜库本体（命令行应用与帮助页）不在本批：矩阵 §2 行保持
      `待迁移（收敛到 backends/）`，验收时不得把置灰机制或 gmic.check 当作
      G'MIC 库已迁移

## 4. 非模态、导航与恢复（必须实机）

- [ ] **非模态**：批次运行中切到编辑/首页等其他页面 → 批处理继续（C++ 单例
      上的后台任务，导航不中断、不阻塞其他页面）；运行大目录时其他页面
      操作全程无卡顿
- [ ] **完成提示边界（如实观察）**：离开批量页后批次完成 → **无**全局
      Toast（本期没有全局 Toast 宿主，AppBatchWizard.qml:34-36 头注如实
      记录的限制）；重进批量页 → 按"审查态"呈现最后已知行 + 完成计数
- [ ] **恢复语义（诚实）**：批次运行中离开页面 → 重进 → 模型仍有行 →
      "审查态" + "上一次批处理可能仍在后台运行或已中断；此页没有取消句柄，
      重新开始将替换它（单活动批次）"提示（AppBatchWizard.qml:413-422）；
      若批次仍在跑，batchFinished/batchError 到达后正常收口；重进后
      [开始] 保持可用（重新受理替换旧跟踪，不产生双批次）
- [ ] **预设选择离开保护**：预设"载入中…"（chainLoadPending）时 [开始]
      禁用；载入在途时离开页面 → 编辑器链还原（Component.onDestruction
      restoreChainSnapshot，不把批量选中的预设静默写进编辑器）

## 5. 大目录与资源（必须实机）

- [ ] ≥200 文件目录批次：运行期间拖动窗口、切换页面、滚动任务表全程无卡顿
      （像素计算全在 Worker，主线程零像素计算——总纲 §9；QML 侧只做行模型
      更新与计数绑定）
- [ ] 记录实测数据 → §6：文件数、总耗时、失败/跳过计数
- [ ] 运行中配置锁定：输出设置/滤镜链/添加文件目录全部禁用，[取消] 唯一
      活动出口；终态后恢复

## 6. 偏差与记录（回填）

- **本批覆盖核对补齐的用例**（tests/test_worker_batch.py，随 CI 执行）：
  单文件失败不中断批处理（failed 记账 + error 上送 + output_path 省略）、
  format 小写 UI 契约、quality 显式转发与缺省不注入、显式不支持扩展名文件
  `FILE_NOT_FOUND`、quality 非整数/布尔与空白路径元素的同步拒绝、steps
  元素非 dict 与 params 非 dict 的同步拒绝。
- **受理回执字段修正（协议 §3.5）**：复查发现文档与测试约定
  `{task_id, total}` 而实现只回 `{task_id, status}`（TaskRuntime.submit
  受理回执形状）——本批已在 `dispatcher.py` 补齐（`job.accepted_extra` 并入
  `total`，dispatcher.py:89-94、287），文档同步为
  `{task_id, status, total}`（docs/ipc-protocol.md §2.3/§3/§3.5）。
- **目录条目行级进度映射限制**：提交清单原样上送 → 目录条目在批次明细中
  只有一行；逐文件进度帧行键（展开后源文件路径）与目录行键不匹配 →
  目录批次运行期间行不翻转、总进度条不动，完成时 items 对账整表刷新
  （batch_service.cpp:132-135 用提交清单建行、batch_model.cpp:76-78 未知
  file 不造行）。显式文件条目不受影响（§2 实测回填观感结论）；改进
  （C++ 预展开或前缀匹配）不在本批。
- **批处理不在任务抽屉**：BatchService 不登记 TaskModel 行
  （AppBatchWizard.qml:34-36），任务抽屉无批处理任务行、无行内取消——
  取消入口只有批量页 [取消] 按钮；离开页面后完成/失败无全局通知（§4）。
- **"完成后打开输出目录"与"失败重试"未实现**：ui-page-spec.md §3 的
  [打开输出目录] 按钮与 [重试失败项] 按钮均未交付——batchFinished 信号
  已挂"打开输出目录"入口注释（batch_service.h:89-91）但 QML 未消费；
  协议无单文件重试动作。均为功能缺口非缺陷，如实记录。
- **覆盖策略无 UI**：1.0 批量面板有覆盖开关；协议 §3.5 有意不暴露
  overwrite 参数（固定覆盖，与 1.0 面板缺省一致）——UI 无对应控件。
- **预设引用不可用滤镜不前置拒绝**：§3 演练的实机结论回填此处（提交
  通过、执行按滤镜实际实现走）。
- **batch.cancel / gmic.check 无 C++ 消费方**：BatchService::cancelBatch 经
  `task.cancel` 转发（batch_service.cpp:88-96，同一 TaskRuntime 取消通道，
  语义一致）；`gmic.check` 仅有协议级验证（§3）。消费接线（设置页外部
  依赖诊断）不在本批。
- **测试注释过期**：tests/native/test_batch_service.cpp:17-23 的"协议状态
  注"（batch.start 尚未进入协议与 dispatcher）是 native 侧先行交付时点的
  快照，现状已过期（协议 §3.5 与 dispatcher 动作表均已交付）；测试本体
  锁定的服务契约不受影响，注释修订不属本批文件清单。
- **已知竞态（如实验收，回填）**：单活动批次语义下"受理响应与取消请求
  赛跑"——向导在 batchStarted 后补发取消意图（AppBatchWizard.qml:946-953），
  服务层翻译仅在活动批次成立（batch_service.cpp:93-94）；大目录受理前
  快速点取消的实际表现回填此处。
- 回填项：CI 实际结果链接与结论（test + native 双 job）；§2-§5 逐项勾选；
  §3 gmic.check 实机输出与置灰演练记录；§5 耗时数据；实际桌面会话
  （X11 / Wayland）→ 直接写入本文件对应小节。
