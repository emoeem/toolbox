# Phase 9 验收清单（Linux 目标环境执行）

> 状态口径：Phase 9 = `code_complete` / `static_reviewed`（总纲 §14.2）。本清单
> 通过后才算 `runtime_verified`；通过前迁移矩阵对应行保持 `待迁移`
> （ui-migration-matrix.md 头部状态取值规则：`已迁移` 要求"新 UI 中真实可用
> 并验收"，CI 单测不构成改判依据）。
> 分工口径：§1 为 CI 已覆盖的逻辑层项（实机不重复执行）；§2 起为必须在 Linux
> 目标环境（真实 Worker 进程 + 真实桌面 GUI 会话）执行的项——按任务要求把
> **目标大小导出实测**单列（§5，含其 fileSize 响应扩展未接线的如实边界）。
> 覆盖范围：Phase 9 编辑补全（分支 `phase9-editing`）四个垂直面：
> ① 检查器"变换"页签——裁剪八手柄 + 比例锁定 / 自由旋转（防抖预览与应用）/
> 透视四角 / 缩放，经新式组合参数 `image.transform`（docs/ipc-protocol.md
> §3.2 Phase 9 增补，两种线形）；② 标注画布模式——八种工具绘制 → 提交
> `image.annotate`（§3.9）→ undo 参数化重放像素一致；③ 对比模式
> AppCompareSlider；④ 保存选项对话框目标大小（`image.save target_kb`，§3.9）。
> **如实边界（撰写本清单时的工作树状态，执行时先复核）**：
> - `image.save target_kb` 的 **C++ 消费侧请求方向已接线**（2026-11-08 修复
>   轮：`saveDocument` 三参 `(path, quality, targetKb)`，>0 随请求携带
>   target_kb；EditorPage 保存选项对话框直调三参，原 try/catch 回退路径
>   移除）；**响应方向仍未接线**：`documentSaved` 信号只携带 `path`
>   （native/core/document_service.h），保存完成 Toast 不显示实际大小
>   （QML 按 undefined 兼容）。§5 据此执行：目标大小落盘/取消/拒绝实测
>   可做，Toast 大小显示项按"fileSize 扩展未合入"如实记录——文件实际
>   大小用 `stat` 核对，不以 Toast 为准。协议级命令（§7）可先行验证
>   Worker 面（与 GUI 无关）。
> - 标注**无 Worker 预览形态**（协议只有全分辨率应用）：画布所见为
>   AppAnnotateOverlay 的本地 Canvas 近似预览层，与 PIL 栅格化结果存在像素级
>   差异属预期——验收以提交后真实像素为准，不以预览逐像素比对。
> - 对比滑块为辅助视图：两侧 PreserveAspectFit 居中，当前图与原图纵横比不同
>   （裁剪/旋转后）时**不逐像素对位**（AppCompareSlider.qml 文件头声明）——
>   如实记录观察，不按"对位失败"记账。
> - 标注 `text` 字形、旋转/透视的插值结果**跨平台有差异**（字体候选链
>   MiSans → Noto CJK → DejaVu → PIL 内置随系统文件而异）：像素一致性断言
>   只在同一台机器内做（undo 重放 vs 应用结果），不跨机锁定。
> 依赖：Phase 5/6A/6B/6C/7 验收截至本清单撰写均**尚未在目标环境执行**。本
> 清单复用其机制：编辑器任务抽屉/Toast/documentActionFailed 在途门（Phase 5）、
> previewReady 临时 PNG 通道（Phase 5/6A 同源）、undo/redo 参数化重放
> （Phase 6+ 机制，Phase 9 扩展 transform/annotate 两类载荷）。
> 实现锚点（行号对齐 2026-11-08 修复轮后的工作树）：Worker 侧
> `python_worker/adapters/image_adapter.py`（组合参数校验
> validate_transform_spec image_adapter.py:576、apply_composite_transform
> image_adapter.py:649、_rotate_free image_adapter.py:674、_perspective_warp
> image_adapter.py:688、标注校验 validate_annotate_ops image_adapter.py:895、
> apply_annotate image_adapter.py:961、target_kb 校验/搜索
> validate_save_target image_adapter.py:1118 / search_quality_for_target
> image_adapter.py:1145、HistoryEntry replay 载荷 transform/annotate
> image_adapter.py:35-66、重放 _replay_apply image_adapter.py:313）与
> `python_worker/dispatcher.py`（target_kb 分支 dispatcher.py:392-421、组合
> 线形分发 dispatcher.py:535-555、_composite_transform_job dispatcher.py:607、
> _image_annotate_job dispatcher.py:655）；C++ 侧
> `native/core/document_service.{h,cpp}`（applyTransform document_service.h:112
> / document_service.cpp:246、applyAnnotate document_service.h:121 /
> document_service.cpp:278、saveDocument 三参 document_service.h:94 /
> document_service.cpp:151、完成路径 handleCompleted ApplyTransform/
> ApplyAnnotate 分支 document_service.cpp:434,459）；QML 侧
> `ui/pages/EditorPage.qml`（画布模式互斥 EditorPage.qml:33-43、refreshPending
> 门控 EditorPage.qml:125-133、setCropMode:335 / setPerspectiveMode:347 /
> setAnnotateMode:359 / setCompareMode:371、requestTransformPreview:387、
> applyCrop:406、applyPerspective:417、pilRotateExpandedSize:451、
> applyFreeRotate:470、applyScale:493、applyAnnotateOps:525、保存选项对话框
> EditorPage.qml:1432-1533）与五个新组件
> `ui/components/AppCropOverlay.qml`（八向手柄 + 整体拖动 + 重新拉框 + 三分线
> + 比例锁定自由/1:1/4:3/3:4/16:9/9:16，AppCropOverlay.qml:382-388）、
> `ui/components/AppPerspectiveOverlay.qml`（四角拖拽 TL,TR,BR,BL 身份固定）、
> `ui/components/AppAnnotateToolbar.qml`（八工具 + 参数 + 撤销上一笔/清空/
> 完成/取消）、`ui/components/AppAnnotateOverlay.qml`（点序列/矩形采集 +
> Canvas 近似预览层）、`ui/components/AppCompareSlider.qml`（分割线 0.02..0.98）；
> 测试锁：`tests/test_worker_transform.py`（23 用例）、
> `tests/test_worker_annotate.py`（19 用例，含 2026-11-08 修复轮 2 例）、
> `tests/native/test_document_service.cpp` Phase 9 三用例
> （applyTransformAndAnnotateLocalRejections / applyTransformDispatchAndCompletion
> / applyAnnotateDispatchAndFailure，ride 既有 document_service CTest 目标）。

