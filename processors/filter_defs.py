from __future__ import annotations

import functools
import inspect
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import numpy as np


class FilterCategory(str, Enum):
    BLUR = "blur"
    COLOR = "color"
    DISTORTION = "distortion"
    EDGE = "edge"
    NOISE = "noise"
    SHARPEN = "sharpen"
    STYLIZE = "stylize"
    GEOMETRY = "geometry"
    LIGHTING = "lighting"
    TEXTURE = "texture"
    ARTISTIC = "artistic"
    FRACTAL = "fractal"
    OTHER = "other"


CATEGORY_LABELS = {
    FilterCategory.BLUR: "模糊",
    FilterCategory.COLOR: "色彩",
    FilterCategory.DISTORTION: "变形",
    FilterCategory.EDGE: "边缘",
    FilterCategory.NOISE: "噪声",
    FilterCategory.SHARPEN: "锐化",
    FilterCategory.STYLIZE: "风格化",
    FilterCategory.GEOMETRY: "几何",
    FilterCategory.LIGHTING: "光影",
    FilterCategory.TEXTURE: "纹理",
    FilterCategory.ARTISTIC: "艺术",
    FilterCategory.FRACTAL: "分形",
    FilterCategory.OTHER: "其他",
}


PARAM_TYPE_INT = "int"
PARAM_TYPE_FLOAT = "float"
PARAM_TYPE_BOOL = "bool"
PARAM_TYPE_ENUM = "enum"
PARAM_TYPE_COLOR = "color"
PARAM_TYPE_STRING = "string"

_VALID_TYPES = {
    PARAM_TYPE_INT, PARAM_TYPE_FLOAT, PARAM_TYPE_BOOL,
    PARAM_TYPE_ENUM, PARAM_TYPE_COLOR, PARAM_TYPE_STRING,
}


