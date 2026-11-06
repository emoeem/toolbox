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

动作集合按阶段扩展（总纲 §6.2）；禁止各页面私自定义协议动作。

本轮增补为**纯新增动作 + `filter.apply` 结果新增 `version` 字段**：不删除字段、
不改既有字段语义，`protocol` 保持 `1`（符合 §8 兼容性规则）。

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

## 4. 大图数据传递（总纲 §6.3）

- JSON 只传路径、ID、尺寸与校验；**禁止 Base64 大图**。
- 预览/恢复刷新类动作（`filter.preview`、`image.adjust`、`image.transform`、
  `image.undo`、`image.redo`、`image.reset`）的结果写入 `--temp-dir` 下
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
