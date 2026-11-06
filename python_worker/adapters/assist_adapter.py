"""辅助工具适配：OCR / PDF / 条形码 / ASCII / 对比 / 校验和 / 直方图 / LUT /
媒体 / EXIF / 水印 / 归档 / 加密 / Base64 / AI 的协议化（Phase 7，
docs/ipc-protocol.md §3.8）。

模式对齐 filter_adapter.list_filters / generate_adapter.list_generators：注册
表来自 processors 既有实现的元信息，本层只做协议化与接线，不重写任何算法
（1.0 资产复用规则，总纲 §15.5）。资产映射（逐函数）：

- OCR              → processors/parity.py ocr_image（pytesseract + tesseract 二进制）
- PDF              → processors/pdf_tools.py 全部 7 函数（pypdf，核心依赖）；
  pdf.to_images 接 pdf2image.convert_from_path（requirements 声明依赖 +
  poppler 外部二进制；1.0 app/main_window.py:1519 明示该导出路径）
- 条形码           → processors/barcode.py generate_qr（qrcode）/
  generate_barcode_ean13（pystrich）/ decode_qr（pyzbar）
- ASCII            → processors/ascii.py ascii_art
- 对比             → processors/compare.py compare
- 校验和 / Base64  → processors/checksum.py file_hashes / parity.base64_encode/decode
- 直方图           → processors/histogram.py histogram_rgb/luma/hsv
- LUT              → processors/lut.py load_lut_from_cube + apply_cube_lut
- 媒体             → processors/media.py extract_frames / convert_animation
  （magick / ffmpeg 外部二进制）
- EXIF / 水印 / 归档 / 加密 → processors/parity.py extract_exif / strip_exif /
  watermark / archive_images / encrypt_file / decrypt_file
- AI               → processors/ai.py remove_background / composite_on_bg /
  upscale_sr / upscale_realesrgan / denoise_nlm / colorize_simple /
  colorize_transfer + processors/ai_models.py registry（模型管理）

依赖诚实原则（总纲 Phase 7 要求）：所有外部依赖在 assist.list 构建时与动作
提交前用同一探测函数如实判定；缺失 → 条目 available=false + optional_deps
列出缺失名，动作提交 → DEPENDENCY_MISSING（details.missing 同源）。可用性
探测不做缓存（安装依赖后立即可见）。1.0 资产中"假实现"的降级路径不暴露：
generate_data_matrix 实际生成的是 QR（非 DataMatrix）、EAN13 的 PIL 兜底生成
的是非功能性条纹——两者一律依赖缺失即拒绝，不以假乱真。
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .. import protocol
from .filter_adapter import write_preview
from .image_adapter import WorkerError

ERR_DEP = protocol.ERR_DEPENDENCY_MISSING

_FMT_RE = re.compile(r'^[a-z0-9]{2,5}$')  # 媒体帧格式：防止经 fmt 注入输出路径

# AI 抠图模型取值域（processors/ai.py BG_REMOVE_MODELS 的模型 id）。
_BACKGROUND_MODEL_IDS = ('u2net', 'u2netp', 'isnet-general-use', 'silueta')
# AI 色彩化取值域（processors/ai.py colorize_transfer style_colors）。
_COLORIZE_STYLES = ('vintage', 'warm', 'cool', 'sunset', 'forest')
# 水印位置取值域（processors/parity.py watermark 的 position 表）。
_WATERMARK_POSITIONS = ('top-left', 'top-right', 'bottom-left', 'bottom-right', 'center')


# ---- 依赖探测（目录与提交共用同一函数；缺失名如实列出，不缓存）--------------

def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _which(name: str) -> bool:
    return shutil.which(name) is not None


def missing_deps_ocr() -> list[str]:
    """OCR = pytesseract 模块 + tesseract 二进制（缺一不可）。"""
    missing = []
    if not _module_available('pytesseract'):
        missing.append('pytesseract')
    if not _which('tesseract'):
        missing.append('tesseract')
    return missing


def missing_deps_pdf_to_images() -> list[str]:
    """pdf.to_images = pdf2image 模块 + poppler（pdftoppm）二进制。"""
    missing = []
    if not _module_available('pdf2image'):
        missing.append('pdf2image')
    if not _which('pdftoppm'):
        missing.append('poppler')
    return missing


def missing_deps_qr() -> list[str]:
    return [] if _module_available('qrcode') else ['qrcode']


def missing_deps_ean13() -> list[str]:
    return [] if _module_available('pystrich') else ['pystrich']


def missing_deps_decode() -> list[str]:
    # 探测 pyzbar.pyzbar（非裸 pyzbar）：zbar 原生库缺失时父包导入即失败，
    # find_spec 连带返回 None——与运行期 `from pyzbar import pyzbar` 同口径。
    return [] if _module_available('pyzbar.pyzbar') else ['pyzbar']


def missing_deps_media(fmt: str | None = None) -> list[str]:
    """媒体工具外部二进制：gif/webp/apng 用 magick，jxl 用 ffmpeg。"""
    if fmt and fmt.lower() == 'jxl':
        return [] if _which('ffmpeg') else ['ffmpeg']
    return [] if _which('magick') else ['magick']


def missing_deps_crypto() -> list[str]:
    return [] if _module_available('cryptography') else ['cryptography']


def missing_deps_ai_background(model: str = 'u2net') -> list[str]:
    """AI 抠图 = rembg + onnxruntime 模块 + 模型文件（~/.rembg/models，
    processors/ai.py ai_model_available 判定）。"""
    missing = [dep for dep in ('rembg', 'onnxruntime') if not _module_available(dep)]
    from processors import ai as ai_processor
    if not ai_processor.ai_model_available(model):
        missing.append(f'model:{model}')
    return missing


def missing_deps_ai_upscale(model_path: str | None = None) -> list[str]:
    """AI 超分：模型路径配置命中（cv2.dnn_superres，无外部二进制）即可用；
    否则要求 upscayl 二进制 + Real-ESRGAN 系统模型文件（如实探测）。"""
    if model_path and Path(model_path).expanduser().is_file():
        return []
    missing = []
    if not (_which('upscayl-bin') or _which('upscayl')):
        missing.append('upscayl')
    from processors import ai as ai_processor
    if not ai_processor.ai_model_status().get('realesrgan-x4plus'):
        missing.append('model:realesrgan-x4plus')
    return missing


# ---- 模型路径配置读取（§3.8 AI 降级路径的配置面）---------------------------

def model_path_config() -> dict[str, str]:
    """AI 模型路径配置：settings.json（processors/ai_models.py
    backend_settings_path，与推理后端同一配置文件）的 `model_paths` 键优先，
    其次 TOOLBOX_AI_MODEL_DIR 环境变量指向目录下的文件（文件名去扩展名为键）。
    显式配置覆盖环境目录。仅读取、不创建不下载。"""
    paths: dict[str, str] = {}
    env_dir = os.environ.get('TOOLBOX_AI_MODEL_DIR')
    if env_dir:
        directory = Path(env_dir).expanduser()
        if directory.is_dir():
            for entry in sorted(directory.iterdir()):
                if entry.is_file():
                    paths.setdefault(entry.stem, str(entry))
    from processors import ai_models
    settings = ai_models.backend_settings_path()
    if settings.exists():
        try:
            config = json.loads(settings.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            config = {}
        configured = config.get('model_paths')
        if isinstance(configured, dict):
            for key, value in configured.items():
                if isinstance(value, str) and value.strip():
                    paths[str(key)] = value.strip()
    return paths


def _configured_model_path(explicit: Any) -> str | None:
    """ai.upscale 的模型文件解析：params.model_path 显式指定优先，其次配置键
    edsr / upscale / super-resolution（cv2.dnn_superres 的 EDSR .pb 模型）。"""
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    config = model_path_config()
    for key in ('edsr', 'upscale', 'super-resolution'):
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


# ---- assist.list 目录（docs/ipc-protocol.md §3.8）---------------------------
#
# 条目 key 即动作名（generate.list 的"键即 generator_key"同款）；type 为
# sync/async；available/optional_deps 由 deps 闭包在构建时如实探测。
# deps 用 lambda 延迟查找模块全局，保证测试可 patch（同 generate_adapter 的
# gmic 探测注入方式）。

CATEGORY_LABELS = {
    'ai': 'AI 工具',
    'archive': '归档',
    'ascii': 'ASCII 艺术',
    'barcode': '条形码',
    'base64': 'Base64',
    'checksum': '校验和',
    'compare': '图像对比',
    'crypto': '加密',
    'exif': 'EXIF',
    'histogram': '直方图',
    'lut': '颜色查找表',
    'media': '媒体工具',
    'ocr': 'OCR 文字识别',
    'pdf': 'PDF 工具',
    'watermark': '水印',
}

_TOOL_TABLE: list[dict[str, Any]] = [
    # ---- OCR ----
    {'key': 'ocr.run', 'name': 'OCR 文字识别', 'category': 'ocr', 'type': 'async',
     'description': 'Tesseract OCR 识别图片中的文字（processors/parity.py ocr_image）',
     'deps': lambda: missing_deps_ocr()},
    # ---- PDF（processors/pdf_tools.py，pypdf 核心依赖；to_images 需 pdf2image+poppler）----
    {'key': 'pdf.merge', 'name': '合并 PDF', 'category': 'pdf', 'type': 'async',
     'description': '多个 PDF 合并为一个文件（processors/pdf_tools.py merge_pdfs）',
     'deps': lambda: []},
    {'key': 'pdf.split', 'name': '拆分 PDF', 'category': 'pdf', 'type': 'async',
     'description': '逐页拆分为单页 PDF（processors/pdf_tools.py split_pdf）',
     'deps': lambda: []},
    {'key': 'pdf.rotate', 'name': '旋转 PDF', 'category': 'pdf', 'type': 'async',
     'description': '整册页面旋转（processors/pdf_tools.py rotate_pdf）',
     'deps': lambda: []},
    {'key': 'pdf.remove_pages', 'name': '删除 PDF 页', 'category': 'pdf', 'type': 'async',
     'description': '按 1 起始页码删除页面（processors/pdf_tools.py remove_pages）',
     'deps': lambda: []},
    {'key': 'pdf.extract_text', 'name': '提取 PDF 文本', 'category': 'pdf', 'type': 'async',
     'description': '提取全册文本层（processors/pdf_tools.py extract_text）',
     'deps': lambda: []},
    {'key': 'pdf.set_metadata', 'name': '设置 PDF 元数据', 'category': 'pdf', 'type': 'async',
     'description': '写入文档信息字典（processors/pdf_tools.py set_metadata）',
     'deps': lambda: []},
    {'key': 'pdf.protect', 'name': 'PDF 加密', 'category': 'pdf', 'type': 'async',
     'description': '口令加密 PDF（processors/pdf_tools.py protect_pdf）',
     'deps': lambda: []},
    {'key': 'pdf.to_images', 'name': 'PDF 转图片', 'category': 'pdf', 'type': 'async',
     'description': '按 DPI 逐页栅格化为 PNG（pdf2image + poppler）',
     'deps': lambda: missing_deps_pdf_to_images()},
    # ---- 条形码 ----
    {'key': 'barcode.qr.generate', 'name': '生成二维码', 'category': 'barcode', 'type': 'async',
     'description': 'QR 码生成（processors/barcode.py generate_qr）',
     'deps': lambda: missing_deps_qr()},
    {'key': 'barcode.ean13.generate', 'name': '生成 EAN-13', 'category': 'barcode', 'type': 'async',
     'description': 'EAN-13 条码生成（processors/barcode.py generate_barcode_ean13，'
                    'pystrich 缺失时拒绝——PIL 兜底为非功能性条纹，不暴露）',
     'deps': lambda: missing_deps_ean13()},
    {'key': 'barcode.decode', 'name': '识别条码/二维码', 'category': 'barcode', 'type': 'sync',
     'description': '解码图中的条码/二维码（processors/barcode.py decode_qr，pyzbar）',
     'deps': lambda: missing_deps_decode()},
    # ---- 文本 / 分析 ----
    {'key': 'ascii.render', 'name': 'ASCII 艺术', 'category': 'ascii', 'type': 'sync',
     'description': '图像转 ASCII 字符画文本（processors/ascii.py ascii_art）',
     'deps': lambda: []},
    {'key': 'compare.images', 'name': '图像对比', 'category': 'compare', 'type': 'async',
     'description': 'MAE/RMSE/MSE/PSNR/NCC/SSIM 指标（processors/compare.py compare）',
     'deps': lambda: []},
    {'key': 'checksum.file', 'name': '文件校验和', 'category': 'checksum', 'type': 'sync',
     'description': 'MD5/SHA/CRC32/BLAKE2 全家桶（processors/checksum.py file_hashes）',
     'deps': lambda: []},
    {'key': 'histogram.compute', 'name': '直方图', 'category': 'histogram', 'type': 'sync',
     'description': 'RGB/亮度/HSV 直方图（processors/histogram.py）',
     'deps': lambda: []},
    {'key': 'lut.apply', 'name': '应用 .cube LUT', 'category': 'lut', 'type': 'async',
     'description': '3D .cube 颜色查找表（processors/lut.py load_lut_from_cube/apply_cube_lut）',
     'deps': lambda: []},
    # ---- 媒体（外部二进制）----
    {'key': 'media.extract_frames', 'name': '动画抽帧', 'category': 'media', 'type': 'async',
     'description': 'ImageMagick 逐帧导出（processors/media.py extract_frames）',
     'deps': lambda: missing_deps_media()},
    {'key': 'media.convert_animation', 'name': '合成动画', 'category': 'media', 'type': 'async',
     'description': '帧序列合成 gif/webp/apng（magick）/jxl（ffmpeg）'
                    '（processors/media.py convert_animation）',
     'deps': lambda: missing_deps_media()},
    # ---- 文件工具 ----
    {'key': 'exif.extract', 'name': '读取 EXIF', 'category': 'exif', 'type': 'sync',
     'description': '读取图片 EXIF 元数据（processors/parity.py extract_exif）',
     'deps': lambda: []},
    {'key': 'exif.strip', 'name': '删除 EXIF', 'category': 'exif', 'type': 'async',
     'description': '去除元数据重存图片（processors/parity.py strip_exif）',
     'deps': lambda: []},
    {'key': 'watermark.text', 'name': '文字水印', 'category': 'watermark', 'type': 'async',
     'description': '给图片加文字水印（processors/parity.py watermark）',
     'deps': lambda: []},
    {'key': 'archive.create', 'name': '打包 ZIP', 'category': 'archive', 'type': 'async',
     'description': '图片打包为 ZIP（processors/parity.py archive_images）',
     'deps': lambda: []},
    {'key': 'crypto.encrypt', 'name': '文件加密', 'category': 'crypto', 'type': 'async',
     'description': '口令 Fernet 加密（processors/parity.py encrypt_file）',
     'deps': lambda: missing_deps_crypto()},
    {'key': 'crypto.decrypt', 'name': '文件解密', 'category': 'crypto', 'type': 'async',
     'description': 'Fernet 口令解密（processors/parity.py decrypt_file）',
     'deps': lambda: missing_deps_crypto()},
    {'key': 'base64.encode', 'name': 'Base64 编码', 'category': 'base64', 'type': 'async',
     'description': '文件编码为 Base64 文本（processors/parity.py base64_encode）',
     'deps': lambda: []},
    {'key': 'base64.decode', 'name': 'Base64 解码', 'category': 'base64', 'type': 'async',
     'description': 'Base64 文本解码为文件（processors/parity.py base64_decode）',
     'deps': lambda: []},
    # ---- AI（重模型能力默认降级，见 §3.8）----
    {'key': 'ai.background.remove', 'name': 'AI 背景移除', 'category': 'ai', 'type': 'async',
     'description': 'rembg 抠图（processors/ai.py remove_background；'
                    'rembg/onnxruntime/模型文件缺失时置灰）',
     'deps': lambda: missing_deps_ai_background('u2net')},
    {'key': 'ai.upscale', 'name': 'AI 超分', 'category': 'ai', 'type': 'async',
     'description': 'Real-ESRGAN（upscayl）或配置的 EDSR 模型'
                    '（processors/ai.py upscale_realesrgan/upscale_sr）',
     'deps': lambda: missing_deps_ai_upscale(_configured_model_path(None))},
    {'key': 'ai.denoise', 'name': 'AI 降噪', 'category': 'ai', 'type': 'async',
     'description': '非局部均值降噪（processors/ai.py denoise_nlm，OpenCV 核心，无外部依赖）',
     'deps': lambda: []},
    {'key': 'ai.colorize', 'name': 'AI 色彩化', 'category': 'ai', 'type': 'async',
     'description': '启发式/风格色彩映射（processors/ai.py colorize_simple/colorize_transfer，'
                    'OpenCV 核心，无外部依赖）',
     'deps': lambda: []},
    {'key': 'ai.models.list', 'name': 'AI 模型管理', 'category': 'ai', 'type': 'sync',
     'description': '模型注册表安装状态 + 推理后端 + 模型路径配置'
                    '（processors/ai_models.py registry/detect_backends）',
     'deps': lambda: []},
]


def list_tools() -> list[dict[str, Any]]:
    """assist.list：与 filter.list / generate.list 同构的辅助工具目录。
    available=false 表示可选依赖未满足，消费方须置灰且不得发起对应动作；
    optional_deps 为缺失依赖名列表（与提交时 DEPENDENCY_MISSING 的
    details.missing 同源）。条目按 (category, key) 排序。"""
    items: list[dict[str, Any]] = []
    for row in _TOOL_TABLE:
        missing = sorted(set(row['deps']()))
        items.append({
            'key': row['key'],
            'name': row['name'],
            'category': row['category'],
            'category_label': CATEGORY_LABELS.get(row['category'], row['category']),
            'description': row['description'],
            'type': row['type'],
            'available': not missing,
            'optional_deps': missing,
        })
    items.sort(key=lambda item: (item['category'], item['key']))
    return items


# ---- 参数与依赖校验助手（INVALID_PARAMS 优先于 DEPENDENCY_MISSING）----------

def _require_deps(action: str, missing: list[str]) -> None:
    if missing:
        raise WorkerError(ERR_DEP, f'{action} 缺少可选依赖: {", ".join(missing)}',
                          {'missing': missing})


def _existing_file(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'缺少 {label}')
    path = Path(value).expanduser()
    if not path.is_file():
        raise WorkerError(protocol.ERR_FILE_NOT_FOUND, f'文件不存在: {value}')
    return path


def _require_existing_file(params: dict, key: str) -> Path:
    return _existing_file(params.get(key), key)


def _output_file(value: Any, label: str) -> Path:
    """输出文件路径：父目录必须已存在（processors 资产不做父目录创建）。"""
    if not isinstance(value, str) or not value.strip():
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'缺少 {label}')
    path = Path(value).expanduser()
    if not path.parent.is_dir():
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'输出目录不存在: {path.parent}')
    return path


def _require_output_file(params: dict, key: str = 'output') -> Path:
    return _output_file(params.get(key), key)


def _existing_files_list(params: dict, key: str = 'paths') -> list[Path]:
    raw = params.get(key)
    if not isinstance(raw, list) or not raw:
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'{key} 必须是非空数组')
    return [_existing_file(item, f'{key}[{i}]') for i, item in enumerate(raw)]


def _int_in(params: dict, key: str, default: int, lo: int, hi: int) -> int:
    value = params.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'{key} 必须是整数')
    if isinstance(value, float) and not float(value).is_integer():
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'{key} 必须是整数')
    number = int(value)
    if not lo <= number <= hi:
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'{key} 必须 {lo}..{hi}，得到 {number}')
    return number


def _number_in(params: dict, key: str, default: float, lo: float, hi: float) -> float:
    value = params.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'{key} 必须是数值')
    number = float(value)
    if not lo <= number <= hi or not math.isfinite(number):
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'{key} 必须 {lo}..{hi}，得到 {number}')
    return number


def _require_flag(params: dict, key: str, default: bool) -> bool:
    value = params.get(key, default)
    if not isinstance(value, bool):
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'{key} 必须是布尔值')
    return value


def _json_safe(value: Any) -> Any:
    """EXIF 等资产返回值 → JSON 安全形状（JSON Lines 通道只承载 JSON 类型）：
    bytes 解码为文本、PIL IFDRational 等标量化为字符串、浮点非有限值如实
    转字符串，不虚构数值。"""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return str(value)


def _finite_or_none(value: float) -> float | None:
    """对比指标：PSNR 在图像全同时为 inf、NCC 在常数图上为 NaN——协议面以
    null 表示"数学上未定义/无穷大"，不输出非法 JSON（json.dumps 的
    Infinity/NaN 令牌）。"""
    number = float(value)
    return number if math.isfinite(number) else None


def _deliver_image(image: np.ndarray, temp_dir: Path, key: str) -> dict[str, Any]:
    """像素结果经 §4 临时 PNG 通道交付（path/width/height/sha256，无 Base64）。
    max_side 取图像最长边 → 不降采样，按处理结果原尺寸落盘；文件按工具 key
    覆盖命名（§4 防堆积规则，同 generate.render）。"""
    max_side = max(int(image.shape[0]), int(image.shape[1]), 16)
    return write_preview(np.ascontiguousarray(image), Path(temp_dir), key, max_side=max_side)


# ---- OCR（ocr.run，async）---------------------------------------------------

def ocr_run_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    lang = str(params.get('lang') or 'eng')
    psm = _int_in(params, 'psm', 3, 0, 13)
    _require_deps('ocr.run', missing_deps_ocr())

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(10, 'OCR 识别')
        cancel_token.raise_if_cancelled()
        from processors.parity import ocr_image
        text = ocr_image(str(path), lang=lang, psm=psm)
        cancel_token.raise_if_cancelled()
        return {'text': text}

    return job


# ---- PDF（processors/pdf_tools.py 资产，全部 async）--------------------------
# 输出文件动作要求父目录已存在（提交前判定，§3.8）；output_dir 类参数由
# 资产自行创建目录，缺省落在 Worker 会话临时目录（§4 会话生命周期）。

def pdf_merge_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    paths = _existing_files_list(params)
    output = _require_output_file(params)

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(20, '合并 PDF')
        cancel_token.raise_if_cancelled()
        from processors.pdf_tools import merge_pdfs
        out = merge_pdfs([str(p) for p in paths], str(output))
        cancel_token.raise_if_cancelled()
        return {'path': out}

    return job


def pdf_split_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    out_dir = (Path(str(params['output_dir'])).expanduser()
               if isinstance(params.get('output_dir'), str) and params['output_dir'].strip()
               else Path(temp_dir or '.') / 'pdf-split')

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(20, '拆分 PDF')
        cancel_token.raise_if_cancelled()
        from processors.pdf_tools import split_pdf
        files = split_pdf(str(path), str(out_dir))
        cancel_token.raise_if_cancelled()
        return {'files': files, 'output_dir': str(out_dir)}

    return job


def pdf_rotate_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    output = _require_output_file(params)
    degrees = _int_in(params, 'degrees', 90, -360, 360)
    if degrees == 0 or degrees % 90 != 0:
        # pypdf PageObject.rotate 仅接受 90 的倍数（资产内 ValueError 前移到提交前）。
        raise WorkerError(protocol.ERR_INVALID_PARAMS,
                          f'degrees 必须是 90 的非零倍数，得到 {degrees}')

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(20, '旋转 PDF')
        cancel_token.raise_if_cancelled()
        from processors.pdf_tools import rotate_pdf
        out = rotate_pdf(str(path), str(output), degrees=degrees)
        cancel_token.raise_if_cancelled()
        return {'path': out}

    return job


def pdf_remove_pages_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    output = _require_output_file(params)
    raw_pages = params.get('pages')
    if not isinstance(raw_pages, list) or not raw_pages:
        raise WorkerError(protocol.ERR_INVALID_PARAMS, 'pages 必须是非空数组（1 起始页码）')
    pages: list[int] = []
    for i, item in enumerate(raw_pages):
        if isinstance(item, bool) or not isinstance(item, (int, float)) or (
                isinstance(item, float) and not float(item).is_integer()):
            raise WorkerError(protocol.ERR_INVALID_PARAMS, f'pages[{i}] 必须是整数')
        page = int(item)
        if page < 1:
            raise WorkerError(protocol.ERR_INVALID_PARAMS,
                              f'pages[{i}] 必须 ≥ 1（1 起始页码），得到 {page}')
        pages.append(page)

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(20, '删除 PDF 页')
        cancel_token.raise_if_cancelled()
        from processors.pdf_tools import remove_pages
        out = remove_pages(str(path), str(output), pages)
        cancel_token.raise_if_cancelled()
        return {'path': out}

    return job


def pdf_extract_text_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(20, '提取 PDF 文本')
        cancel_token.raise_if_cancelled()
        from processors.pdf_tools import extract_text
        text = extract_text(str(path))
        cancel_token.raise_if_cancelled()
        return {'text': text}

    return job


def pdf_set_metadata_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    output = _require_output_file(params)
    raw = params.get('metadata')
    if not isinstance(raw, dict):
        raise WorkerError(protocol.ERR_INVALID_PARAMS, 'metadata 必须是对象')
    metadata = {str(k): str(v) for k, v in raw.items()}

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(20, '写入 PDF 元数据')
        cancel_token.raise_if_cancelled()
        from processors.pdf_tools import set_metadata
        out = set_metadata(str(path), str(output), metadata)
        cancel_token.raise_if_cancelled()
        return {'path': out}

    return job


def pdf_protect_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    output = _require_output_file(params)
    password = params.get('password')
    if not isinstance(password, str) or not password:
        raise WorkerError(protocol.ERR_INVALID_PARAMS, 'password 必须是非空字符串')

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(20, '加密 PDF')
        cancel_token.raise_if_cancelled()
        from processors.pdf_tools import protect_pdf
        out = protect_pdf(str(path), str(output), password)
        cancel_token.raise_if_cancelled()
        return {'path': out}

    return job


def pdf_to_images_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    dpi = _int_in(params, 'dpi', 150, 72, 1200)
    out_dir = (Path(str(params['output_dir'])).expanduser()
               if isinstance(params.get('output_dir'), str) and params['output_dir'].strip()
               else Path(temp_dir or '.') / 'pdf-to-images')
    _require_deps('pdf.to_images', missing_deps_pdf_to_images())
    stem = path.stem

    def job(progress_cb, cancel_token) -> dict:
        from pdf2image import convert_from_path
        progress_cb(10, '栅格化 PDF')
        cancel_token.raise_if_cancelled()
        pages = convert_from_path(str(path), dpi=dpi)
        out_dir.mkdir(parents=True, exist_ok=True)
        files: list[str] = []
        for i, page_image in enumerate(pages, 1):
            cancel_token.raise_if_cancelled()
            target = out_dir / f'{stem}_{i:03d}.png'
            page_image.save(target, format='PNG')
            files.append(str(target))
            progress_cb(10 + int(i * 85 / max(1, len(pages))), f'导出第 {i}/{len(pages)} 页')
        return {'files': files, 'pages': len(files), 'output_dir': str(out_dir), 'dpi': dpi}

    return job


# ---- 条形码（processors/barcode.py 资产）------------------------------------

def barcode_qr_generate_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    data = params.get('data')
    if not isinstance(data, str) or not data:
        raise WorkerError(protocol.ERR_INVALID_PARAMS, 'data 必须是非空字符串')
    size = _int_in(params, 'size', 300, 16, 4096)
    error_correction = str(params.get('error_correction') or 'M').upper()
    if error_correction not in ('L', 'M', 'Q', 'H'):
        raise WorkerError(protocol.ERR_INVALID_PARAMS,
                          f'error_correction 必须是 L/M/Q/H，得到 {error_correction}')
    _require_deps('barcode.qr.generate', missing_deps_qr())

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(30, '生成二维码')
        cancel_token.raise_if_cancelled()
        from processors.barcode import generate_qr
        image = generate_qr(data, size=size, error_correction=error_correction)
        progress_cb(85, '写入结果文件')
        return _deliver_image(image, temp_dir or '.', 'barcode-qr')

    return job


def barcode_ean13_generate_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    data = params.get('data')
    if not isinstance(data, str) or not data.isdigit() or len(data) not in (12, 13):
        raise WorkerError(protocol.ERR_INVALID_PARAMS,
                          'data 必须是 12 或 13 位数字字符串（EAN-13）')
    height = _int_in(params, 'height', 100, 16, 4096)
    # 依赖检查在参数校验之后：参数非法永远报 INVALID_PARAMS，不因依赖缺失掩盖。
    _require_deps('barcode.ean13.generate', missing_deps_ean13())

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(30, '生成 EAN-13')
        cancel_token.raise_if_cancelled()
        from processors.barcode import generate_barcode_ean13
        image = generate_barcode_ean13(data, height=height)
        progress_cb(85, '写入结果文件')
        return _deliver_image(image, temp_dir or '.', 'barcode-ean13')

    return job


def barcode_decode(params: dict) -> dict[str, Any]:
    """barcode.decode（sync）：解码输入图中的条码/二维码。"""
    path = _require_existing_file(params, 'path')
    _require_deps('barcode.decode', missing_deps_decode())
    from processors.utils import load_image
    from processors.barcode import decode_qr
    image = load_image(str(path))
    results = decode_qr(image)
    normalized: list[dict[str, Any]] = []
    for item in results:
        rect = item.get('rect') if isinstance(item, dict) else None
        normalized.append({
            'data': str(item.get('data', '')) if isinstance(item, dict) else '',
            'type': str(item.get('type', '')) if isinstance(item, dict) else '',
            'rect': ({'x': int(getattr(rect, 'x')), 'y': int(getattr(rect, 'y')),
                      'width': int(getattr(rect, 'width')), 'height': int(getattr(rect, 'height'))}
                     if rect is not None else None),
        })
    return {'results': normalized}


# ---- 文本 / 分析小工具 -------------------------------------------------------

def ascii_render(params: dict) -> dict[str, Any]:
    """ascii.render（sync）：图像 → ASCII 字符画文本（processors/ascii.py
    ascii_art）。文本结果直接走 JSON（非像素，不受 §4 大图限制约束）。"""
    path = _require_existing_file(params, 'path')
    cols = _int_in(params, 'cols', 100, 10, 500)
    invert = _require_flag(params, 'invert', False)
    from processors.ascii import ascii_art
    from processors.utils import load_image
    image = load_image(str(path))
    text = ascii_art(image, cols=cols, invert=invert)
    return {'text': text, 'rows': text.count('\n') + 1, 'cols': cols}


def compare_images_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path_a = _require_existing_file(params, 'path_a')
    path_b = _require_existing_file(params, 'path_b')

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(15, '载入图像')
        from processors import compare as compare_processor
        from processors.utils import load_image
        a = load_image(str(path_a))
        cancel_token.raise_if_cancelled()
        b = load_image(str(path_b))
        cancel_token.raise_if_cancelled()
        progress_cb(55, '计算指标')
        metrics = compare_processor.compare(a, b)
        cancel_token.raise_if_cancelled()
        # b 会被资产按 a 的尺寸缩放（compare() 既有行为）；指标形状固定六键。
        return {key: _finite_or_none(value) for key, value in metrics.items()}

    return job


def checksum_file(params: dict) -> dict[str, Any]:
    """checksum.file（sync）：processors/checksum.py file_hashes（七种算法 +
    字节数）。文件不存在/不可读 → FILE_NOT_FOUND。"""
    path = _require_existing_file(params, 'path')
    from processors.checksum import file_hashes
    try:
        hashes = file_hashes(path)
    except OSError as exc:
        raise WorkerError(protocol.ERR_FILE_NOT_FOUND, f'文件无法读取: {exc}') from exc
    return {key: _json_safe(value) for key, value in hashes.items()}


def histogram_compute(params: dict) -> dict[str, Any]:
    """histogram.compute（sync）：mode=rgb {R,G,B}（各 256 bin）/ luma（256
    bin）/ hsv {H(180),S,V}（processors/histogram.py 三个既有函数）。"""
    path = _require_existing_file(params, 'path')
    mode = str(params.get('mode') or 'rgb').lower()
    if mode not in ('rgb', 'luma', 'hsv'):
        raise WorkerError(protocol.ERR_INVALID_PARAMS,
                          f'mode 必须是 rgb/luma/hsv，得到 {mode}')
    from processors import histogram as histogram_processor
    from processors.utils import load_image
    image = load_image(str(path))
    if mode == 'rgb':
        histogram = histogram_processor.histogram_rgb(image)
    elif mode == 'luma':
        histogram = histogram_processor.histogram_luma(image)
    else:
        histogram = histogram_processor.histogram_hsv(image)
    return {'mode': mode, 'histogram': histogram}


def lut_apply_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    cube_path = _require_existing_file(params, 'cube_path')
    from processors import lut as lut_processor
    from processors.utils import load_image
    # cube 解析前移到提交前（文件小、解析廉价）：解析失败 → 提交前
    # INVALID_PARAMS，不产生 task_id（先例同 crop 越界提交前判定）。
    cube = lut_processor.load_lut_from_cube(str(cube_path))
    if cube is None:
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'LUT 文件无法解析: {cube_path}')
    image = load_image(str(path))

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(40, '应用 LUT')
        cancel_token.raise_if_cancelled()
        result = lut_processor.apply_cube_lut(image, cube)
        progress_cb(85, '写入结果文件')
        return _deliver_image(result, temp_dir or '.', 'lut-apply')

    return job


# ---- 媒体（processors/media.py 资产，外部二进制）----------------------------

def media_extract_frames_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    fmt = str(params.get('fmt') or 'png').lower()
    if not _FMT_RE.fullmatch(fmt):
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'fmt 格式非法: {fmt}')
    out_dir = (Path(str(params['output_dir'])).expanduser()
               if isinstance(params.get('output_dir'), str) and params['output_dir'].strip()
               else Path(temp_dir or '.') / 'media-frames')
    _require_deps('media.extract_frames', missing_deps_media(fmt))

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(20, '抽帧')
        cancel_token.raise_if_cancelled()
        from processors.media import extract_frames
        files = extract_frames(str(path), str(out_dir), fmt)
        cancel_token.raise_if_cancelled()
        return {'files': files, 'output_dir': str(out_dir)}

    return job


def media_convert_animation_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    paths = _existing_files_list(params)
    output = _require_output_file(params)
    fmt = str(params.get('fmt') or Path(str(output)).suffix.lstrip('.')).lower()
    if not _FMT_RE.fullmatch(fmt):
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'fmt 格式非法: {fmt}')
    if fmt not in ('gif', 'webp', 'webp_anim', 'apng', 'jxl'):
        raise WorkerError(protocol.ERR_INVALID_PARAMS,
                          f'fmt 必须是 gif/webp/apng/jxl，得到 {fmt}')
    fps = _number_in(params, 'fps', 12.0, 0.1, 120.0)
    _require_deps('media.convert_animation', missing_deps_media(fmt))

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(20, '合成动画')
        cancel_token.raise_if_cancelled()
        from processors.media import convert_animation
        out = convert_animation([str(p) for p in paths], str(output), fmt, fps=fps)
        cancel_token.raise_if_cancelled()
        return {'path': out}

    return job


# ---- EXIF / 水印 / 归档 / 加密 / Base64（processors/parity.py 资产）---------

def exif_extract(params: dict) -> dict[str, Any]:
    """exif.extract（sync）：processors/parity.py extract_exif；返回值经
    _json_safe 归一（bytes → 文本、IFDRational → 字符串）。"""
    path = _require_existing_file(params, 'path')
    from processors.parity import extract_exif
    raw = extract_exif(str(path))
    return {'exif': {str(k): _json_safe(v) for k, v in raw.items()}}


def exif_strip_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    output = _require_output_file(params)

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(30, '去除 EXIF')
        cancel_token.raise_if_cancelled()
        from processors.parity import strip_exif
        out = strip_exif(str(path), str(output))
        cancel_token.raise_if_cancelled()
        return {'path': out}

    return job


def watermark_text_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    output = _require_output_file(params)
    text = params.get('text')
    if not isinstance(text, str) or not text:
        raise WorkerError(protocol.ERR_INVALID_PARAMS, 'text 必须是非空字符串')
    opacity = _number_in(params, 'opacity', 128, 0, 255)
    position = str(params.get('position') or 'bottom-right')
    if position not in _WATERMARK_POSITIONS:
        raise WorkerError(protocol.ERR_INVALID_PARAMS,
                          f'position 必须是 {" / ".join(_WATERMARK_POSITIONS)}，得到 {position}')

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(30, '加水印')
        cancel_token.raise_if_cancelled()
        from processors.parity import watermark
        out = watermark(str(path), str(output), text, opacity=int(opacity), position=position)
        cancel_token.raise_if_cancelled()
        return {'path': out}

    return job


def archive_create_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    paths = _existing_files_list(params)
    output = _require_output_file(params)

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(30, '打包 ZIP')
        cancel_token.raise_if_cancelled()
        from processors.parity import archive_images
        out = archive_images([str(p) for p in paths], str(output))
        cancel_token.raise_if_cancelled()
        return {'path': out}

    return job


def crypto_encrypt_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    return _crypto_job(params, 'crypto.encrypt', 'encrypt_file', '加密')


def crypto_decrypt_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    return _crypto_job(params, 'crypto.decrypt', 'decrypt_file', '解密')


def _crypto_job(params: dict, action: str, fn_name: str, label: str) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    output = _require_output_file(params)
    password = params.get('password')
    if not isinstance(password, str) or not password:
        raise WorkerError(protocol.ERR_INVALID_PARAMS, 'password 必须是非空字符串')
    _require_deps(action, missing_deps_crypto())

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(30, f'文件{label}')
        cancel_token.raise_if_cancelled()
        from processors import parity
        out = getattr(parity, fn_name)(str(path), str(output), password)
        cancel_token.raise_if_cancelled()
        return {'path': out}

    return job


def base64_encode_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    output = _require_output_file(params)

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(30, 'Base64 编码')
        cancel_token.raise_if_cancelled()
        from processors.parity import base64_encode
        out = base64_encode(str(path), str(output))
        cancel_token.raise_if_cancelled()
        return {'path': out}

    return job


def base64_decode_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    output = _require_output_file(params)

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(30, 'Base64 解码')
        cancel_token.raise_if_cancelled()
        from processors.parity import base64_decode
        out = base64_decode(str(path), str(output))
        cancel_token.raise_if_cancelled()
        return {'path': out}

    return job


# ---- AI（processors/ai.py + ai_models.py 资产；重模型默认降级）---------------
# 降级路径（§3.8）：rembg/onnxruntime 模块或模型文件缺失 → 目录置灰 +
# 提交 DEPENDENCY_MISSING；超分优先走配置的 EDSR 模型路径（无外部二进制），
# 未配置时要求 upscayl 二进制 + 系统模型；降噪/色彩化为 OpenCV 核心，恒可用。
# 模型安装/卸载（网络下载）不在本批动作面。

def ai_background_remove_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    model = str(params.get('model') or 'u2net')
    if model not in _BACKGROUND_MODEL_IDS:
        raise WorkerError(protocol.ERR_INVALID_PARAMS,
                          f'未知抠图模型: {model}（可选: {", ".join(_BACKGROUND_MODEL_IDS)}）')
    background = params.get('background')
    bg_color: list[int] | None = None
    if background is not None:
        if (not isinstance(background, list) or len(background) != 3
                or any(isinstance(c, bool) or not isinstance(c, int) or not 0 <= c <= 255
                       for c in background)):
            raise WorkerError(protocol.ERR_INVALID_PARAMS,
                              'background 必须是 [r,g,b]（0-255 整数）数组')
        bg_color = [int(c) for c in background]
    _require_deps('ai.background.remove', missing_deps_ai_background(model))

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(15, 'AI 抠图')
        from processors import ai as ai_processor
        from processors.utils import load_image
        image = load_image(str(path))
        cancel_token.raise_if_cancelled()
        result = ai_processor.remove_background(image, model=model)
        if bg_color is not None:
            cancel_token.raise_if_cancelled()
            result = ai_processor.composite_on_bg(result, tuple(bg_color))
        progress_cb(85, '写入结果文件')
        return _deliver_image(result, temp_dir or '.', 'ai-background-remove')

    return job


def ai_upscale_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    scale = _int_in(params, 'scale', 4, 2, 8)
    explicit = params.get('model_path')
    if explicit is not None and (not isinstance(explicit, str) or not explicit.strip()):
        raise WorkerError(protocol.ERR_INVALID_PARAMS, 'model_path 必须是非空字符串或省略')
    model_path = _configured_model_path(explicit)
    if explicit is not None and not Path(model_path).expanduser().is_file():
        # 显式指定的模型文件缺失是参数错误（用户输入），不是环境依赖缺失。
        raise WorkerError(protocol.ERR_INVALID_PARAMS, f'模型文件不存在: {model_path}')
    _require_deps('ai.upscale', missing_deps_ai_upscale(model_path))
    use_dnn = model_path is not None and Path(model_path).expanduser().is_file()

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(15, 'AI 超分')
        from processors import ai as ai_processor
        from processors.utils import load_image
        image = load_image(str(path))
        cancel_token.raise_if_cancelled()
        if use_dnn:
            result = ai_processor.upscale_sr(image, model_path=model_path, scale=scale)
        else:
            result = ai_processor.upscale_realesrgan(image, scale=scale)
        progress_cb(85, '写入结果文件')
        return _deliver_image(result, temp_dir or '.', 'ai-upscale')

    return job


def ai_denoise_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    strength = _number_in(params, 'strength', 10.0, 0.0, 100.0)

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(15, 'AI 降噪')
        from processors import ai as ai_processor
        from processors.utils import load_image
        image = load_image(str(path))
        cancel_token.raise_if_cancelled()
        result = ai_processor.denoise_nlm(image, strength=strength)
        progress_cb(85, '写入结果文件')
        return _deliver_image(result, temp_dir or '.', 'ai-denoise')

    return job


def ai_colorize_job(params: dict, temp_dir: Path | None = None) -> Callable[..., dict]:
    path = _require_existing_file(params, 'path')
    mode = str(params.get('mode') or 'simple').lower()
    if mode not in ('simple', 'transfer'):
        raise WorkerError(protocol.ERR_INVALID_PARAMS,
                          f'mode 必须是 simple/transfer，得到 {mode}')
    style = str(params.get('style') or 'vintage').lower()
    if mode == 'transfer' and style not in _COLORIZE_STYLES:
        raise WorkerError(protocol.ERR_INVALID_PARAMS,
                          f'style 必须是 {" / ".join(_COLORIZE_STYLES)}，得到 {style}')

    def job(progress_cb, cancel_token) -> dict:
        progress_cb(15, 'AI 色彩化')
        from processors import ai as ai_processor
        from processors.utils import load_image
        image = load_image(str(path))
        cancel_token.raise_if_cancelled()
        if mode == 'transfer':
            result = ai_processor.colorize_transfer(image, style=style)
        else:
            result = ai_processor.colorize_simple(image)
        progress_cb(85, '写入结果文件')
        return _deliver_image(result, temp_dir or '.', 'ai-colorize')

    return job


# ai.models.list 的 task 过滤词汇：ai_models.MODEL_REGISTRY 的 task 为中文
# （抠图/超分）；接受 ai.py AI_MODEL_REGISTRY 的英文 id 作别名。
_AI_TASK_ALIASES = {'background-removal': '抠图', 'upscale': '超分', '抠图': '抠图', '超分': '超分'}


def ai_models_list(params: dict) -> dict[str, Any]:
    """ai.models.list（sync）：模型注册表（processors/ai_models.py registry，
    installed/size 为真实文件探测结果——无模型文件即 installed=false，不谎报）
    + 推理后端探测 + 模型路径配置只读视图。本动作不下载、不安装、不删除。"""
    task = params.get('task')
    if task is not None:
        if not isinstance(task, str) or not task.strip():
            raise WorkerError(protocol.ERR_INVALID_PARAMS, 'task 必须是非空字符串或省略')
        task = _AI_TASK_ALIASES.get(task.strip(), task.strip())
    from processors import ai_models
    models = [m for m in ai_models.registry() if task is None or m['task'] == task]
    return {
        'models': models,
        'backends': ai_models.detect_backends(),
        'cache_root': str(ai_models.CACHE_ROOT),
        'model_paths': model_path_config(),
    }
