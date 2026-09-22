from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np

from .utils import ensure_rgb, ensure_rgba, u8, clamp


def _rembg_session(name: str, backend: str = "auto"):
    from rembg import new_session
    if backend == "auto":
        try:
            import onnxruntime as ort
            providers = ort.get_available_providers()
            backend = "CUDA" if "CUDAExecutionProvider" in providers else "CPU"
        except Exception:
            backend = "CPU"
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if backend == "CUDA" else ["CPUExecutionProvider"]
    try:
        return new_session(name, providers=providers)
    except TypeError:
        return new_session(name)


def remove_background(img: np.ndarray, model: str = "u2net",
                     alpha_matting: bool = False, post_process: bool = True,
                     backend: str = "auto") -> np.ndarray:
    from PIL import Image
    from rembg import remove
    from .utils import np_to_pil, pil_to_np
    pil = np_to_pil(ensure_rgb(img))
    sess = _rembg_session(model, backend)
    result_pil = remove(pil, session=sess, alpha_matting=alpha_matting,
                        post_process_mask=post_process)
    return pil_to_np(result_pil)


def remove_background_mask(img: np.ndarray, model: str = "u2net", backend: str = "auto") -> np.ndarray:
    from PIL import Image
    from rembg import remove
    from .utils import np_to_pil
    pil = np_to_pil(ensure_rgb(img))
    sess = _rembg_session(model, backend)
    result = remove(pil, session=sess, only_mask=True)
    arr = np.array(result, dtype=np.float32)
    if arr.max() > 1.0:
        arr = arr / 255.0
    return arr


def composite_on_bg(img: np.ndarray, bg_color=(0, 255, 0)) -> np.ndarray:
    rgba = ensure_rgba(img).astype(np.float32)
    bg = np.array(bg_color, dtype=np.float32)
    alpha = rgba[..., 3:4] / 255.0
    result = rgba[..., :3] * alpha + bg[None, None, :] * (1 - alpha)
    return u8(clamp(result))


BG_REMOVE_MODELS = [
    ("U²-Net 通用 (推荐)", "u2net"),
    ("U²-Net 轻量", "u2netp"),
    ("ISNet 通用", "isnet-general-use"),
    ("Silueta", "silueta"),
]


def denoise_nlm(img: np.ndarray, strength: float = 10.0) -> np.ndarray:
    img_ = ensure_rgb(img)
    h_color = strength * 0.5
    return cv2.fastNlMeansDenoisingColored(img_, None, strength, h_color, 7, 21)


def denoise_bilateral(img: np.ndarray, d: int = 9, sigma_color: float = 75.0,
                      sigma_space: float = 75.0) -> np.ndarray:
    return cv2.bilateralFilter(ensure_rgb(img), d, sigma_color, sigma_space)


def denoise_median(img: np.ndarray, ksize: int = 3) -> np.ndarray:
    return cv2.medianBlur(ensure_rgb(img), ksize)


def denoise_wavelet(img: np.ndarray, strength: float = 10.0) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)
    blurred = cv2.GaussianBlur(img_, (5, 5), 1.0)
    detail = img_ - blurred
    detail_denoised = np.sign(detail) * np.maximum(np.abs(detail) - strength, 0)
    result = blurred + detail_denoised
    return u8(clamp(result))


def upscale_lanczos(img: np.ndarray, scale: float = 2.0) -> np.ndarray:
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    nh, nw = int(h * scale), int(w * scale)
    return cv2.resize(img_, (nw, nh), interpolation=cv2.INTER_LANCZOS4)


def upscale_cubic(img: np.ndarray, scale: float = 2.0) -> np.ndarray:
    img_ = ensure_rgb(img)
    h, w = img_.shape[:2]
    nh, nw = int(h * scale), int(w * scale)
    return cv2.resize(img_, (nw, nh), interpolation=cv2.INTER_CUBIC)


def upscale_sr(img: np.ndarray, model_path: str | None = None,
              scale: int = 4) -> np.ndarray:
    img_ = ensure_rgb(img)
    if model_path is None or not Path(model_path).exists():
        return upscale_lanczos(img, scale)
    sr = cv2.dnn_superres.DnnSuperResImpl_create()
    sr.readModel(model_path)
    sr.setModel("edsr", scale)
    return sr.upsample(img_)