## 准备

```bash
cd ~/toolbox
git fetch origin && git checkout phase9-editing
uv sync --extra dev                       # Worker 依赖沿用现有锁定环境
cmake --preset linux-debug && cmake --build --preset linux-debug
```

测试素材：

- 一张几何特征明显的照片（直线/矩形边缘，供透视校正目测）与一张人像或大字
  文本图（供局部模糊/像素化目测）；主验证样本可用 `tools/make_test_samples.py`
  的 gradient/checker/noise。
- 记录每个断言用的机器内基线：**像素一致性断言全部在同一会话内做**
  （应用 → sha256 → undo → sha256 对照，`sha256sum` 临时 PNG 或结果帧的
  `sha256` 字段），不跨机、不跨字体环境。
- §5 步骤要求原生端 `saveDocument` 第三参已合入（2026-11-08 修复轮已随本
  工作树落地）；`documentSaved` 的 `fileSize` 扩展未合入——Toast 实际
  大小显示按未接线如实记录（"已保存：<路径>"无大小），文件字节用
  `stat -c %s` 核对；执行时用 `git log -- native/core/document_service.*`
  复核。

## 1. CI 已覆盖（实机不重复执行；推送后以 GitHub Actions 实际结果为准）

> 以下项由 CI 两个 job 的既有机制自动纳入：test job 的 `unittest discover`
> （ci.yml `discover("tests")`）发现 tests/ 下全部用例；native job 的 CTest
> 既有 `document_service` 目标（tests/native/CMakeLists.txt:104-110）随新用例
> 一并执行。截至本清单撰写，Phase 9 改动尚未提交推送——"CI 已覆盖"均指测试
> 已就位并随既有 CI 机制执行，推送后的实际运行结果回填 §8。

