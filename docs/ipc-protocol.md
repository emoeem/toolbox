# IPC 协议规范（Phase 3 交付物）

> 状态：`code_complete`（Phase 3 范围内协议与两端实现同步交付；跨进程验收在 Linux 目标环境）
> 实现位置：`python_worker/`（Python 侧）与 `native/backend/`（C++ 侧）。
> 修改本文件必须同步更新两端实现、测试与版本兼容逻辑（总纲 §16.3）。
>
> Phase 4 定义、Phase 5（分支 `phase4-ui-infra`）两端落地：§3 新增
> `image.adjust` / `image.transform` / `image.undo` / `image.redo` /
> `image.reset` / `image.history` 与 `version` 字段，`protocol` 保持 `1`。
> 两端实现与两端测试已同步：Worker 侧 `python_worker/dispatcher.py`（动作表）
> 与 `python_worker/adapters/image_adapter.py`，C++ 侧
> `native/core/document_service.cpp`；测试锁为 `tests/test_worker_edit.py`
> 与 `tests/native/test_document_service.cpp`。

## 1. 传输

- C++ 通过 QProcess 启动 Worker：`<python> <repo>/python_worker/main.py [options]`。
- 控制消息：**stdin/stdout 上的 JSON Lines**（每行一个 UTF-8 JSON 对象，`\n` 结尾）。
- stdout 只写协议消息；日志/调试一律写 stderr（`type:"log"` 事件不占用 stdout）。
- 消息必须有 `protocol` 字段；本版本 `protocol = 1`。
- Worker 不得依赖当前工作目录定位 processors（`main.py` 自行把仓库根加入
  `sys.path`，也可用 `--repo-root` 显式指定）。

Worker 启动参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--repo-root <path>` | 自动推断 | processors/backends 所在根目录 |
| `--max-workers N` | 2 | 任务线程池大小 |
| `--temp-dir <path>` | 系统临时目录 `toolbox-worker-<pid>` | 预览/结果临时文件根目录 |
| `--idle-timeout <sec>` | 0（禁用） | 空闲自动退出（Phase 8 打包后启用） |

## 2. 消息类型

### 2.1 请求（C++ → Worker）

```json
{
  "protocol": 1,
  "request_id": "req-0001",
  "action": "image.open",
  "params": { "path": "/tmp/a.png" }
}
```

`request_id` 由 C++ 生成（如 `req-<序号>`），Worker 原样回传。

### 2.2 同步响应（Worker → C++）

```json
{
  "protocol": 1,
  "request_id": "req-0001",
  "success": true,
  "result": { "document_id": "doc-a1b2" }
}
```

```json
{
  "protocol": 1,
  "request_id": "req-0002",
  "success": false,
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "文件不存在: /tmp/x.png",
    "details": {}
  }
}
```

### 2.3 异步任务

长耗时动作的响应立即返回 `task_id`，随后以事件推送生命周期：

```json
{ "protocol": 1, "request_id": "req-0003", "success": true,
  "result": { "task_id": "task-0001", "status": "queued" } }
```

```json
{ "protocol": 1, "type": "task.progress", "task_id": "task-0001",
  "progress": 45, "message": "Rendering preview" }
{ "protocol": 1, "type": "task.completed", "task_id": "task-0001",
  "result": { "path": "/tmp/toolbox-worker-123/prev.png", "width": 384, "height": 256, "sha256": "…" } }
{ "protocol": 1, "type": "task.failed", "task_id": "task-0001",
  "error": { "code": "CANCELLED", "message": "任务已取消", "details": {} } }
```

状态机（总纲 §6.4）：`queued → running → completed | failed`；
`queued|running → cancelling → cancelled`。

动作可在 `task.progress` 事件上附加该动作特有的字段（当前仅批处理任务，
见 §3.5）；受理响应的 `result` 同样可携带动作特有字段（当前仅 `batch.start`
的 `total`，§3.5）。消费方按既有字段解析，必须忽略未知字段。终态仍只由
`task.completed` / `task.failed` 表达，progress 事件永不改变状态机。

全分辨率变更类动作（规则见 §3.1）的 `task.completed` 事件 `result` 一律携带
`version`（文档版本；`preview=true` 的 `image.*` 任务同样携带 `version`，但为
执行时的当前版本——与预览所据像素一致，不递增；`filter.preview` 的 `result`
形状不变，不含 `version`）。
`image.undo` / `image.redo` / `image.reset` 完成时还携带画布刷新所需的文件
信息（形状见 §3.3）；`image.adjust` / `image.transform` 的 result 形状见 §3.2
（仅 `preview=true` 携带 `path/sha256`，全分辨率完成不含像素文件）：

```json
{ "protocol": 1, "type": "task.completed", "task_id": "task-0002",
  "result": { "version": 3, "width": 1024, "height": 768, "path": "…", "sha256": "…" } }
