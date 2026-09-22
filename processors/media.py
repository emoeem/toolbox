from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import os


def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "外部工具执行失败")


def convert_animation(inputs: list[str], output: str, fmt: str, fps: float = 12.0) -> str:
    if not inputs:
        raise ValueError("至少需要一个输入文件")
    out = str(Path(output).expanduser())
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    src = [str(Path(p).expanduser()) for p in inputs]
    if fmt.lower() == "gif":
        _run(["magick", "-delay", str(max(1, round(100 / fps))), "-loop", "0", *src, out])
    elif fmt.lower() in {"webp", "webp_anim"}:
        _run(["magick", "-delay", str(max(1, round(100 / fps))), "-loop", "0", *src, out])
    elif fmt.lower() == "apng":
        _run(["magick", "-delay", str(max(1, round(100 / fps))), "-loop", "0", *src, out])
    elif fmt.lower() == "jxl":
        _run(["ffmpeg", "-y", "-framerate", str(fps), "-i", src[0] if len(src) == 1 else "concat:" + "|".join(src), out])
    else:
        raise ValueError(f"不支持的动画格式: {fmt}")
    return out


def extract_frames(input_path: str, output_dir: str, fmt: str = "png") -> list[str]:
    out_dir = Path(output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(input_path).stem
    pattern = str(out_dir / f"{stem}_%04d.{fmt.lower()}")
    _run(["magick", str(Path(input_path).expanduser()), pattern])
    return sorted(str(p) for p in out_dir.glob(f"{stem}_*.{fmt.lower()}"))


def merge_animations(inputs: list[str], output: str) -> str:
    if len(inputs) < 2:
        raise ValueError("至少需要两个动画文件")
    tmp = Path(tempfile.mkdtemp(prefix="toolbox_anim_"))
    try:
        frames: list[str] = []
        for i, src in enumerate(inputs):
            frames.extend(extract_frames(src, str(tmp / str(i))))
        return convert_animation(frames, output, Path(output).suffix.lstrip("."))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