- [ ] Worker 组合变换与 target_kb（Python，`tests/test_worker_transform.py`，
      23 用例，进程内 Dispatcher + TaskRuntime(max_workers=1)，参照
      test_worker_edit.py 风格）：既有五 op 与 processors/core 直调逐位一致、
      既有形式历史仍为无 replay 快照（重放屏障不因 Phase 9 改变）、既有参数
      校验仍提交前同步；组合参数校验 25 例提交前同步 `INVALID_PARAMS`
      （crop 负值/非正/越界/缺键/非对象、角度越界、expand 非布尔、perspective
      点数/形状/非数值/与其它组合键并存、scale 非正/缺键/resample 非法、
      op/params 与组合混用三种形态、嵌套线形同判、未知文档同步
      `UNKNOWN_DOCUMENT`、零任务事件）；嵌套线形与顶层线形逐位一致（C++
      applyTransform 透传形状）；crop 精确像素、scale 四 resample + 同参数
      确定性、rotate_free 90°/45° expand 两态/0° 恒等、45° expand 露出底面
      RGBA 透明/RGB 黑、perspective 恒等/负坐标外扩/梯形三例外接矩形、
      crop→rotate→scale 执行顺序与手工链逐位一致、预览不触碰文档（version 0
      + undo 栈空）、全分辨率快照 + replay 历史形状、组合锚点之上
      filter.apply 保持参数化且 undo/redo 逐位；target_kb：非 JPEG/WebP 扩展名
      拒绝、RGBA→JPEG 拒绝 + WebP 成功（quality/bytes 附加字段、bytes==
      file_size、format 核对 WEBP）、RGB JPEG 二分收敛 + 最优性（quality 达标
      quality+1 超预算）、1 字节预算收敛到下限 30 并如实报告实际字节、取消在
      探测边界检查点生效、target_kb 优先于 quality、无 target_kb 响应形状
      逐字节不变（无新字段）
- [ ] Worker 标注（Python，`tests/test_worker_annotate.py`，19 用例）：八种
      op 逐类型像素效应（pen 中心纯红 + 远离不变 + 参数化条目形状、hex 颜色、
      alpha 混色（[r,g,b,a] 数组与 #RRGGBBAA 同源、alpha=0 恒等、半透明中心
      像素非纯红非源图）、RGB 画布（adjust 后）alpha 混色与 PIL 图层合成
      期望值逐位一致且不退化为不透明（2026-11-08 修复轮补）、rect/ellipse
      描边 vs 填充、arrow 主线 + 头线几何、text 两字号出像素、blur_rect
      区域外逐位不变、pixelate_rect 块内逐位一致）；eraser 恢复源图基线 +
      undo/redo 经参数化重放逐位一致、几何变换后 eraser 降级不越界写、
      adjust 后通道数不一致（RGBA 基线 vs RGB 画布）按前 C 通道恢复
      （2026-11-08 修复轮补）；多次 annotate undo 重绘 ops 前缀 / redo 逐位
      复原；annotate + filter.apply 全参数化栈；组合参数 transform 锚点之上
      annotate 保持参数化（undo 锚点直达 / redo 重放）；既有 op 形式
      transform 之上 annotate 照旧退化为快照（重放屏障）；ops 校验 27 例
      提交前同步 `INVALID_PARAMS`（缺 ops/空/非数组/未知 type/缺键/取值越界/
      颜色非法，消息带下标；未知文档同步拒绝；零任务事件 + 版本未动）；
      生命周期对齐既有任务（受理 `status: 'queued'`、首条 progress、完成
      `{version,width,height}`、modified 置位、task.cancel 语义）、逐 op 协作
      取消文档不动（先算后提交）
