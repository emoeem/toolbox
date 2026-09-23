from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def available() -> bool:
    return shutil.which("gmic") is not None


def version() -> str:
    if not available():
        return ""
    p = subprocess.run(["gmic", "-version"], capture_output=True, text=True)
    m = re.search(r"Version\s+([0-9.]+)", p.stdout)
    return m.group(1) if m else "unknown"


def apply(input_path: str, output_path: str, command: str) -> str:
    if not available():
        raise RuntimeError("未找到 G'MIC，请安装 gmic")
    if not command.strip():
        raise ValueError("请输入 G'MIC 命令")
    # 用户输入只作为 G'MIC 脚本参数，不通过 shell 执行。
    p = subprocess.run(
        ["gmic", input_path, *command.split(), "-output", output_path],
        capture_output=True, text=True,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip() or "G'MIC 执行失败")
    return output_path


def command_help(command: str) -> str:
    p = subprocess.run(["gmic", "-h", command], capture_output=True, text=True)
    return p.stdout or p.stderr