```

（上例为 undo/redo/reset 的 completed result；`image.adjust` /
`image.transform` 全分辨率完成的 result 仅含 `version/width/height`，见 §3.2。）

### 2.4 其他事件

```json
{ "protocol": 1, "type": "log", "level": "warning", "message": "…" }
```

## 3. 动作

| 动作 | 类型 | 参数 | 结果 / 事件 |
|---|---|---|---|
| `worker.hello` | sync | `{}` | `{worker_version, protocol, engine: {numpy, cv2, numba}, pid}` |
| `worker.shutdown` | sync | `{}` | `{ok: true}` 后 Worker 退出 |
| `capabilities.list` | sync | `{}` | `{actions: [...], filter_count, engine: {...}}` |
| `image.open` | sync | `{path}` | `{document_id, width, height, format, file_size}` |
| `image.close` | sync | `{document_id}` | `{closed: true}` |
| `image.metadata` | sync | `{document_id}` | `{width, height, format, mode, source, modified}` |
| `image.save` | async | `{document_id, path, quality?}` | `{saved: true, path, file_size}` |
| `filter.list` | sync | `{}` | `{filters: [{key, name, category, params, available, optional_deps, description}]}` |
| `filter.presets.list` | sync | `{}` | `{presets: [{name, step_count}]}`（§3.4） |
| `filter.presets.save` | sync | `{name, steps: [{filter_key, params, enabled}]}` | `{saved: true, name}`（steps 逐项经 `FilterStep.from_dict` 校验，非法 → `INVALID_PARAMS`，§3.4） |
| `filter.presets.load` | sync | `{name}` | `{name, steps: [{filter_key, params, enabled}]}`（预设不存在 → `FILE_NOT_FOUND`，§3.4） |
| `filter.presets.delete` | sync | `{name}` | `{deleted: true}`（预设不存在 → `FILE_NOT_FOUND`，§3.4） |
| `filter.preview` | async | `{document_id, filters: [{filter_key, params, enabled}], max_side?}` | `{path, width, height, sha256, preview_of}` |
| `filter.apply` | async | `{document_id, filters: [...]}` | `{width, height, version}`（文档像素被更新，`modified=true`；`version` 规则见 §3.1） |
| `image.adjust` | async | `{document_id, adjustments: {brightness?, contrast?, saturation?, gamma?, exposure?, hue?, vibrance?, highlights?, shadows?}, preview, max_side?}` | `{version, width, height, path?, sha256?}`（§3.2；`preview=true` 时含 `path/sha256`） |
| `image.transform` | async | `{document_id, op, params, preview, max_side?}` | 同 `image.adjust`；`op`/`params` 约束见 §3.2 |
| `image.undo` | async | `{document_id}` | `{version, width, height, path, sha256}`（栈空 → 同步 `UNREDOABLE`，§3.3） |
| `image.redo` | async | `{document_id}` | 同 `image.undo` |
| `image.reset` | async | `{document_id}` | 同 `image.undo`（恢复初始状态并清空历史） |
| `image.history` | sync | `{document_id}` | `{entries: [{index, name}], current, canUndo, canRedo}`（§3.3） |
| `task.cancel` | sync | `{task_id}` | `{cancelling: true}` |
| `task.query` | sync | `{task_id}` | `{task_id, status, progress}` |
| `batch.start` | async | `{paths, output_dir, format, quality?, naming?, pattern?, steps?}` | `{task_id, status, total}`（受理回执；进度/终态事件增补批处理字段，§3.5） |
| `batch.cancel` | sync | `{task_id}` | `{cancelled}`（§3.5） |
| `gmic.check` | sync | `{}` | `{available, version, source}`（§3.6） |
| `generate.list` | sync | `{}` | `{generators: [{key, name, category, category_label, description, available, optional_deps, params}]}`（§3.7） |
| `generate.render` | async | `{generator_key, params?, width, height}` | `{task_id, status}`（受理回执）；完成 result `{path, width, height, sha256, generator_key}`（§3.7） |

动作集合按阶段扩展（总纲 §6.2）；禁止各页面私自定义协议动作。

本轮增补为**纯新增动作 + `filter.apply` 结果新增 `version` 字段**：不删除字段、
不改既有字段语义，`protocol` 保持 `1`（符合 §8 兼容性规则）。

Phase 5（分支 `phase5-core-editing`）再增补：§3.4 新增 `filter.presets.list /
save / load / delete` 四个 sync 动作。同样为纯新增动作，不改动既有动作，
`protocol` 保持 `1`；Worker（Python）侧实现于
`python_worker/adapters/filter_adapter.py`（预设封装，复用
`processors/filter_presets.py` 既有持久化）与 `python_worker/dispatcher.py`
（动作表），测试锁为 `tests/test_worker_presets.py`。C++/QML 侧消费随滤镜链
页面接线交付（ui-component-spec.md §3：AppFilterChainItem 为 Phase 6 交付；
2026-11-07 本批已随滤镜页签接线交付该消费侧——FilterModel / FilterService 与
AppFilterCard / AppFilterParameterGroup / AppFilterChainItem /
AppFilterInspector，批次口径见 CHANGELOG 同日 Phase 6A 条目）。

Phase 6（总纲 §13 第 6-7 项：G'MIC 依赖探测与 Batch Processing）本轮增补：
§3 新增 `batch.start` / `batch.cancel`（§3.5）与 `gmic.check`（§3.6），§2.3
允许任务事件携带动作特定增补字段。仍为纯新增：不删除字段、不改既有字段
语义，`protocol` 保持 `1`（§8 兼容性规则）。Python 侧实现于
`python_worker/adapters/batch_adapter.py` 与 `python_worker/dispatcher.py`
（动作表），复用 1.0 资产——`processors/batch_filter_chain.py`
`run_batch_filter_chain`（逐文件 load → 链 → save 与逐项记账；本批仅为其补
`quality` / `output_name_fn` 两个可选参数）、`processors/batch.py`
`batch_rename` 的 pattern 占位符语义、`processors/cancellation.py`
`CancelToken`、`processors/gmic.py`（CLI 探测）；测试锁为
`tests/test_worker_batch.py`。C++ 侧批处理消费实现于
`native/services/batch_service.cpp` 与 `native/models/batch_model.cpp`
（逐文件行模型，测试锁 `tests/native/test_batch_service.cpp` /
`test_batch_model.cpp`，与本节字段同步交付）；既有 `TaskModel`
（`native/models/task_model.cpp`）只消费 `task.progress` 的 `progress`
字段，本节增补字段对其为向后兼容的纯新增（消费方忽略未知字段）。

Phase 6B 复查（2026-11-07，与本节实现逐字段核对后的修订）：§3 表与 §3.5 的
`batch.start` 受理回执补 `status` 字段（实现 `TaskRuntime.submit` 的回执含
`status: "queued"`，`Dispatcher` 经 `job.accepted_extra` 并入 `total`——此前
文档写 `{task_id, total}`、测试断言 `total` 而实现漏交，现三方一致）。消费侧
现状如实记录：C++ `BatchService::cancelBatch` 经 `task.cancel` 转发
（`native/services/batch_service.cpp:88-96`，与 `batch.cancel` 同一
TaskRuntime 取消通道、语义一致），`batch.cancel` 与 `gmic.check` 动作本身
目前没有 C++ 调用方——G'MIC 置灰路径消费的是 `filter.list` 的
`available`/`optional_deps`（Phase 6A 交付口径），`gmic.check` 为设置页
"外部依赖"分组的规划数据源（ui-page-spec.md §4），尚未接线。

Phase 6（总纲 §13 迁移顺序第 8-11 项：Fractal / Texture / Shader Studio 与
Gradient 等参数驱动生成器的统一目录与渲染，Phase 6C 批次）本轮增补：§3 新增
`generate.list` / `generate.render`（§3.7）。仍为纯新增
动作，不改动既有动作，`protocol` 保持 `1`（§8 兼容性规则）。Python 侧实现于
`python_worker/adapters/generate_adapter.py` 与 `python_worker/dispatcher.py`
（动作表），复用 1.0 资产——`processors/fractal.py`（公式表 +
`render_fractal` / `render_mandelbulb`）、`processors/texture_studio/`
（`presets.py` 预设表 + `generators.generate`）、`processors/gradients.py`
（linear/radial/mesh + MESH_PRESETS）、`processors/shader_studio/`（依赖标注，
Worker 侧降级为不可用）、`processors/filter_defs.py` `FilterParam.validate`
（参数取值域校验）与 `python_worker/adapters/filter_adapter.py`
`write_preview`（§4 临时 PNG 通道）；测试锁为 `tests/test_worker_generate.py`。
C++ 侧消费实现于 `native/services/studio_service.cpp`（generate.render 上送
`generator_key/params/width/height`，完成事件取 `path` 交付预览）与
`native/models/generator_model.cpp`（generate.list 结果驱动目录行模型），
与本节字段同步交付。总纲 Phase 6 清单中的 photomosaic / fusion 在 1.0 资产
（`processors/parity.py:319` / `:474`）中是文件→文件工具而非参数驱动的
生成器，不注册（不凭空造实现）。

Phase 6C 复查（2026-11-07，与本节实现逐字段核对后的增补）：`params` 中
`color` 类型条目的取值形状按 `FilterParam._validate_color` 的既有词汇双向
接受——`[r,g,b]` 整数数组（0-255）**或** `#RGB/#RRGGBB/#RRGGBBAA` hex 文本；
QML 参数面板（AppFilterParameterGroup）对 color 类型发送 hex 文本，Worker
渲染侧经 `generate_adapter._hex_to_rgb` 归一为元组后交给 processors（processors
各实现按数组消费，不接受 hex 字符串）。消费侧现状如实记录：C++ 的
`notifyPreviewReady` 另接受完成 result 的 `data` 字段作为 `path` 缺失时的
内联兜底（studio_service.cpp:209-223，test_studio_service.cpp 锁定）——
`data` **不在本节协议形状内**（§4 禁止 Base64 大图），Worker 实现也从不
发送，该分支仅为消费方防御路径，按"消费方忽略未知字段"口径如实记录。
`generate.list` 条目的 `description` 字段当前无 UI 消费（GeneratorModel
角色面不含该字段），协议面保留。

