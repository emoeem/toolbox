from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from .filter_chain import FilterChain, FilterStep
from .utils import ensure_writable_dir

PRESET_SCHEMA_VERSION = 1


def _preset_store_path() -> Path:
    from app.settings_store import DesktopSettings
    settings = DesktopSettings()
    stored = settings.value("presets/filter_chain_dir", None)
    if stored:
        p = Path(str(stored))
        if ensure_writable_dir(p) == p:
            return p
    for candidate in (
        Path.home() / ".toolbox" / "filter_presets",
        Path.home() / ".config" / "toolbox" / "filter_presets",
    ):
        resolved = ensure_writable_dir(candidate, fallback=Path(tempfile.gettempdir()) / "toolbox_filter_presets")
        if resolved == candidate:
            try:
                settings.setValue("presets/filter_chain_dir", str(resolved))
            except Exception:
                pass
            return resolved
    return ensure_writable_dir(Path(tempfile.gettempdir()) / "toolbox_filter_presets")


def _preset_filename(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in ("_", "-", " ") else "_" for c in name).strip()
    if not safe:
        safe = "preset"
    return f"{safe}.filterchain.json"


def _preset_file_path(name: str) -> Path:
    return _preset_store_path() / _preset_filename(name)


def list_presets() -> list[dict]:
    store = _preset_store_path()
    results: list[dict] = []
def list_presets(include_errors: bool = False) -> list[dict]:
    store = _preset_store_path()
    results: list[dict] = []
    for f in sorted(store.glob("*.filterchain.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            if include_errors:
                # Surface unreadable presets instead of silently hiding them.
                results.append({
                    "name": f.stem.replace(".filterchain", ""),
                    "file": str(f),
                    "schema_version": 0,
                    "created_at": "",
                    "updated_at": "",
                    "step_count": 0,
                    "error": str(exc),
                })
            continue
        results.append({
            "name": data.get("name", f.stem.replace(".filterchain", "")),
            "file": str(f),
            "schema_version": data.get("schema_version", 0),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "step_count": len(data.get("chain", {}).get("steps", [])),
        })
    return results


def save_preset(name: str, chain: FilterChain, overwrite: bool = True) -> str:
    if not name.strip():
        raise ValueError("Preset 名称不能为空")
    path = _preset_file_path(name)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Preset 已存在: {path}")
    now = int(time.time())
    created_at = now
    if path.exists():
        try:
            created_at = json.loads(path.read_text(encoding="utf-8")).get("created_at", now)
        except Exception:
            created_at = now
    payload = {
        "schema_version": PRESET_SCHEMA_VERSION,
        "name": name,
        "created_at": created_at,
        "updated_at": now,
        "chain": chain.to_dict(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(path, payload)
    return str(path)


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Write via a temp file + rename so a crash cannot leave a truncated preset."""
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_preset(name: str) -> FilterChain:
    path = _preset_file_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Preset 不存在: {name}")
    return load_preset_from_path(path)


def load_preset_from_path(path: Path | str) -> FilterChain:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    version = data.get("schema_version", 0)
    if version > PRESET_SCHEMA_VERSION:
        raise ValueError(f"不支持的 preset schema_version {version}")
    chain_data = data.get("chain", {})
    return FilterChain.from_dict(chain_data)


def delete_preset(name: str) -> bool:
    path = _preset_file_path(name)
    if path.exists():
        path.unlink()
        return True
    return False


def preset_exists(name: str) -> bool:
    return _preset_file_path(name).exists()