- [ ] 既有参数化 undo 机制回归（Python，`tests/test_worker_history_parametric.py`
      既有用例不改动地继续通过——Phase 9 只新增 replay 载荷类别
      transform/annotate 与 `_replay_apply` 的 baseline 形参，既有 chain/adjust
      路径行为不变）
- [ ] C++ 消费侧（CTest，`tests/native/test_document_service.cpp` Phase 9
      三用例，信号模拟不启动 Worker）：本地拒绝契约（无文档/空 params/空 ops
      一律不上送——探针证明未消耗槽位——且恰好一次 documentError + 一次
      documentActionFailed，动作标识含 -preview 后缀各就位）；
      applyTransform 分发与完成（受理建任务行"应用变换"、全分辨率完成递增
      version/置 modified、预览完成只发 previewReady 不触碰 version/modified）；
      applyAnnotate 分发与失败（行名"应用标注"、完成递增 version、无
      previewReady、task.failed → documentError + documentActionFailed 恰好
      一次且状态不动）
- [ ] CI 环境边界（为何仍需实机）：ubuntu runner、Python 测试进程内
      Dispatcher（不启动 QProcess 真实链路）、C++ 测试直接 emit
      BackendManager 信号模拟协议帧、无 GUI（八手柄拖拽/四角拖拽/画布模式
      互斥/工具栏/对话框/Esc 退出/Toast 全不可测）、App* QML 组件无 QML 测试
      机制、字体栅格化随 CI 机器字库。变换/标注/对比/目标大小的跨进程全链路
      （QML 组包 → QProcess + JSON Lines → Worker PIL/cv2 栅格 → 像素回读）
      必须实机（§2-§5）。

## 2. 变换页签端到端（必须实机）

> 前置：Worker 已启动（无降级横幅）、编辑器已打开一张图。全部经检查器
> "变换"页签与画布模式真实控件操作；每次几何应用后核对状态栏 宽×高 与
> 历史面板条目名（"应用变换"/"变换预览"）。

- [ ] **裁剪八手柄 + 比例锁定端到端**：点"裁剪"进入画布模式（其余模式与
      检查器禁用、视图冻结）→ 全图初始选区 + 三分线 + 暗区遮罩呈现 →
      逐一拖四角手柄（对角双向）与四边手柄（单边）→ 尺寸浮条随动 → 拖矩形
      整体移动 → 在暗区重新拉框 → 选比例锁定 4:3 后拖角（选区强制 4:3、
      越界钳回）→ [应用] → 任务抽屉"应用变换"行（queued→running→completed）
      → 画布变为裁剪后图像、状态栏尺寸 = 选区文档像素尺寸、undo 一次回到
      原图（重放屏障不适用——组合 crop 是可重放锚点，undo 直达快照）→
      redo 回裁剪结果。非法提交路径：选区宽或高换算后 <1 文档像素时 [应用]
      如实禁用/提示（AppCropOverlay minSelSize 16 视口像素兜底）
- [ ] **裁剪提交形状核对（协议面抽查）**：应用一次已知选区（如四角对齐
      (16,16)-(48,48) 文档像素）→ 结果尺寸恰为 (32,32) 且左上内容与源图
      (16,16) 对齐（与 §7 协议级 crop 证据互相印证）
- [ ] **自由旋转预览与应用**：拖动角度滑杆（非零角）→ 停 300ms → 预览经
      previewReady 通道刷新（临时 PNG 通道，画布 URL 带 ?v= 重载触发）、
      文档版本不递增、历史面板无新条目；拖动中（未过防抖）无请求风暴
      （任务抽屉无"变换预览"行堆积）；勾选/取消"扩展画布"→ 预览相应
      扩张/保持原尺寸 → [应用] → 版本 +1、状态栏尺寸按 expand 语义更新
      （expand=true 时按 Worker 端实际引擎 PIL `Image.rotate` 的角点外接框
      公式推演——pilRotateExpandedSize，applyFreeRotate 函数旁，2026-11-08
      修复轮由 cv2 截断公式修正，与 Pillow ceil(max(xx))−floor(min(xx))
      一致；核对方式：应用已知尺寸/角度（如 64×64 @45° 应为 92×92）后
      对照状态栏尺寸）
      → undo/redo 像素往返一致（同一会话 sha256 对照）；角度 0 时 [应用]
      如实提示"角度为 0，无需应用"不发任务