### 3.1 文档版本（document version）

每个打开的文档持有一个整数 `version`（Worker 内存态，随文档关闭与进程退出消亡）：

- `image.open` 时 `version = 0`。
- 以下动作**全分辨率成功完成后** `version += 1`：`filter.apply`、
  `image.adjust`（`preview=false`）、`image.transform`（`preview=false`）、
  `image.undo`、`image.redo`、`image.reset`。
- 预览类任务（`filter.preview`、`preview=true` 的 `image.*` 任务）**不递增**
  版本；`preview=true` 的 `image.*` 任务 `result.version` 为执行时的当前版本
  （与预览所据像素一致；`filter.preview` 的 `result` 不含 `version` 字段，
  保持原形状）。
- `image.save` 只写文件、不改像素，不递增版本。
- 递增与像素是否"回到旧值"无关：undo/redo/reset 同样递增——`version` 是
  画布/缓存失效与旧任务结果丢弃的依据，不是内容指纹（总纲 §6.4）。

### 3.2 image.adjust / image.transform

`image.adjust`（async）一次提交一组全局调整：

- `adjustments` 至少提供一个键，键值均为数值；空对象、未知键或非数值 →
  `INVALID_PARAMS`（提交任务前同步返回）。九个键的取值语义与
  `processors/core.py` 的对应实现一致（brightness / contrast / saturation /
  gamma / exposure / hue / vibrance / highlights / shadows）。
