"""Toolbox Python Worker 入口。

运行方式（C++ BackendManager 使用第一种，两种都必须可用，总纲 §15.4 不依赖 cwd）：

    python <repo>/python_worker/main.py --repo-root <repo>
    python -m python_worker.main        # 需 repo 在 sys.path

规则（docs/ipc-protocol.md §1）：
- stdout 只写协议消息（protocol.encode 的结果），任何日志走 stderr。
- 单条消息处理异常不得让 Worker 退出；致命错误也以错误响应回执。
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import python_worker.protocol as protocol  # noqa: E402
from python_worker.dispatcher import Dispatcher, WorkerContext  # noqa: E402
from python_worker.task_runtime import TaskRuntime  # noqa: E402


def _log_stderr(level: str, message: str) -> None:
    print(f'[worker:{level}] {message}', file=sys.stderr, flush=True)


def _emit(msg: dict) -> None:
    """唯一的 stdout 出口：事件（progress/completed/failed）经此写出。"""
    sys.stdout.write(protocol.encode(msg))
    sys.stdout.flush()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Toolbox Python Worker')
    parser.add_argument('--repo-root', default=str(REPO_ROOT),
                        help='processors/backends 所在根目录')
    parser.add_argument('--max-workers', type=int, default=2, help='任务线程池大小')
    parser.add_argument('--temp-dir', default=None, help='预览/结果临时文件目录')
    parser.add_argument('--idle-timeout', type=int, default=0,
                        help='空闲自动退出秒数；0 = 禁用（Phase 8 打包后启用）')
    return parser.parse_args(argv)


def _start_idle_watcher(runtime: TaskRuntime, timeout: int):
    """空闲看门狗：stdin 阻塞在主线程，超时退出只能由守护线程执行。

    返回 touch()：主循环每收到一条请求调用一次以刷新活跃时间。
    退出条件 = 超过 timeout 无请求 且 无活跃任务（协议 §6.4：不打断在途工作）。
    """
    last_activity = [time.monotonic()]

    def touch() -> None:
        last_activity[0] = time.monotonic()

    def watch() -> None:
        while True:
            time.sleep(1.0)
            if time.monotonic() - last_activity[0] >= timeout and not runtime.has_active():
                _log_stderr('info', f'idle timeout ({timeout}s) reached, exiting')
                runtime.shutdown()
                os._exit(0)

    threading.Thread(target=watch, name='toolbox-idle', daemon=True).start()
    return touch


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    temp_dir = Path(args.temp_dir) if args.temp_dir else (
        Path(tempfile.gettempdir()) / f'toolbox-worker-{_pid()}'
    )

    ctx = WorkerContext(temp_dir=temp_dir, repo_root=repo_root,
                        runtime=TaskRuntime(max_workers=args.max_workers, emitter=_emit))
    dispatcher = Dispatcher(ctx)

    touch = _start_idle_watcher(ctx.runtime, args.idle_timeout) if args.idle_timeout > 0 else None

    _log_stderr('info', f'worker started: pid={_pid()} repo={repo_root} temp={temp_dir}')

    # 优雅退出：Ctrl+C / 系统终止 → 取消全部任务后正常收尾。
    def _handle_signal(signum, _frame):
        _log_stderr('info', f'signal {signum} received, shutting down')
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            if touch is not None:
                touch()
            try:
                request = protocol.decode(line)
            except protocol.ProtocolError as exc:
                # 无法定位 request_id 的坏消息：以 request_id='' 回错误帧。
                response = protocol.make_error('', exc.code, exc.message)
                sys.stdout.write(protocol.encode(response))
                sys.stdout.flush()
                continue

            try:
                response = dispatcher.handle(request)
            except Exception as exc:  # 双保险：分发器自身异常也不得终止 Worker
                _log_stderr('error', f'dispatcher crashed: {exc!r}')
                response = protocol.make_error(
                    request.get('request_id', ''), protocol.ERR_INTERNAL, str(exc),
                )
            sys.stdout.write(protocol.encode(response))
            sys.stdout.flush()

            if dispatcher.shutting_down:
                _log_stderr('info', 'shutdown requested, exiting main loop')
                break
    except KeyboardInterrupt:
        pass
    finally:
        ctx.runtime.shutdown()
        ctx.store.close_all()
        _log_stderr('info', 'worker exited')

    return 0


def _pid() -> int:
    import os
    return os.getpid()


if __name__ == '__main__':
    try:
        raise SystemExit(run())
    except KeyboardInterrupt:
        raise SystemExit(0)
