from __future__ import annotations

import json
import time
from pathlib import Path

from .filter_chain import FilterChain, FilterStep

PRESET_SCHEMA_VERSION = 1


def _preset_store_path() -> Path:
    from app.settings_store import DesktopSettings
    settings = DesktopSettings()
    stored = settings.value("presets/filter_chain_dir", None)
    if stored:
        p = Path(str(stored))
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass
    candidates = [
        Path.home() / ".toolbox" / "filter_presets",
        Path.home() / ".config" / "toolbox" / "filter_presets",
        Path("/tmp/toolbox_filter_presets"),
    ]
    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            settings.setValue("presets/filter_chain_dir", str(p))
            return p
        except Exception:
            continue
    import tempfile
    t = Path(tempfile.gettempdir()) / "toolbox_filter_presets"
    t.mkdir(parents=True, exist_ok=True)
    return t


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
    for f in sorted(store.glob("*.filterchain.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "name": data.get("name", f.stem.replace(".filterchain", "")),
                "file": str(f),
                "schema_version": data.get("schema_version", 0),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "step_count": len(data.get("chain", {}).get("steps", [])),
            })
        except Exception:
            continue
    return results


def save_preset(name: str, chain: FilterChain, overwrite: bool = True) -> str:
    if not name.strip():
        raise ValueError("Preset 名称不能为空")
    path = _preset_file_path(name)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Preset 已存在: {path}")
    now = int(time.time())
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    payload = {
        "schema_version": PRESET_SCHEMA_VERSION,
        "name": name,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
        "chain": chain.to_dict(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


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
