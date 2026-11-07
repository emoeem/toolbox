# Phase 3 验收清单（Linux 目标环境执行）

> 状态口径：Phase 3 = `code_complete`。协议单测（Python/C++）已在 CI 执行，
> 但"跨进程垂直切片"必须在本清单通过后才算 `runtime_verified`（总纲 §14.2）。

## 准备

```bash
cd ~/toolbox
uv sync --extra dev      # Worker 依赖沿用现有锁定环境
cmake --build --preset linux-debug
```

## 1. Worker 独立冒烟（不启动 GUI）

```bash
cd ~/toolbox
printf '%s\n%s\n' \
  '{"protocol":1,"request_id":"r1","action":"worker.hello","params":{}}' \
  '{"protocol":1,"request_id":"r2","action":"filter.list","params":{}}' \
  | uv run python python_worker/main.py --repo-root . 2>worker.log | head -2
```

- [ ] 两行合法 JSON 响应；`worker.hello` 返回 `protocol:1` 与 engine 信息
- [ ] `filter.list` 返回非空滤镜数组（含 params 定义）
- [ ] stderr 有启动日志；stdout 只有协议消息
- [ ] stdin 关闭（EOF）后 Worker 干净退出（exit code 0）

## 2. 协议单测（CI 已跑，本机复核）

```bash
uv run python -m unittest tests.test_worker_protocol -v
QT_QPA_PLATFORM=offscreen ctest --preset linux-ci
```

- [ ] 全部通过

## 3. 跨进程垂直切片（总纲 §13 Phase 3 验收核心）

通过 Phase 2 编辑器 + BackendManager（若 QML 接线尚未暴露按钮，用测试驱动
`BackendManager::sendAction`；验收方式记录实际采用哪一种：＿＿＿＿）：

- [ ] C++ 启动 Worker → 握手成功 → 状态 `ready`（能力含 filter_count > 0）
- [ ] `image.open` 打开真实图像 → 返回 document_id 与尺寸
- [ ] `filter.preview`（brightness 0.1）→ 任务事件 queued→progress→completed
      → C++ 读取预览临时文件 → 画布显示处理结果
- [ ] `filter.apply`（invert）→ 文档 modified=true；尺寸不变
- [ ] `image.save` → 目标文件产生且可被旧程序打开
- [ ] 处理期间拖动界面无卡顿（任务不在 UI 主线程）
- [ ] 大图（≥ 40MP）处理时 UI 保持响应，进度事件节流可见（≥100ms 间隔）
- [ ] 任务取消：preview 进行中 `task.cancel` → 收到 `task.failed` 且
      `code=CANCELLED`
- [ ] Worker 崩溃恢复：`kill -9 <worker_pid>` → UI 收到 `WORKER_CRASHED`，
      状态 `crashed` → 自动重启并重新握手（≤3 次）→ 旧 document_id 失效被
      明确提示
- [ ] 握手超时路径：用不存在的 python 路径启动 → `WORKER_START_FAILED`
      可读错误
- [ ] 未知动作：发送 `foo.bar` → `UNKNOWN_ACTION` 错误响应
- [ ] 协议不一致：临时把 C++ 期望版本改为 2 → 握手失败并给出可读提示
      （验证后还原）

## 4. 无 Base64 大图检查

- [ ] 抓取一次完整 preview 会话的 stdout 日志，确认所有消息长度 < 10KB，
      图像数据只以临时文件路径传递（协议 §4）

## 5. 记录

- Worker 进程退出码、崩溃恢复次数、大图处理耗时 → 回填本文件。
- 任何协议字段偏差 → 修 `python_worker/protocol.py`、`native/backend/ipc_protocol.h`
  与 `docs/ipc-protocol.md` 三处并同步测试。