@dataclass
class FilterParam:
    name: str
    label: str
    type: str = PARAM_TYPE_FLOAT
    default: Any = 0.0
    minimum: float | int | None = None
    maximum: float | int | None = None
    step: float | int = 1
    choices: list[str] | dict[str, Any] | None = None
    description: str = ""

    def __post_init__(self):
        if self.type not in _VALID_TYPES:
            raise ValueError(f"Unknown param type: {self.type}")
        if self.type == PARAM_TYPE_ENUM and not self.choices:
            raise ValueError(f"Enum param '{self.name}' requires choices")
        if self.type == PARAM_TYPE_BOOL:
            if self.default is None:
                self.default = False
            self.minimum = None
            self.maximum = None
            self.step = 1
        if self.type == PARAM_TYPE_STRING:
            self.minimum = None
            self.maximum = None
            self.step = 1
        if self.type in (PARAM_TYPE_INT, PARAM_TYPE_FLOAT):
            if self.default is None:
                self.default = 0 if self.type == PARAM_TYPE_INT else 0.0

    def validate(self, value: Any) -> tuple[bool, str]:
        if self.type == PARAM_TYPE_BOOL:
            return isinstance(value, bool) or isinstance(value, (int, float)), f"'{self.label}' must be bool"
        if self.type == PARAM_TYPE_INT:
            try:
                v = int(value)
            except (TypeError, ValueError):
                return False, f"'{self.label}' must be int"
            if self.minimum is not None and v < int(self.minimum):
                return False, f"'{self.label}' must be >= {int(self.minimum)}"
            if self.maximum is not None and v > int(self.maximum):
                return False, f"'{self.label}' must be <= {int(self.maximum)}"
            return True, ""
        if self.type == PARAM_TYPE_FLOAT:
            try:
                v = float(value)
            except (TypeError, ValueError):
                return False, f"'{self.label}' must be float"
            if self.minimum is not None and v < float(self.minimum):
                return False, f"'{self.label}' must be >= {float(self.minimum)}"
            if self.maximum is not None and v > float(self.maximum):
                return False, f"'{self.label}' must be <= {float(self.maximum)}"
            return True, ""
        if self.type == PARAM_TYPE_ENUM:
            if self.choices is None:
                return True, ""
            if isinstance(self.choices, dict):
                valid = list(self.choices.keys())
            else:
                valid = list(self.choices)
            if value not in valid:
                return False, f"'{self.label}' must be one of {valid}"
            return True, ""
        if self.type == PARAM_TYPE_COLOR:
            return self._validate_color(value)
        if self.type == PARAM_TYPE_STRING:
            return isinstance(value, str), f"'{self.label}' must be string"
        return False, f"Unknown type: {self.type}"

    def _validate_color(self, value: Any) -> tuple[bool, str]:
        if isinstance(value, (tuple, list)):
            if len(value) >= 3 and all(isinstance(c, (int, np.integer)) and 0 <= int(c) <= 255 for c in value[:3]):
                return True, ""
            return False, f"'{self.label}' color tuple must be (r,g,b) 0-255"
        if isinstance(value, str):
            if re.match(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$", value):
                return True, ""
            return False, f"'{self.label}' must be #RGB/#RRGGBB/#RRGGBBAA"
        return False, f"'{self.label}' invalid color format"


@functools.lru_cache(maxsize=512)
def _accepted_kwargs(processor: Callable) -> frozenset[str] | None:
    """Keyword names `processor` accepts, or None if it takes **kwargs.

    Used to filter the parameter dict instead of probing by catching TypeError,
    which could not be told apart from a TypeError raised *inside* a processor.
    """
    try:
        sig = inspect.signature(processor)
    except (TypeError, ValueError):
        return frozenset()
    names: set[str] = set()
    for name, p in sig.parameters.items():
        if p.kind is inspect.Parameter.VAR_KEYWORD:
            return None
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
            names.add(name)
    return frozenset(names)


@dataclass
class FilterDef:
    key: str
    display_name: str
    processor: Callable[..., np.ndarray]
    category: FilterCategory = FilterCategory.OTHER
    params: list[FilterParam] = field(default_factory=list)
    description: str = ""
    preview_supported: bool = True
    batch_supported: bool = True
    optional_deps: list[str] = field(default_factory=list)
    version: str = "1.0"

    def default_params(self) -> dict[str, Any]:
        return {p.name: p.default for p in self.params}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
        errors: list[str] = []
        merged = self.default_params()
        if params:
            merged.update(params)
        for p in self.params:
            if p.name not in merged:
                errors.append(f"Missing required param: {p.label}")
                continue
            ok, msg = p.validate(merged[p.name])
            if not ok:
                errors.append(msg)
        return (len(errors) == 0), errors, merged

    def apply(self, image: np.ndarray, params: dict[str, Any] | None = None,
              cancel_token: Any | None = None) -> np.ndarray:
        ok, errors, merged = self.validate_params(params or {})
        if not ok:
            raise ValueError("; ".join(errors))
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()
        accepted = _accepted_kwargs(self.processor)
        if accepted is None:
            call_kwargs = dict(merged)
        else:
            # Keep only params the processor's signature actually accepts.
            call_kwargs = {k: v for k, v in merged.items() if k in accepted}
        if cancel_token is not None and accepted is not None and "cancel_token" in accepted:
            # Let long-running processors honour cancellation cooperatively.
            call_kwargs["cancel_token"] = cancel_token
        return self.processor(image, **call_kwargs) if call_kwargs else self.processor(image)

    def param(self, name: str) -> FilterParam | None:
        for p in self.params:
            if p.name == name:
                return p
        return None


class FilterDefRegistry:
    _instance: FilterDefRegistry | None = None

    def __init__(self) -> None:
        self._defs: dict[str, FilterDef] = {}

    @classmethod
    def instance(cls) -> FilterDefRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, defn: FilterDef) -> FilterDef:
        self._defs[defn.key] = defn
        return defn

    def unregister(self, key: str) -> bool:
        """Remove a registration; returns True when something was removed."""
        return self._defs.pop(key, None) is not None

    def get(self, key: str) -> FilterDef | None:
        return self._defs.get(key)

    def has(self, key: str) -> bool:
        return key in self._defs

    def all(self) -> dict[str, FilterDef]:
        return dict(self._defs)

    def keys(self) -> list[str]:
        return list(self._defs.keys())

    def by_category(self) -> dict[FilterCategory, list[FilterDef]]:
        grouped: dict[FilterCategory, list[FilterDef]] = {}
        for d in self._defs.values():
            grouped.setdefault(d.category, []).append(d)
        return grouped

    def __contains__(self, key: str) -> bool:
        return key in self._defs

    def __getitem__(self, key: str) -> FilterDef:
        return self._defs[key]

    def __len__(self) -> int:
        return len(self._defs)