- `preview=true`：走降采样预览管线（复用 `processors/filter_chain_task.py`
  的 `downscale_preview`，`max_side` 缺省 768），结果写入 §4 临时预览文件；
  `result = {version, width, height, path, sha256}`，`width/height` 为预览图
  尺寸；文档像素与 `version` 不变。
- `preview=false`：全分辨率应用到文档（`modified=true`，`version += 1`）；
  `result = {version, width, height}`。

`image.transform`（async）按 `op` 做几何变换。`op` 与 `params` 必需键的对应
关系如下；未知 `op`、缺少必需键或取值非法 → `INVALID_PARAMS`（提交前同步返回）：

| op | params 必需键 | 说明 |
|---|---|---|
| `rotate` | `angle` | 旋转角度（度，顺时针为正） |
| `flip_h` / `flip_v` | 无 | 水平 / 垂直镜像 |
| `scale` | `sx` | 等比缩放因子（> 0） |
| `crop` | `x`, `y`, `w`, `h` | 图像坐标目标矩形（`w`, `h` > 0，须落在当前图像内） |

`preview` 语义与 `image.adjust` 一致（降采样预览 / 全分辨率应用二选一），
`result` 形状相同；`width/height`：预览时为预览图尺寸，全分辨率时为应用后的
文档尺寸（`rotate` / `scale` / `crop` 会改变尺寸）。

### 3.3 文档历史（image.undo / image.redo / image.reset / image.history）

每个文档在 Worker 内持有一份历史栈（像素快照留在 Worker 进程内，不跨进程
复制大图；栈容量与内存预算为 Worker 内部策略，非协议字段）：

- `entries[0]` 固定为初始状态（`image.open` 时的像素，`name = "open"`）；
  其后每个条目对应一次全分辨率变更（`filter.apply`、全分辨率
  `image.adjust` / `image.transform`），`name` 为产生该条目的动作名，
  本地化显示由 C++/QML 侧负责。
- 当前状态为 `entries[current]`；`canUndo = current > 0`，
  `canRedo = current < len(entries) - 1`。
- 在 `current` 非栈顶时发生新的全分辨率变更：截断 `current` 之后的 redo
  分支，追加新条目并将 `current` 指向它（与主流编辑器行为一致）。

| 动作 | 行为 | completed result |
|---|---|---|
| `image.undo` | 恢复 `entries[current - 1]` 的像素 | `{version, width, height, path, sha256}` |
| `image.redo` | 恢复 `entries[current + 1]` 的像素 | 同 `image.undo` |
| `image.reset` | 恢复初始状态并清空全部历史（`entries` 仅剩初始状态，`canUndo = canRedo = false`） | 同 `image.undo` |

- 栈空（`image.undo` 时 `current == 0`；`image.redo` 时 `current` 已在末尾）
  在**提交任务前同步判定**：直接返回 `UNREDOABLE` 错误响应，不产生任务
  （与 `filter.preview` 的链参数校验在提交前报错的先例一致，见
  `python_worker/dispatcher.py` 的预览任务工厂）。
- 三者完成时 `version += 1`（§3.1），并写一份恢复后图像的降采样预览文件
  （§4）供画布立即刷新；`width/height` 为恢复后的文档尺寸（预览文件尺寸以
  文件自身图像头为准）。
- `modified` 语义（两端一致）：`image.reset` 恢复源图后文档不再有未保存
  修改——后续 `image.metadata` 返回 `modified=false`，C++ 端据完成事件清除
  未保存标记（`●` 熄灭、保存禁用）；undo/redo 不清除 `modified`（恢复的是
  历史中间态，非源图）。
- `image.history`（sync）：返回 `{entries: [{index, name}], current, canUndo,
  canRedo}`，`index` 即 `entries` 下标。C++ 端以此驱动 HistoryModel 与
  撤销/重做按钮启停（ui-page-spec.md §2）。

Phase 6+ 改进批次（2026-11-07，docs/competitive-analysis.md §4 行动项 1/2 落地）
对本节的两点 Worker 内部策略修订——**协议形状不变**（动作、参数、completed
result、history result 均与上文一致，`protocol` 保持 `1`），仅可观测行为
按下列口径变化，两端实现与测试已同步（Worker 侧
`python_worker/adapters/image_adapter.py` HistoryMixin，测试锁为
`tests/test_worker_history_parametric.py`；C++ 侧无源码改动，消费侧契约
锁为 `tests/native/test_document_service.cpp`）：