- [ ] **透视四角**：点"透视"进入画布模式 → 四角手柄初始在图像四角、四边形
      连线与界外暗化呈现 → 拖动任一角（其余不动、身份固定 TL,TR,BR,BL）、
      角点钳回显示矩形内 → [应用] → 图像按四角重投影、状态栏尺寸 = 四角
      轴对齐包围盒（推演假设见 EditorPage.qml:403-405——Worker 输出画布恒为
      目标四点外接矩形上取整，§3.2，两者一致）→ undo 回原图 →
      **如实记录**：若状态栏尺寸与实际结果短暂失准（推演镜像与 Worker 取整
      差 1px 内），按"下次打开自愈"记账而非失败
- [ ] **缩放**：宽高数值框 + resample 下拉（lanczos/bilinear/nearest/bicubic）
      → [应用] → 尺寸精确等于输入、undo 往返一致；非法输入（0/负）本地
      提示不上送
- [ ] **画布模式互斥与退出**：四模式（crop/perspective/annotate/compare）
      同时只能激活其一；Esc/取消退出后工具栏缩放按钮与检查器恢复、
      恢复期间无陈旧选区残留；模式内滚轮不缩放画布（视图冻结假设成立）
- [ ] **刷新窗口门控（2026-11-08 修复轮）**：大图上提交一次改变尺寸的
      全分辨率变换（如 crop/scale）→ 完成后、画布刷新预览到达前这一窗口
      （大图可达数百毫秒）内"进入裁剪模式/进入透视模式/标注"按钮如实
      禁用、程序化进入（setCropMode 等）被拦；刷新预览到达后按钮恢复、
      此时进入画布模式拖框选区换算与文档像素一致；已处于画布模式时
      退出方向（Esc/取消）不受该门控影响
- [ ] **失败呈现**：断开后端（设置页停 Worker）后提交变换 → 错误 Toast
      `code · message` + 在途门解除（documentActionFailed 通道）；恢复后端
      重试成功
- [ ] **undo 参数化重放像素一致（变换面）**：crop + rotate_free + scale
      一次组合（页签只单键提交，此处经 §7 协议级组合命令补）→ 依次 undo
      到 open 态 → 逐步 sha256 与应用后记录一致 → redo 逐步逐位复原
      （组合变换为确定性函数，§3.2 参数化历史）

## 3. 标注端到端（必须实机）

> 工作流：点"标注"进入画布模式 → AppAnnotateToolbar 选工具调参 → 画布
> 绘制（Canvas 近似预览层即时呈现）→ [完成标注] 一次全分辨率提交
> （image.annotate，无 Worker 预览形态）→ 任务行"应用标注" → 画布刷新为
> 真实结果 → undo/redo。预览与最终像素的栅格化差异属预期（如实边界）。

- [ ] **八工具逐个 绘制 → 提交 → undo 参数化重放像素一致**：对 pen /
      rect（描边与填充各一）/ ellipse / arrow / text / blur_rect /
      pixelate_rect / eraser 各执行一轮：
      ① 绘制（记录画布近似预览观感）；② 提交前用 `sha256sum` 记录当前
      文档导出基线（或经 §7 协议级 history 比对）；③ [完成标注] → 版本
      +1；④ 观察真实像素效果（pen 圆头线、rect 边框 vs 实心、arrow 主线 +
      头线、text 真字形、blur 区域平滑、pixelate 块状、eraser 恢复底图）；
      ⑤ undo 一次 → 导出当前文档核对 sha256 与 ② 完全一致（参数化重放
      从锚点/基线重绘 ops 前缀，§3.9）；⑥ redo → 与 ③ 后 sha256 一致
      （逐位复原）。**每工具的 ⑤⑥ 必须各自留 sha256 证据**