def register_filter(
    key: str,
    display_name: str,
    processor: Callable[..., np.ndarray],
    category: FilterCategory = FilterCategory.OTHER,
    params: list[FilterParam] | None = None,
    description: str = "",
    preview_supported: bool = True,
    batch_supported: bool = True,
    optional_deps: list[str] | None = None,
) -> FilterDef:
    defn = FilterDef(
        key=key,
        display_name=display_name,
        processor=processor,
        category=category,
        params=params or [],
        description=description,
        preview_supported=preview_supported,
        batch_supported=batch_supported,
        optional_deps=optional_deps or [],
    )
    FilterDefRegistry.instance().register(defn)
    return defn


def _infer_params_from_signature(func: Callable) -> list[FilterParam]:
    sig = inspect.signature(func)
    params: list[FilterParam] = []
    for name, p in sig.parameters.items():
        if name in ("img", "image", "src", "cancel_token"):
            continue
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        annotation = p.annotation if p.annotation is not inspect.Parameter.empty else None
        default = p.default if p.default is not inspect.Parameter.empty else None
        if annotation is bool or default is False or default is True:
            params.append(FilterParam(name=name, label=name, type=PARAM_TYPE_BOOL,
                                      default=bool(default) if default is not None else False))
        elif annotation is int:
            lo = max(0, int(default) - 255) if default is not None else 0
            hi = int(default) + 255 if default is not None else 255
            params.append(FilterParam(name=name, label=name, type=PARAM_TYPE_INT,
                                      default=int(default) if default is not None else 0,
                                      minimum=lo, maximum=hi, step=1))
        elif annotation is float:
            params.append(FilterParam(name=name, label=name, type=PARAM_TYPE_FLOAT,
                                      default=float(default) if default is not None else 0.0,
                                      minimum=0.0, maximum=2.0, step=0.01))
        elif isinstance(default, bool):
            params.append(FilterParam(name=name, label=name, type=PARAM_TYPE_BOOL, default=default))
        elif isinstance(default, int):
            params.append(FilterParam(name=name, label=name, type=PARAM_TYPE_INT,
                                      default=default, minimum=0, maximum=max(255, default * 3), step=1))
        elif isinstance(default, float):
            params.append(FilterParam(name=name, label=name, type=PARAM_TYPE_FLOAT,
                                      default=default, minimum=0.0, maximum=max(2.0, default * 3), step=0.01))
    return params


def register_legacy_filters(legacy_registry: dict[str, tuple[str, Callable]]) -> int:
    reg = FilterDefRegistry.instance()
    count = 0
    for key, (zh_name, func) in legacy_registry.items():
        if reg.has(key):
            continue
        inferred = _infer_params_from_signature(func)
        cat = _guess_category(key, zh_name)
        reg.register(FilterDef(
            key=key,
            display_name=zh_name,
            processor=func,
            category=cat,
            params=inferred,
            description=f"Legacy filter: {zh_name}",
        ))
        count += 1
    return count