1. **滤镜链参数化 undo**：`filter.apply` 的历史条目只存链 steps 参数
   （协议 `filters` 数组的深拷贝），不保留像素快照；`image.undo` 对参数化
   条目从重放基线（源图 open 态）或最近的快照锚点重放链复原像素，重放
   复用与原应用同一条运行路径（`FilterChain` + `run_filter_chain_sync`），
   确定性逐位一致。像素快照仅保留给不可参数化操作（`image.transform` /
   crop 类，scale/crop 有损、参数重放不可靠——"重放屏障"；其上的链条目
   退化为快照条目）。全分辨率 `image.adjust` 条目仍是快照条目，但额外
   携带 adjustments 作重放参数（可无损确定性重放），使其上的链条目可以
   参数化。内存从 O(像素×历史) 降到 O(参数)（8000×5000 大图 undo 的主要
   出路）；字节预算（§3.3 上文，512MB）只计快照条目。对协议的可见影响：
   - `image.history` 的条目名不变（参数化链条目仍叫 `filter.apply`），
     条目数与可达状态的对齐规则不变（含深度淘汰 `dropped_names` 机制；
     淘汰弹出参数化条目时其所在参数段整段随行，保证重放参数完整）。
   - 参数化条目的 undo/redo 完成事件仍是上文同一 completed result 形状
     （`version/width/height/path/sha256`，画布刷新文件照常写入）。
   - 重放为确定性重算：重放中途取消（§7）或失败（如可选依赖在会话中
     消失导致 `ENGINE_ERROR`）时文档状态不动（先算后提交），不产生半途
     历史栈。
2. **滑杆命令合并（coalescing）**：全分辨率 `image.adjust` 应用时，若上一
   条历史条目同为 `image.adjust` 且其上无其它动作、redo 栈为空，则**并作
   单条**：不新增条目，本次 adjustments 追加进该条目的重放序列，undo 一次
   越过两次应用回到首个 adjust 之前的像素，redo 按快照像素精确复原合并后
   状态。合并判定以 redo 栈为准（实现口径 `not redo_stack`）：redo 栈非空
   ——栈顶条目之后发生过尚未被 redo 抵消的 undo——时不合并；undo 后又
   redo 的序列 redo 栈已空，恢复合并（redo 恢复的正是条目快照的前态，
   applies 重放与实况一致）。对协议的可见影响：连续 adjust 的
   `image.history` 条目数少于应用次数（名字仍为 `image.adjust`）；
   `version` 语义不变（每次全分辨率应用照常 +1，§3.1——version 不是内容
   指纹）。有其它动作（transform/filter.apply）插入时同样不合并，条目数与
   应用次数一致。HistoryModel（C++）为纯消费者，无需感知合并。

并发口径（现状如实记录）：Worker 不做 per-document 串行化（`DocumentStore`
的锁只护文档 id 表，任务线程池内同一文档的两个任务可交叠）；同一
`document_id` 的变更类任务由客户端保证不并发提交——C++/QML 侧的在途门控
已保证 UI 流程满足这一点，协议层不另行强制。

### 3.4 滤镜链预设（filter.presets.*，Phase 5 增补）

四个 sync 动作，为 `processors/filter_presets.py` 既有持久化的协议化薄封装；
存储语义（路径、文件格式、原子写）由该模块定义，本节只锁定协议形状与
错误码。对应流程：user-flows.md 流程 2 的"预设"节点。

- 持久化沿用既有资产：文件为 `~/.toolbox/filter_presets/*.filterchain.json`
  （可被 Settings `presets/filter_chain_dir` 覆盖），写入为临时文件 +
  原子 rename，`schema_version` 由存储层维护——协议层不暴露文件路径与
  schema 细节。
- `filter.presets.list`（sync）`{}` → `{presets: [{name, step_count}]}`，
  按存储文件名（净化后的 name）排序——存储层行为；`step_count` 为链内
  步骤数（含 disabled）。只暴露这两个字段，文件路径/时间戳等存储细节
  不进协议。
- `filter.presets.save`（sync）`{name, steps}` → `{saved: true, name}`：
  - `name` 必须为非空字符串；`steps` 逐项经 `FilterStep.from_dict` 校验
    （非对象、缺 `filter_key`、形状非法 → `INVALID_PARAMS`，提交前同步
    返回，错误消息带出错下标，与 `filter.preview` 的链校验一致）。
  - 有意**不做** FilterDef 参数校验：预设是持久化用户状态，允许保存引用
    当前环境不可用滤镜（如缺 G'MIC 依赖）的链；参数合法性沿用 apply 路径
    的 `FilterChain.validate_all` 检查。
  - 同名预设直接覆盖（存储层 `overwrite=True` 语义），不返回
    FileExists 类错误。
- `filter.presets.load`（sync）`{name}` → `{name, steps: [{filter_key,
  params, enabled}]}`。预设不存在 → `FILE_NOT_FOUND`（提交前同步返回）；
  文件损坏或 `schema_version` 高于当前支持 → `ENGINE_ERROR`（内容问题，
  非请求参数问题）。`steps` 形状与 `filter.preview` / `filter.apply` 的
  `filters` 参数一致，可直接回填链编辑器。
- `filter.presets.delete`（sync）`{name}` → `{deleted: true}`；预设不存在
  → `FILE_NOT_FOUND`——列表与存储之间的陈旧状态如实上报，不谎报删除
  成功。
