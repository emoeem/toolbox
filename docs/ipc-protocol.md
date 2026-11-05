# IPC 协议规范（Phase 3 交付物）

> 状态：`code_complete`（协议与两端实现同步交付；跨进程验收在 Linux 目标环境）
> 实现位置：`python_worker/`（Python 侧）与 `native/backend/`（C++ 侧）。
> 修改本文件必须同步更新两端实现、测试与版本兼容逻辑（总纲 §16.3）。

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

### 2.4 其他事件

```json
{ "protocol": 1, "type": "log", "level": "warning", "message": "…" }
```

## 3. 动作（Phase 3 范围）

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
| `filter.apply` | async | `{document_id, filters: [...]}` | `{width, height}`（文档像素被更新，`modified=true`） |
| `task.cancel` | sync | `{task_id}` | `{cancelling: true}` |
| `task.query` | sync | `{task_id}` | `{task_id, status, progress}` |

动作集合按阶段扩展（总纲 §6.2）；禁止各页面私自定义协议动作。

## 4. 大图数据传递（总纲 §6.3）

- JSON 只传路径、ID、尺寸与校验；**禁止 Base64 大图**。
- `filter.preview` 结果写入 `--temp-dir` 下 PNG（无损小文件，便于纹理上传），
  消息携带 `path/width/height/sha256`。
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

## 8. 版本策略

- `protocol` 整数递增；不兼容变更（字段删除/语义变更）必须升版本。
- C++ 端收到更高版本请求响应时：握手失败并给出可读提示，不得猜测语义。
- 兼容性测试：`tests/test_worker_protocol.py`（Python）与
  `tests/native/test_ipc_protocol.cpp`（C++）共同锁定消息形状。