_KEYWORD_CATEGORIES: list[tuple[FilterCategory, list[str]]] = [
    (FilterCategory.BLUR, ["blur", "模糊", "gaussian", "box", "median", "bilateral", "motion", "zoom", "sh blur", "stack", "tent", "poisson", "lens", "radial_tilt", "tilt", "nativestack", "enhancedzoomblur"]),
    (FilterCategory.COLOR, ["color", "颜色", "brightness", "亮度", "contrast", "对比度", "saturation", "饱和度", "hue", "色相", "gamma", "曝光", "exposure", "white_balance", "白平衡", "false_color", "伪彩色", "monochrome", "sepia", "vintage", "复古", "warm", "cool", "night_vision", "夜视", "grayscale", "灰度", "black_and_white", "bw", "invert", "反色", "solarize", "posterize", "色调分离", "equalize", "histogram", "clahe", "dehaze", "去雾", "haze", "雾化"]),
    (FilterCategory.DISTORTION, ["distort", "变形", "bulge", "鼓胀", "pinch", "收缩", "wave", "波浪", "swirl", "漩涡", "twirl", "扭转", "fish_eye", "鱼眼", "glass_sphere", "玻璃球", "mosaic", "crystallize", "结晶", "kaleidoscope", "万花筒", "mirror", "arc", "shear", "polar", "vortex", "ripple"]),
    (FilterCategory.EDGE, ["edge", "边缘", "sobel", "laplacian", "canny", "nonmaximum", "sketch", "素描", "contour", "轮廓", "emboss", "浮雕"]),
    (FilterCategory.NOISE, ["noise", "噪声", "grain", "颗粒", "dither", "抖动", "film_grain", "halftone", "半色调"]),
    (FilterCategory.SHARPEN, ["sharpen", "锐化", "unsharp", "usm", "highpass"]),
    (FilterCategory.STYLIZE, ["stylize", "风格", "oil_paint", "油画", "water_color", "水彩", "toon", "卡通", "neon", "霓虹", "old_tv", "电视", "crt", "bloom", "泛光", "glow", "光晕", "hdr", "glitch", "故障", "anaglyph", "立体", "vignette", "虚化", "lomo", "宝丽来", "polaroid", "crosshatch", "engrave", "pastel"]),
    (FilterCategory.GEOMETRY, ["geometry", "resize", "rotate", "flip", "crop", "scale", "perspective", "warp"]),
    (FilterCategory.LIGHTING, ["lighting", "光", "light", "shadow", "shadow", "rays", "flare", "sun", "vignette_blur", "drop_shadow"]),
    (FilterCategory.TEXTURE, ["texture", "纹理", "metal", "wood", "brushed", "leather", "bokeh", "dust", "划痕", "scratches", "dust_scratches"]),
    (FilterCategory.ARTISTIC, ["artistic", "艺术", "cyberpunk", "赛博朋克", "coda_chrome", "night_magic", "rainbow", "彩虹", "browni", "protonomaly", "色盲", "anomaly"]),
]


def _guess_category(key: str, zh_name: str = "") -> FilterCategory:
    hay = (key + " " + zh_name).lower().replace("_", " ")
    for cat, keywords in _KEYWORD_CATEGORIES:
        for kw in keywords:
            if kw in hay:
                return cat
    return FilterCategory.OTHER


ALL_FILTERS_COMPAT: dict[str, tuple[str, Callable]] = {}


def build_legacy_compat_layer() -> None:
    reg = FilterDefRegistry.instance()
    ALL_FILTERS_COMPAT.clear()
    for key, defn in reg.all().items():
        def _make_callable(d: FilterDef):
            def _call(img: np.ndarray, **kwargs) -> np.ndarray:
                return d.apply(img, kwargs if kwargs else None)
            return _call
        ALL_FILTERS_COMPAT[key] = (defn.display_name, _make_callable(defn))
