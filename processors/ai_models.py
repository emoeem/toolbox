from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.request import urlopen, Request

CACHE_ROOT = Path(os.environ.get("TOOLBOX_AI_CACHE", Path.home() / ".cache" / "image-toolbox" / "models"))
INDEX_FILE = CACHE_ROOT / "registry.json"

MODEL_REGISTRY = [
    {"id":"u2net","name":"U²-Net","task":"抠图","backend":"ONNX Runtime","runtime":"rembg","version":"2.0","source":"rembg","kind":"rembg"},
    {"id":"u2netp","name":"U²-Netp","task":"抠图","backend":"ONNX Runtime","runtime":"rembg","version":"2.0","source":"rembg","kind":"rembg"},
    {"id":"isnet-general-use","name":"IS-Net General","task":"抠图","backend":"ONNX Runtime","runtime":"rembg","version":"1.0","source":"rembg","kind":"rembg"},
    {"id":"silueta","name":"Silueta","task":"抠图","backend":"ONNX Runtime","runtime":"rembg","version":"1.0","source":"rembg","kind":"rembg"},
    {"id":"realesrgan-x4plus","name":"Real-ESRGAN x4+","task":"超分","backend":"Vulkan","runtime":"Upscayl","version":"1.0","source":"system","kind":"upscayl","system_model":"realesrgan-x4plus"},
    {"id":"realesrgan-x4plus-anime","name":"Real-ESRGAN x4+ Anime","task":"超分","backend":"Vulkan","runtime":"Upscayl","version":"1.0","source":"system","kind":"upscayl","system_model":"realesrgan-x4plus-anime"},
    {"id":"realesr-animevideov3-x2","name":"AnimeVideoV3 x2","task":"超分","backend":"Vulkan","runtime":"Upscayl","version":"1.0","source":"system","kind":"upscayl","system_model":"realesr-animevideov3-x2"},
    {"id":"realesr-animevideov3-x3","name":"AnimeVideoV3 x3","task":"超分","backend":"Vulkan","runtime":"Upscayl","version":"1.0","source":"system","kind":"upscayl","system_model":"realesr-animevideov3-x3"},
    {"id":"realesr-animevideov3-x4","name":"AnimeVideoV3 x4","task":"超分","backend":"Vulkan","runtime":"Upscayl","version":"1.0","source":"system","kind":"upscayl","system_model":"realesr-animevideov3-x4"},
]

def cache_root() -> Path:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    return CACHE_ROOT

def model_cache_dir(model_id: str) -> Path:
    return cache_root() / model_id

def _rembg_installed(model_id: str) -> bool:
    root = Path.home() / ".rembg" / "models"
    return root.exists() and any(root.rglob(f"{model_id}.onnx"))

def _upscayl_installed(model: dict) -> bool:
    root = Path("/usr/lib/upscayl/models")
    name = model.get("system_model", model["id"])
    return (root / f"{name}.bin").exists() and (root / f"{name}.param").exists()

def is_installed(model: dict) -> bool:
    if model["kind"] == "rembg": return _rembg_installed(model["id"])
    if model["kind"] == "upscayl": return _upscayl_installed(model)
    return model_cache_dir(model["id"]).exists()
def model_size(model: dict) -> int:
    if model["kind"] == "rembg":
        root = Path.home() / ".rembg" / "models"
        return sum(p.stat().st_size for p in root.rglob(f"{model['id']}.*") if p.is_file()) if root.exists() else 0
    if model["kind"] == "upscayl":
        root = Path("/usr/lib/upscayl/models"); name=model.get("system_model",model["id"])
        return sum((root/f"{name}{ext}").stat().st_size for ext in (".bin",".param") if (root/f"{name}{ext}").exists())
    d=model_cache_dir(model["id"]); return sum(p.stat().st_size for p in d.rglob("*") if p.is_file()) if d.exists() else 0