- [ ] **eraser 语义三态**：在源图上画 pen 后用更宽 eraser 同路径擦除 →
      回到源图像素（恢复 open 态基线）；先调整应用（RGB 画布）再标注用
      eraser → 恢复源图 RGB 分量（基线 RGBA 与画布通道数不一致按前 C 通道
      恢复，2026-11-08 修复轮语义）；对已裁剪文档（先 crop 再标注）用
      eraser → 如实观察"只等效恢复本动作前像素"的降级（不越界写、不崩溃）
- [ ] **待提交栈 vs 已提交撤销**：绘制数笔 → 工具栏[撤销上一笔]只弹回
      **待提交** ops 栈顶（预览层回退、无任务产生）；[清空] 清空待提交；
      [完成标注] 提交后的撤销走编辑器既有 undo（Worker 参数化重放）——
      两套撤销语义互不混淆
- [ ] **颜色与参数**：AppColorField 六位 hex（含 #RRGGBBAA 透明度，透明笔触
      混色呈现；RGB 画布（调整应用后）上透明笔触仍应呈混色而非不透明——
      2026-11-08 修复轮语义）、粗细/字号/强度/块大小滑杆范围与协议一致
      （粗细 ≥1、字号 1..512、强度 (0,100]、块 ≥2）——超界值由控件量程
      拦住，不上送
- [ ] **提交门控**：无文档/后端未就绪/在途时 [完成标注] 如实禁用；空 ops
      时不可提交；提交期间画布模式控件在途门锁定（fullResInFlight），
      完成或失败后解锁
- [ ] **失败与取消**：提交注定失败 ops（如经协议级构造——UI 控件拦不住的
      输入）→ `INVALID_PARAMS`/`ENGINE_ERROR` Toast + 在途门解除、文档状态
      不动；标注任务进行中行内 [取消] → `CANCELLED` → 像素与版本不变
      （先算后提交）

## 4. 对比滑块（必须实机）

- [ ] **进入与退出**：打开图并做至少一次调整/变换 → 点"对比"进入对比模式
      （其余交互禁用）→ 左侧原图（打开时本地文件）右侧当前图，分割线可
      拖动（0.02..0.98 钳制）→ Esc 或再点工具栏按钮退出、交互恢复
- [ ] **未编辑文档的对比**：刚打开未编辑时进入对比 → 两侧内容一致（原图 ==
      当前图）如实呈现
- [ ] **纵横比不同后的对比（如实记录）**：裁剪或旋转后进入对比 → 两侧按
      各自外接框居中、不逐像素对位——按 AppCompareSlider 文件头声明的辅助
      视图语义记录，不按缺陷记账
- [ ] **预览与对比的协同**：对比模式的"当前图"取画布当前 source（最近一次
      预览文件）；调整滑杆拖动后退出对比 → 画布与对比一致

## 5. 目标大小导出实测（必须实机；fileSize 响应扩展未合入为如实边界）

> 如实边界见头部：`saveDocument` 第三参（target_kb 请求方向）已随
> 2026-11-08 修复轮接线，原 (a) "回退路径"观察项随之作废删除（该路径
> 已不存在）；`documentSaved` 的 `fileSize` 扩展未合入——完成 Toast 只
> 显示"已保存：<路径>"，**文件大小一律以 `stat -c %s` 核对为准，不以
> Toast 为准**。Worker 面可随时用 §7 协议级命令先行验证。

- [ ] **限制目标大小端到端**：[另存为] → 保存选项对话框勾选"限制目标大小
      （KB）"（字段随之启用，量程 1..1048576、步长 64）→ 确定 →
      - RGB 文档另存 `.jpg` 目标 200 KB → 落盘文件 ≤ 200×1024 字节
        （`stat -c %s` 核对）、协议级/任务抽屉核对响应 `bytes` == 实际
        字节 == `file_size`、同图更高目标（如 1 MB）得到更高质量
        （quality 单调）
      - `.webp` 同测；RGBA 文档（未拍平）另存 `.jpg` → `INVALID_PARAMS`
        Toast（保 alpha 用 WebP）；`.png` + 目标大小 → `INVALID_PARAMS`
        （无损格式无 quality 旋钮）
      - 目标 1 KB（必不可达）→ 按 quality 30 落盘、响应如实报告
        实际字节（大于预算、不谎报达标）
      - 大图目标大小的保存任务可取消：行内 [取消] → `CANCELLED`、无残文件
      - **不勾选开关**（"空=不限"语义）→ 请求不携带 target_kb（§7 向后
        兼容抽查同源），按格式默认质量保存