- 预设与文档无关：四个动作均不接受/返回 `document_id`，不触碰 §3.1 的
  `version`，不产生任务（无 task_id、无 task.* 事件）。

### 3.5 批处理（batch.start / batch.cancel，Phase 6 增补）

`batch.start`（async）把一组路径经可选滤镜链批量写到目标目录。参数：

- `paths`：非空数组，元素为非空字符串路径，可混含文件与目录；目录**递归
  扫描**。只有 `processors/utils.py` `SUPPORTED_READ` 扩展名的文件纳入
  批处理（其余文件忽略）；路径不存在 → 同步 `FILE_NOT_FOUND`；全部输入
  展开后没有可处理文件 → 同步 `FILE_NOT_FOUND`。同一文件只计一次（目录与
  其内文件并列、重复条目去重，按绝对路径）；展开结果按路径排序，`pattern`
  的 `{i}` 序号依此序。以上判定均在提交任务前同步完成（错误响应不产生
  task_id，与 `filter.preview` 的链校验先例一致）。
- `output_dir`：必需，输出目录（不存在则创建）。
- `format`：必需，输出格式（如 `PNG` / `JPEG` / `WEBP`），大小写不敏感；
  `JPEG` 规范化为 `.jpg` 扩展名（1.0 批量链处理既有规则）；不在
  `SUPPORTED_WRITE` → 同步 `INVALID_PARAMS`。
- `quality`：可选整数 1-100，透传 `processors/utils.py` `save_image`；
  缺省用 `save_image` 自身缺省（JPEG/WebP 92；PNG 等无损格式不适用）。
  非整数或越界 → 同步 `INVALID_PARAMS`。
- `naming`：`keep`（缺省）/ `suffix` / `pattern`。
  - `keep`：`{源文件名}.{输出扩展名}`（1.0 批量处理既有命名）。
  - `suffix`：`{源文件名}_batch.{输出扩展名}`（输出目录与源目录相同时也
    不覆盖源图）。
  - `pattern`：`pattern` 必须为非空字符串，占位符与 `processors/batch.py`
    `batch_rename` 同款——`{name}`=源文件名（不含扩展名）、`{ext}`=输出
    扩展名（含点）、`{i}`/`{index}`=自 1 起按扫描序 3 位补零的序号；
    格式化结果若不以输出扩展名结尾则自动补齐（保证按 `format` 落盘）。
    `naming=pattern` 缺 `pattern`、占位符拼写非法 → 同步 `INVALID_PARAMS`。
- `steps`：可选，形状与 `filter.preview` / `filter.apply` 的 `filters` 参数
  一致（`[{filter_key, params, enabled}]`），校验方式相同（未知 key / 参数
  非法 → 同步 `INVALID_PARAMS`）。缺省或空数组 = 纯格式转换（逐文件
  load → save，不跑滤镜）。

同步响应 `{task_id, status, total}`（`status` 为 §2.3 受理回执既有字段；
`total` 为扫描所得文件数，与完成事件 `result.total` 同源）。执行复用
`processors/batch_filter_chain.py` `run_batch_filter_chain`：逐文件 load →
滤镜链 → save；单个文件失败（解码/处理/写盘）记为该项 failed，**不中断**
批处理（1.0 批量面板同款汇总行为）。输出同名默认覆盖（与 1.0 面板缺省
一致；本动作不暴露 overwrite 参数）。任务完成时 `task.completed` 的
`result` 为 `{total, done, succeeded, failed, current, state: "done",
output_dir, items}`，`done = succeeded + failed`（到达终态的条数）；
`items` 为**逐文件全量对账**（见下），补齐被进度节流丢弃的终态帧。

批处理进度字段（对齐 §2.3 既有任务进度协议，仅 batch 任务携带；消费方
忽略未知字段）。`task.progress` 为**逐文件帧**，条目到达自身终态时发出：

| 字段 | 出现位置 | 含义 |
|---|---|---|
| `task_id` | 所有事件顶层（§2.3 既有） | 任务 ID |
| `file` | `task.progress` 附加字段 | 行键：该帧所指源文件的绝对路径 |
| `state` | 同上 | **该条目**的状态，取值 `running/done/failed/cancelled`；本实现只在条目终态发帧，实际值为 `done` / `failed` |
| `progress` | 同上 | 该条目进度百分比（终态帧为 100） |
| `output_path` | 同上，可省 | `done` 条目的输出文件绝对路径；`failed` 条目省略 |
| `done` | 同上；`task.completed.result` | 整批聚合：已到达终态的条数 |
| `total` | 同上 | 扫描所得总数（= start 响应的 `total`） |
| `current` | 同上 | 聚合视角最近一次状态变更涉及的源文件绝对路径（逐文件帧上等于 `file`；completed 时为空串） |
| `error` | `task.failed.error`（§2.3 既有形状）；逐文件对账条目内 | 整批失败/取消由 `task.failed.error` 承载（`code = "CANCELLED"` 表示取消，§7）；单文件失败在 `items` 条目的 `error` 上 |

- 批处理整体状态由事件生命周期表达（§2.3）：completed ⇒ 整批 done；
  failed / cancelled 不引入新事件类型，仍映射为 `task.failed`，批处理
  字段不在 failed 事件上重复出现。