def format_size(n: int) -> str:
    units=("B","KB","MB","GB")
    x=float(n)
    for u in units:
        if x < 1024 or u == "GB": return f"{x:.1f} {u}"
        x /= 1024
    return f"{n} B"

def detect_backends() -> list[str]:
    out=["CPU"]
    if shutil.which("upscayl-bin") or shutil.which("upscayl"): out.insert(0,"Vulkan")
    try:
        import onnxruntime as ort
        providers=ort.get_available_providers()
        if "CUDAExecutionProvider" in providers: out.insert(0,"CUDA")
    except Exception: pass
    return list(dict.fromkeys(out))

def registry() -> list[dict]:
    return [dict(m, installed=is_installed(m), size_bytes=model_size(m), size=format_size(model_size(m))) for m in MODEL_REGISTRY]
def get_model(model_id: str) -> dict:
    for m in MODEL_REGISTRY:
        if m["id"] == model_id: return m
    raise KeyError(f"未知模型: {model_id}")

def install_model(model_id: str, progress=None) -> dict:
    model=get_model(model_id)
    if model["kind"] == "upscayl":
        if is_installed(model): return dict(model, installed=True, size=format_size(model_size(model)))
        raise RuntimeError("该模型由系统 Upscayl 提供；请通过系统包/模型包安装，Toolbox 不会写入 /usr/lib。")
    if model["kind"] == "rembg":
        from rembg import new_session
        # rembg performs verified model download and caching itself.
        if progress: progress("正在准备 rembg 模型…")
        new_session(model_id)
        return dict(model, installed=True, size=format_size(model_size(model)))
    raise RuntimeError("该模型暂未提供下载器")

def uninstall_model(model_id: str) -> None:
    model=get_model(model_id)
    if model["kind"] == "upscayl": raise RuntimeError("系统模型不会由 Toolbox 删除。")
    if model["kind"] == "rembg":
        root=Path.home()/".rembg"/"models"
        for p in root.rglob(f"{model_id}.*"):
            if p.is_file(): p.unlink()
        return
    d=model_cache_dir(model_id)
    if d.exists(): shutil.rmtree(d)

def verify_model(model_id: str) -> dict:
    m=get_model(model_id); installed=is_installed(m); size=model_size(m)
    return {"id":model_id,"installed":installed,"size":size,"size_text":format_size(size),"version":m["version"],"backend":m["backend"]}

def backend_for(model_id: str, preferred: str="auto") -> str:
    m=get_model(model_id)
    if preferred != "auto": return preferred
    if m["kind"] == "upscayl": return "Vulkan"
    available=detect_backends()
    return "CUDA" if "CUDA" in available else "CPU"
def backend_settings_path() -> Path:
    return cache_root() / "settings.json"

def selected_backend() -> str:
    p=backend_settings_path()
    if p.exists():
        try: return json.loads(p.read_text(encoding="utf-8")).get("backend", "auto")
        except Exception: pass
    return "auto"

def set_backend(backend: str) -> str:
    if backend not in {"auto", "CUDA", "Vulkan", "CPU"}: raise ValueError("不支持的推理后端")
    p=backend_settings_path(); p.write_text(json.dumps({"backend":backend},ensure_ascii=False,indent=2),encoding="utf-8"); return backend

def export_registry(path: str | Path = INDEX_FILE) -> Path:
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(registry(),ensure_ascii=False,indent=2),encoding="utf-8")
    return path

def model_params(model_id: str) -> dict:
    m=get_model(model_id)
    if m["task"] == "超分": return {"scale":[2,3,4,8],"tile":0,"gpu":0}
    if m["task"] == "抠图": return {"alpha_matting":False,"post_process_mask":True}
    return {}

__all__=["MODEL_REGISTRY","registry","get_model","install_model","uninstall_model","verify_model","detect_backends","backend_for","selected_backend","set_backend","model_params","export_registry","format_size"]