def upscale_realesrgan(img: np.ndarray, scale: int = 4, model: str = "realesrgan-x4plus") -> np.ndarray:
    """Run the real Real-ESRGAN neural model through Upscayl's Vulkan runtime."""
    import os
    import subprocess
    import tempfile
    from PIL import Image

    binary = "/usr/bin/upscayl-bin" if os.path.exists("/usr/bin/upscayl-bin") else "/usr/bin/upscayl"
    if not os.path.exists(binary):
        raise RuntimeError("未找到 Upscayl/Real-ESRGAN 运行时，请安装 upscayl")
    model_dir = "/usr/lib/upscayl/models"
    if not (Path(model_dir, f"{model}.bin").exists() and Path(model_dir, f"{model}.param").exists()):
        raise RuntimeError(f"缺少 Real-ESRGAN 模型: {model}")

    with tempfile.TemporaryDirectory(prefix="toolbox-esrgan-") as td:
        inp, out = Path(td) / "input.png", Path(td) / "output.png"
        Image.fromarray(ensure_rgb(img)).save(inp)
        cmd = [binary, "-i", str(inp), "-o", str(out), "-z", "4", "-s", str(scale),
               "-m", model_dir, "-n", model, "-g", "0", "-f", "png"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError(f"Real-ESRGAN 推理失败: {(proc.stderr or proc.stdout or '').strip()[-1200:]}")
        with Image.open(out) as result:
            return np.array(result.convert("RGB"), dtype=np.uint8)


UPSCALE_MODELS = [("Real-ESRGAN x4+ (RTX/Vulkan)", "realesrgan-x4plus")]


def ai_model_status() -> dict:
    import importlib.util
    return {
        "rembg": importlib.util.find_spec("rembg") is not None,
        "onnxruntime": importlib.util.find_spec("onnxruntime") is not None,
        "upscayl": Path("/usr/bin/upscayl-bin").exists() or Path("/usr/bin/upscayl").exists(),
        "realesrgan-x4plus": Path("/usr/lib/upscayl/models/realesrgan-x4plus.bin").exists(),
    }


# ---- AI model registry ----------------------------------------------------
# One task may expose many interchangeable local models.
AI_MODEL_REGISTRY = [
    {"id":"u2net","name":"U²-Net","task":"background-removal","backend":"onnx/rembg","source":"rembg"},
    {"id":"u2netp","name":"U²-Netp","task":"background-removal","backend":"onnx/rembg","source":"rembg"},
    {"id":"isnet-general-use","name":"IS-Net General","task":"background-removal","backend":"onnx/rembg","source":"rembg"},
    {"id":"silueta","name":"Silueta","task":"background-removal","backend":"onnx/rembg","source":"rembg"},
    {"id":"realesrgan-x4plus","name":"Real-ESRGAN x4+","task":"upscale","backend":"vulkan","source":"upscayl"},
    {"id":"realesrgan-x4plus-anime","name":"Real-ESRGAN x4+ Anime","task":"upscale","backend":"vulkan","source":"upscayl"},
    {"id":"realesrnet-x4plus","name":"Real-ESRNet x4+","task":"upscale","backend":"vulkan","source":"upscayl"},
    {"id":"realesr-animevideov3","name":"Real-ESRGAN AnimeVideoV3","task":"upscale","backend":"vulkan","source":"upscayl"},
    {"id":"depth-anything-v2","name":"Depth Anything V2","task":"depth","backend":"onnx/torch","source":"huggingface"},
]


def list_ai_models(task: str | None = None) -> list[dict]:
    models = AI_MODEL_REGISTRY if task is None else [m for m in AI_MODEL_REGISTRY if m["task"] == task]
    return [dict(m, available=ai_model_available(m["id"])) for m in models]


def ai_model_available(model_id: str) -> bool:
    if model_id in {"u2net", "u2netp", "isnet-general-use", "silueta"}:
        root = Path.home() / ".rembg" / "models"
        return root.exists() and any(root.rglob(f"{model_id}.onnx"))
    if Path("/usr/lib/upscayl/models", f"{model_id}.bin").exists() and Path("/usr/lib/upscayl/models", f"{model_id}.param").exists():
        return True
    return False


def model_capabilities() -> dict[str, list[dict]]:
    return {task: list_ai_models(task) for task in sorted({m["task"] for m in AI_MODEL_REGISTRY})}


def colorize_simple(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(ensure_rgb(img), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    result = np.zeros((gray.shape[0], gray.shape[1], 3), dtype=np.float32)
    result[..., 0] = gray * 0.9 + 0.05
    result[..., 1] = gray * 0.95 + 0.03
    result[..., 2] = gray * 0.8 + 0.1
    return u8(clamp(result * 255))


def colorize_transfer(img: np.ndarray, style: str = "vintage") -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    style_colors = {
        "vintage": [(0.95, 0.85, 0.70), (0.85, 0.75, 0.60)],
        "warm": [(1.0, 0.9, 0.7), (0.9, 0.75, 0.55)],
        "cool": [(0.7, 0.8, 1.0), (0.6, 0.7, 0.9)],
        "sunset": [(1.0, 0.85, 0.7), (0.95, 0.7, 0.55)],
        "forest": [(0.7, 0.9, 0.75), (0.55, 0.8, 0.6)],
    }
    c1, c2 = style_colors.get(style, style_colors["vintage"])
    result = img_.copy()
    result[..., 0] = img_[..., 0] * c1[0]
    result[..., 1] = img_[..., 1] * c1[1] + img_[..., 0] * (1 - c1[0]) * 0.3
    result[..., 2] = img_[..., 2] * c1[2] + img_[..., 0] * (1 - c1[0]) * 0.2
    result = result * 0.7 + np.array(c2, dtype=np.float32)[None, None, :] * 0.3
    return u8(clamp(result * 255))


def colorize_manual(img: np.ndarray, color: tuple = (255, 180, 100),
                   intensity: float = 0.5) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    gray = img_.mean(axis=-1, keepdims=True)
    target = np.array(color, dtype=np.float32) / 255.0
    result = target[None, None, :] * gray * intensity + img_ * (1 - intensity)
    return u8(clamp(result * 255))


def depth_map(img: np.ndarray) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32) / 255.0
    gray = img_.mean(axis=-1)
    h, w = gray.shape

    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    edges = np.sqrt(sobel_x ** 2 + sobel_y ** 2)

    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2.0, h / 2.0
    depth = 1 - np.sqrt(((x - cx) / cx) ** 2 + ((y - cy) / cy) ** 2) / 1.414

    depth = depth * 0.5 + gray * 0.3 + (edges / edges.max().clip(min=1)) * 0.2

    depth_min, depth_max = depth.min(), depth.max()
    if depth_max - depth_min > 1e-6:
        depth = (depth - depth_min) / (depth_max - depth_min)

    result = (depth * 255).astype(np.uint8)
    result_colored = cv2.applyColorMap(result, cv2.COLORMAP_INFERNO)
    return result_colored


def depth_map_rembg(img: np.ndarray, model: str = "u2net") -> np.ndarray | None:
    try:
        from PIL import Image
        from rembg import new_session, remove
        from .utils import np_to_pil, pil_to_np
        pil = np_to_pil(ensure_rgb(img))
        sess = new_session(model)
        result = remove(pil, session=sess, only_mask=True)
        arr = np.array(result, dtype=np.uint8)
        if arr.ndim == 3:
            arr = arr[..., 0]
        return cv2.applyColorMap(arr, cv2.COLORMAP_INFERNO)
    except Exception:
        return None


DEPTH_MODELS = [
    ("简单启发式 (无需模型)", "heuristic"),
    ("U²-Net 分割深度图", "u2net"),
    ("ISNet 通用", "isnet-general-use"),
]


def portrait_bokeh(img: np.ndarray, model: str = "u2net",
                   blur_strength: float = 15.0) -> np.ndarray:
    img_ = ensure_rgb(img)
    try:
        mask = remove_background_mask(img_, model)
    except Exception:
        h, w = img_.shape[:2]
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = w / 2.0, h / 2.0
        dist = np.sqrt(((x - cx) / cx) ** 2 + ((y - cy) / cy) ** 2)
        mask = np.clip(1 - dist * 1.5, 0, 1)

    blurred = cv2.GaussianBlur(img_, (0, 0), blur_strength)
    alpha = mask[..., None]
    result = img_.astype(np.float32) * alpha + blurred.astype(np.float32) * (1 - alpha)
    return u8(clamp(result))


def ai_enhance(img: np.ndarray, denoise: float = 5.0, upscale: float = 1.0,
               saturation: float = 1.15, contrast: float = 1.1) -> np.ndarray:
    img_ = ensure_rgb(img).astype(np.float32)

    if denoise > 0:
        img_ = denoise_nlm(u8(clamp(img_)), denoise).astype(np.float32)

    if upscale > 1.0:
        h, w = img_.shape[:2]
        nh, nw = int(h * upscale), int(w * upscale)
        img_ = cv2.resize(img_, (nw, nh), interpolation=cv2.INTER_LANCZOS4)

    img_ = (img_ - 128) * contrast + 128

    hsv = cv2.cvtColor(u8(clamp(img_)), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation, 0, 255)
    img_ = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)

    img_ = u8(clamp(img_))
    return img_