- 进度事件照旧 ≥100ms 节流（§7），逐文件帧可能被丢弃——行状态的最终
  真相源是 `task.completed.result.items`（UI 侧不得把进度帧当第二真相源）。
- `items` 条目形状：`{file, state, error?, output_path?}`，`state` 映射
  `done | failed`（完成批次；`cancelled` / `pending` 仅在理论上可能出现，
  如实映射不虚构）；`error` / `output_path` 空时省略。
- 取消收尾呈现（把未完成行收尾为 `skipped`）由 C++ 侧负责
  （`native/models/batch_model.cpp` `markActiveAs`），Worker 不发
  `skipped` 词汇。

`batch.cancel`（sync）`{task_id}` → `{cancelled: true}`：取消信号已送达，
任务在下一协作检查点停止（逐文件边界 + 滤镜链步骤内检查点，复用
`processors/cancellation.py` `CancelToken`）；任务已终结 →
`{cancelled: false}`（不谎报已取消）；未知 `task_id` → `UNKNOWN_TASK`
（同 `task.cancel`）。取消后任务以 `task.failed`
（`error.code = "CANCELLED"`）收尾；被取消条目不写输出。

`batch.start` 为标准异步任务：适用 §7 全部取消语义与 §2.3 生命周期；不经
DocumentStore、无 `document_id`，不触碰 §3.1 的文档 `version`。

### 3.6 G'MIC 可用性探测（gmic.check，Phase 6 增补）

`gmic.check`（sync）`{}` → `{available, version, source}`：

- 优先探测 `gmic` CLI（`processors/gmic.py` `available()` / `version()`，
  即 `shutil.which("gmic")` + `gmic -version`）→ `{available: true,
  version: "<x.y.z>", source: "cli"}`；版本号无法解析时如实记 `"unknown"`。
- CLI 不存在时尝试 `import gmic`（python-gmic 绑定）→ `{available: true,
  version: "<模块 __version__，缺失记 unknown>", source: "python"}`。
- 都不可用 → `{available: false, version: "", source: null}`，**不抛错**——
  可用性探测是诊断动作，依赖缺失不是协议错误（与滤镜卡片按
  `optional_deps` 置灰的原则一致，Phase 6A 交付口径）。
- 本动作不产生任务、不触碰文档与任务状态；`source` 仅在 `available=true`
  时为 `"cli" | "python"`。

### 3.7 生成器目录与渲染（generate.list / generate.render，Phase 6C 增补）

`generate.list`（sync）`{}` → `{generators: [{key, name, category,
category_label, description, available, optional_deps, params}]}`：

- 形状与 `filter.list` 同构（目录类 sync 动作的既有词汇）；条目来自
  processors 既有生成器资产的元信息，Worker 不自造参数表。
- `category` 取值 `fractal | texture | gradient | shader`；`category_label`
  为本地化显示名（缺省回落 `category` 原值，filter.list 同款）。
- `params` 为参数定义数组，元素形状与 filter.list 的参数描述一致
  （`{name, label, type, default, minimum, maximum, step, choices,
  description}`），`type` 词汇同为 `int/float/bool/enum/color`；UI 据此
  自动生成控件，不硬编码任何生成器的参数表。
- `available=false` 表示可选依赖未满足，消费方须置灰且不得发起渲染；
  `optional_deps` 为置灰原因（缺失依赖名列表，如 `["gmic"]`）。
- 覆盖范围（如实枚举，键即 `generate.render` 的 `generator_key`）：
  - `fractal:<formula>`（`processors/fractal.py` `_2D_FORMULAS` 全部 15 个
    2D 公式）与 `fractal:mandelbulb`（3D 光线步进）；均可用。
  - `texture:perlin|simplex|value|worley|cellular`（noise）、
    `texture:pattern:stripes|rings|checker|dots|grid`（pattern）、
    `texture:raymarch:orb`（CPU SDF）：均可用；缺省参数取自
    `processors/texture_studio/presets.py` 内置预设。
  - `texture:gmic:paper|canvas|grunge|noise_blend`：仅当 G'MIC CLI 可用
    （`processors/gmic.py available()`，即 `shutil.which("gmic")`）时
    `available=true`；缺失时 `available=false` + `optional_deps=["gmic"]`
    （ui-page-spec.md："G'MIC 缺失时该生成器置灰"）。1.0 内部的 numpy
    降级实现不改变协议面的可用性判定。
  - `gradient:linear|radial|mesh`：均可用。
  - `shader:preview`：恒为 `available=false`（优雅降级）——Worker 进程没有
    OpenGL 运行时（1.0 的着色器渲染发生在 Qt/GL 侧），`optional_deps` 含
    `opengl`；`processors/shader_studio/validator.py` 的外部校验依赖
    `glslangValidator` 缺失时一并列入。

`generate.render`（async）`{generator_key, params?, width, height}` → 受理
`{task_id, status}`，完成事件 result `{path, width, height, sha256,
generator_key}`：

- `generator_key` 必须来自 `generate.list`；`generator` 作为同值别名兼容
  接受（两者都不给 → `INVALID_PARAMS`）。
- `width` / `height`：整数 1..4096（上限与 `FractalParams.validate` 一致），
  非法 → 同步 `INVALID_PARAMS`。