- [ ] **响应形状回归**：不勾选限制的普通保存 → 行为与响应形状与 Phase 5
      完全一致（无 quality/bytes 字段路径，QML 兼容；完成 Toast 为
      "已保存：<路径>"——fileSize 扩展未接线，按边界如实记录）

## 6. 非模态、导航与恢复（必须实机）

- [ ] **非模态**：变换/标注全分辨率任务进行中（大图放大慢放）切到首页/
      工具页 → 任务继续；画布模式期间应用切换不产生半途状态
- [ ] **重进恢复**：任务在途时切页再回编辑器 → 在途门与任务行仍在；
      完成后画布刷新
- [ ] **Worker 崩溃恢复**：变换/标注在途时杀 Worker → Toast（code ·
      message）+ 在途门立即解除 + 可再次提交；重启后文档需重新打开
      （UNKNOWN_DOCUMENT 兜底语义，与 Phase 5 口径一致）
- [ ] **主题与缩放**：深浅主题切换后变换页签/标注工具栏/对比分割线/保存
      对话框渲染一致；窗口缩放下叠加层显示矩形推演与手柄命中不漂移
      （视图冻结期间不缩放；缩放只发生在退出画布模式后）

## 7. 协议级实机验证（补 CI 不触达的真实进程链路）

> 真实 Worker 进程（QProcess 之外的直接管道形态）验证协议面与 GUI 组包的
> 一致性；`<doc>` 用 image.open 返回的 document_id 替换。

```bash
cd ~/toolbox
# 组合变换（顶层线形）：crop → rotate_free
echo '{"protocol":1,"request_id":"req-p1","action":"image.open","params":{"path":"<样本图>"}}' | \
  uv run python python_worker/main.py --repo-root .
echo '{"protocol":1,"request_id":"req-p2","action":"image.transform","params":{"document_id":"<doc>","crop":{"x":8,"y":8,"width":32,"height":16},"rotate_free":{"angle":90,"expand":true},"preview":false}}' | \
  uv run python python_worker/main.py --repo-root .
# 组合变换（嵌套线形，C++ applyTransform 透传形状）：与 p2 同参数应逐位一致
echo '{"protocol":1,"request_id":"req-p3","action":"image.transform","params":{"document_id":"<doc>","params":{"crop":{"x":8,"y":8,"width":32,"height":16},"rotate_free":{"angle":90,"expand":true}},"preview":false}}' | \
  uv run python python_worker/main.py --repo-root .
# 标注：提交 → completed result {version,width,height}
echo '{"protocol":1,"request_id":"req-p4","action":"image.annotate","params":{"document_id":"<doc>","ops":[{"type":"rect","x":4,"y":4,"width":16,"height":8,"color":[255,0,0],"stroke_width":2,"fill":false}]}}' | \
  uv run python python_worker/main.py --repo-root .
# target_kb：保存为 webp，核对 bytes == file_size == stat 字节数
echo '{"protocol":1,"request_id":"req-p5","action":"image.save","params":{"document_id":"<doc>","path":"/tmp/p9-target.webp","target_kb":16}}' | \
  uv run python python_worker/main.py --repo-root .
# 提交前同步拒绝：组合 + op 混用 / 未知标注类型 / 越界 crop
echo '{"protocol":1,"request_id":"req-p6","action":"image.transform","params":{"document_id":"<doc>","op":"flip_h","params":{},"crop":{"x":0,"y":0,"width":8,"height":8},"preview":false}}' | \
  uv run python python_worker/main.py --repo-root .
echo '{"protocol":1,"request_id":"req-p7","action":"image.annotate","params":{"document_id":"<doc>","ops":[{"type":"spray","points":[[0,0],[1,1]]}]}}' | \
  uv run python python_worker/main.py --repo-root .
```

