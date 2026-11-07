"""Toolbox 2.0 Python Worker.

独立进程承载现有 processors/backends 引擎，通过 JSON Lines 控制消息与
C++ 桌面应用通信。协议规范见 docs/ipc-protocol.md。

- stdout 只写协议消息；日志与调试输出写 stderr。
- 不依赖当前工作目录定位 processors（main.py 负责定位仓库根）。
"""

__all__ = ['protocol', 'task_runtime', 'dispatcher', 'adapters']