- `params`：参数值对象，可省（缺省按条目默认值渲染）。键值逐项经条目
  `params` 定义校验（`FilterParam.validate`），分形另经
  `FractalParams.validate`；未知生成器、不可用生成器（`optional_deps` 未
  满足）或取值非法 → **提交任务前同步 `INVALID_PARAMS`**，不产生 task_id
  （先例同 `image.transform` 的提交前 op 校验）。`color` 类型条目的取值
  形状见本节 Phase 6C 复查注（`[r,g,b]` 数组或 hex 文本双向接受，渲染侧
  归一为数组）。
- 渲染复用既有实现：`processors/fractal.py` `render_fractal` /
  `render_mandelbulb`、`processors/texture_studio/generators.py` `generate`、
  `processors/gradients.py` 三个渐变函数。完成 result 经 §4 临时 PNG 通道
  交付（复用 `filter_adapter.write_preview` 机制，`max_side` 取请求尺寸 →
  不降采样，按请求的 width/height 原尺寸落盘）；同一生成器重复渲染按
  生成器 key 覆盖命名（`preview-generate-<key>.png`，§4 防堆积规则）。
- 进度与取消照 §2.3/§7（≥100ms 节流）：分形渲染直通 `render_fractal` /
  `render_mandelbulb` 的协作检查点（逐行）；texture / gradient 渲染为同步
  CPU 计算，取消在任务体边界检查。取消以 `task.failed`（`CANCELLED`）收尾。
- 本动作不经 DocumentStore、无 `document_id`，不触碰 §3.1 的文档
  `version`。

## 4. 大图数据传递（总纲 §6.3）

- JSON 只传路径、ID、尺寸与校验；**禁止 Base64 大图**。
- 预览/恢复刷新类动作（`filter.preview`、`image.adjust`、`image.transform`、
  `image.undo`、`image.redo`、`image.reset`）与生成器渲染（`generate.render`，
  §3.7）的结果写入 `--temp-dir` 下
  PNG（无损小文件，便于纹理上传），消息携带 `path/width/height/sha256`。
- C++ 侧读取临时文件构造 QSG 纹理；读取后即可删除，由 Worker 会话结束统一清理。
- 临时文件规则：所有者 = Worker 会话；生命周期 = 会话；每会话预览文件按
  `document_id` 覆盖命名，防堆积。
- 内存映射/共享内存：仅当实测证明必要才引入（Phase 5 用性能数据决策）。

## 5. 错误码（稳定集合）

| 码 | 含义 |
|---|---|
| `PARSE_ERROR` | 消息不是合法 JSON 或缺少必需字段 |
| `PROTOCOL_MISMATCH` | `protocol` 版本不受支持 |
| `UNKNOWN_ACTION` | 动作未注册 |
| `INVALID_PARAMS` | 参数缺失/类型/取值不合法 |
| `UNKNOWN_DOCUMENT` | document_id 不存在或已关闭 |
| `UNKNOWN_TASK` | task_id 不存在 |
| `FILE_NOT_FOUND` | 打开的文件不存在 |
| `UNSUPPORTED_FORMAT` | 图像格式无法解码 |
| `UNREDOABLE` | 历史/重做栈无可恢复条目（`image.undo` / `image.redo`，提交前同步返回，见 §3.3） |
| `CANCELLED` | 任务被取消（task.failed 事件携带） |
| `ENGINE_ERROR` | 处理器执行异常（details 里带 step/filter 信息） |
| `INTERNAL` | 未分类的内部错误 |

## 6. 握手与崩溃恢复（总纲 §6.5）

1. Worker 启动后**第一条消息必须是** `worker.hello` 的响应（或能力事件）。
   C++ 端握手超时 5s：超时视为启动失败。
2. C++ 检测异常退出（exitCode ≠ 0 或 QProcess::CrashExit）→ 状态置 `crashed`。
3. 自动重启上限 **3 次**（1s 退避），重启后重新握手；超过上限停止并报告用户。
4. 重启后 Worker 状态清空：所有 document_id 失效。C++ 收到 `crashed` 后必须
   失效全部文档状态并提示用户从源文件重新打开（不得谎称可恢复未持久化像素）。

## 7. 取消语义

- `task.cancel` 尽快置任务为 `cancelling`；处理器在协作检查点抛出
  `CancelledError`（复用 `processors/cancellation.py`）。
- 取消后产生 `task.failed` 事件，`error.code = "CANCELLED"`。
- 已完成任务不可取消；未知 task_id 返回 `UNKNOWN_TASK`。
- 进度事件节流：同一任务 ≥ 100ms 才发一条（Worker 端保证）。
- 本轮新增的 `image.adjust` / `image.transform` / `image.undo` / `image.redo` /
  `image.reset` 异步动作均为标准任务，同样适用本节全部语义
  （`task.cancel` / 协作检查点 / `CANCELLED`）；本节既有语义不变。

## 8. 版本策略

- `protocol` 整数递增；不兼容变更（字段删除/语义变更）必须升版本。
- C++ 端收到更高版本请求响应时：握手失败并给出可读提示，不得猜测语义。
- 兼容性测试：`tests/test_worker_protocol.py`（Python）与
  `tests/native/test_ipc_protocol.cpp`（C++）共同锁定消息形状。