- [ ] p2/p3 返回 `{version,width,height}` 且两者对同一文档状态输出逐位一致
      （先 reset 再跑 p3 对照 sha256）；p4 完成后 undo 一次恢复（协议级
      `image.undo`），undo 前后导出像素与 GUI 面一致；p5 响应 `bytes` ==
      `file_size` == `stat -c %s /tmp/p9-target.webp` 且 ≤ 16×1024；p6/p7
      同步返回 `INVALID_PARAMS`、无 task_id
- [ ] **向后兼容抽查**：仅携带既有 `op`/`params` 的 transform 请求（如
      `{"op":"flip_h","params":{}}`）与不携带 target_kb 的 save 请求在
      Phase 9 Worker 上行为与响应形状和 Phase 5/7 记录逐字节一致

## 8. 偏差与记录（回填）

- **本批复核对补齐的用例**（随 CI 执行）：tests/test_worker_transform.py
  21 → 23 用例（rotate_free 露出底面 RGBA 透明/RGB 黑、target_kb 二分探测
  边界取消）；tests/test_worker_annotate.py 15 → 17 用例（alpha 第 4 分量
  混色与 #RRGGBBAA、组合参数 transform 锚点之上 annotate 保持参数化）。
- **修复轮（2026-11-08）补齐的用例**（随 CI 执行）：tests/test_worker_annotate.py
  17 → 19 用例（RGB 画布 alpha 混色与 PIL 图层合成期望逐位一致、adjust 后
  通道不一致基线的 eraser 恢复 + 重放一致）。
- **修复轮（2026-11-08）行为修正**（协议形状不变，均为实现/消费侧对齐）：
  ① EditorPage applyFreeRotate 的 expand 输出尺寸推演由 processors/core 的
  cv2 截断公式改为 Worker 实际引擎 PIL `Image.rotate` 的角点外接框公式
  （64×64@45°：90 → 92，与 Worker 输出一致）；② eraser 基线恢复的降级
  条件由 `shape` 全等（把通道数混入）改为几何一致 + 通道裁剪（RGBA 基线 ×
  RGB 画布恢复源图，§3.9 eraser 行同步）；③ RGB 画布上 alpha < 255 的
  混色路径恒用 4 元组墨水（此前 3 元组墨水使半透明退化为不透明落笔，
  §3.9 颜色注同步）；④ `DocumentService::saveDocument` 补第三参
  `targetKb`（>0 随请求携带 target_kb）——EditorPage 防御性 try/catch
  回退移除（其注释曾把"Q_INVOKABLE 多余实参同步抛 TypeError"写成定论，
  该运行时行为从未实机核实，QV4 历史行为更可能是静默丢弃多余实参——
  两种观察都不可再触发，路径已删除）；⑤ 画布模式入口（crop/perspective/
  annotate）补 refreshPending 门控（全分辨率应用完成 → 刷新预览到达的
  窗口期 k 因子失配不可进入拉框）。
- **协议复查修订**（docs/ipc-protocol.md §3.9 末消费侧复查注，均为现状
  对齐、协议形状不变）：`target_kb` 的 C++ 消费侧请求方向已接线（
  saveDocument 三参，2026-11-08 修复轮），响应方向 `documentSaved` 无
  fileSize——Toast 实际大小显示待扩展；transform/annotate 消费侧已接线
  （applyTransform 嵌套线形 / applyAnnotate）与 §3.2/§3.9 一致。
- **rect/ellipse 描边键名消解**：任务书字面 schema 的重复 `width` 按
  "几何 width + 描边 stroke_width"实现并在 §3.9 注明（三端同源）。
- 回填项：CI 实际结果链接与结论（test + native 双 job）；§2-§5 逐项勾选与
  sha256 证据；§5 限制目标大小实测记录（文件字节以 `stat` 为准，Toast 无
  大小显示属 fileSize 未接线边界）；§7 协议级输出；实际桌面会话
  （X11 / Wayland）→ 直接写入本文件对应小节。
