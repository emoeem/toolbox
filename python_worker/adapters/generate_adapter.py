"""生成器适配：fractal / texture_studio / gradients / shader_studio 的协议化
（Phase 6C，docs/ipc-protocol.md §3.7）。

模式对齐 filter_adapter.list_filters：注册表来自 processors 各生成器既有实现
的元信息（processors/fractal.py 公式表、processors/texture_studio/presets.py
预设表、processors/gradients.py 预设），本层只做协议化与接线，不重写任何
生成算法（1.0 资产复用规则，总纲 §15.5）。

- generate.list（sync）→ {generators: [...]}：与 filter.list 同构的目录条目，
  C++ GeneratorModel.reloadFrom 按 key/name/category(_label)/params/available/
  optional_deps 消费（native/models/generator_model.cpp）。
- generate.render（async）任务体：渲染 → filter_adapter.write_preview 的
  §4 临时 PNG 通道交付（不 Base64，docs/ipc-protocol.md §4）。

参数定义复用 processors/filter_defs.py FilterParam（含 validate），颜色等
类型校验与 filter.list 的参数描述同一词汇（int/float/bool/enum/color）。
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Callable

import numpy as np

from processors import fractal as fractal_processor
from processors import gmic as gmic_processor
from processors import gradients
from processors.filter_defs import (
    PARAM_TYPE_BOOL,
    PARAM_TYPE_COLOR,
    PARAM_TYPE_ENUM,
    PARAM_TYPE_FLOAT,
    PARAM_TYPE_INT,
    FilterParam,
)
from processors.texture_studio import generators as texture_generators
from processors.texture_studio.noise import GENERATORS as NOISE_GENERATORS
from processors.texture_studio.presets import BUILTIN_PRESETS as TEXTURE_PRESETS
from processors.texture_studio.presets import GMIC_DEFAULTS
from processors.texture_studio.raymarch import RAYMARCH_DEFAULTS as RAYMARCH_PARAM_DEFAULTS

from . import filter_adapter
from .image_adapter import WorkerError

# generate.render 的渲染上限：与 FractalParams.validate 的 4096 上限一致，
# 对全部生成器统一生效（内存保护；提交前同步拒绝）。
MAX_RENDER_SIDE = 4096

GENERATOR_CATEGORY_LABELS = {
    'fractal': '分形',
    'texture': '纹理',
    'gradient': '渐变',
    'shader': '着色器',
}

_REGISTRY: dict[str, dict] | None = None


def reset_registry_cache() -> None:
    """重建注册表（测试钩子）：gmic / glslangValidator 可用性在构建时探测并
    固化到条目上，依赖环境变化后需重置再按当前环境重建。"""
    global _REGISTRY
    _REGISTRY = None


# ---- 注册表构建（元信息全部取自 processors 既有资产）------------------------

def _entry(key: str, name: str, category: str, params: list[FilterParam],
           description: str, available: bool = True,
           optional_deps: list[str] | None = None,
           extra_defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    defaults: dict[str, Any] = {p.name: p.default for p in params}
    if extra_defaults:
        defaults.update(extra_defaults)
    return {
        'key': key,
        'name': name,
        'category': category,
        'description': description,
        'available': available,
        'optional_deps': list(optional_deps or []),
        'params': params,
        'defaults': defaults,
    }


def _list(value) -> list:
    return list(value)


def _fractal_2d_entry(formula: str) -> dict[str, Any]:
    """fractal:<formula> 条目——参数集与 fractal.register_fractal_filters
    （processors/fractal.py:792）的 can_power/can_bailout/can_julia/
    can_phoenix/can_nova 裁剪逻辑一致。"""
    info = fractal_processor.formula_info(formula)
    zh = info['zh_name']
    params: list[FilterParam] = [
        FilterParam('cx', '中心 X', PARAM_TYPE_FLOAT, -0.5, -10.0, 10.0, 0.01),
        FilterParam('cy', '中心 Y', PARAM_TYPE_FLOAT, 0.0, -10.0, 10.0, 0.01),
        FilterParam('scale', '缩放范围', PARAM_TYPE_FLOAT, 3.0, 0.01, 100.0, 0.01),
    ]
    if info['can_power']:
        params.append(FilterParam('power', '幂次 (power)', PARAM_TYPE_FLOAT,
                                  info['default_power'], 1.0, 10.0, 0.1))
    params.append(FilterParam('iterations', '迭代次数', PARAM_TYPE_INT, 256, 10, 2048, 10))
    if info['can_bailout']:
        params.append(FilterParam('bailout', '逃逸半径 (bailout)', PARAM_TYPE_FLOAT,
                                  2.0, 1.0, 1000.0, 0.1))
    params.append(FilterParam('coloring', '着色模式', PARAM_TYPE_ENUM, 'smooth', None, None, 1,
                              choices=['smooth', 'banded', 'grayscale']))
    if info['can_julia']:
        params.append(FilterParam('julia_c_x', 'Julia 常数 Re', PARAM_TYPE_FLOAT,
                                  -0.8, -10.0, 10.0, 0.01))
        params.append(FilterParam('julia_c_y', 'Julia 常数 Im', PARAM_TYPE_FLOAT,
                                  0.156, -10.0, 10.0, 0.01))
    if info['can_phoenix']:
        params.append(FilterParam('phoenix_c_x', 'Phoenix 常数 Re', PARAM_TYPE_FLOAT,
                                  -0.5, -10.0, 10.0, 0.01))
        params.append(FilterParam('phoenix_c_y', 'Phoenix 常数 Im', PARAM_TYPE_FLOAT,
                                  0.0, -10.0, 10.0, 0.01))
    if info['can_nova']:
        params.append(FilterParam('nova_relaxation', 'Nova 松弛系数', PARAM_TYPE_FLOAT,
                                  1.0, 0.0, 5.0, 0.01))
    return _entry(f'fractal:{formula}', f'分形 · {zh}', 'fractal', params,
                  f'2D {zh} 分形生成（processors/fractal.py formula={formula}）')


def _texture_entries() -> list[dict[str, Any]]:
    """texture:* 条目——缺省参数取自 texture_studio.presets.BUILTIN_PRESETS
    按生成器 id 建立的元信息表；G'MIC 系按 CLI 实际可用性如实置灰
    （ui-page-spec.md：G'MIC 缺失时该生成器置灰）。"""
    entries: list[dict[str, Any]] = []
    preset_names: dict[str, str] = {}
    preset_params: dict[str, dict] = {}
    for preset in TEXTURE_PRESETS:
        preset_names.setdefault(preset.generator_id, preset.name)
        preset_params.setdefault(preset.generator_id, dict(preset.params))

    # 噪声（processors/texture_studio/noise.py GENERATORS）
    for gid in sorted(NOISE_GENERATORS):
        d = preset_params.get(gid, {})
        params = [
            FilterParam('scale', '尺度', PARAM_TYPE_INT, int(d.get('scale', 48)), 1, 512, 1),
            FilterParam('octaves', '倍频数', PARAM_TYPE_INT, int(d.get('octaves', 4)), 1, 8, 1),
            FilterParam('persistence', '持久度', PARAM_TYPE_FLOAT,
                        float(d.get('persistence', 0.5)), 0.05, 1.0, 0.01),
            FilterParam('lacunarity', '频率倍率', PARAM_TYPE_FLOAT,
                        float(d.get('lacunarity', 2.0)), 1.1, 4.0, 0.1),
            FilterParam('seed', '随机种子', PARAM_TYPE_INT, int(d.get('seed', 42)), 0, 999999, 1),
            FilterParam('warp', '扰动', PARAM_TYPE_FLOAT, float(d.get('warp', 0)), 0, 256, 1),
            FilterParam('contrast', '对比度', PARAM_TYPE_FLOAT,
                        float(d.get('contrast', 1.0)), 0.1, 4.0, 0.05),
            FilterParam('brightness', '亮度', PARAM_TYPE_FLOAT,
                        float(d.get('brightness', 0.0)), -1.0, 1.0, 0.01),
        ]
        entries.append(_entry(
            f'texture:{gid}', f"纹理 · {preset_names.get(gid, gid)}", 'texture', params,
            f'{gid} 噪声纹理（processors/texture_studio/noise.py GENERATORS）'))

    # 图案（processors/texture_studio/pattern.py；grid 走 pattern() 的兜底分支）
    for kind in ('stripes', 'rings', 'checker', 'dots', 'grid'):
        gid = f'pattern:{kind}'
        d = preset_params.get(gid, {})
        params = [
            FilterParam('size', '图元尺寸', PARAM_TYPE_FLOAT, float(d.get('size', 32)), 2, 512, 1),
            FilterParam('spacing', '间距', PARAM_TYPE_FLOAT, float(d.get('spacing', 8)), 0, 256, 1),
            FilterParam('angle', '角度', PARAM_TYPE_FLOAT, float(d.get('angle', 0)), 0, 360, 1),
            FilterParam('color_a', '前景色 A', PARAM_TYPE_COLOR, _list(d.get('color_a', (35, 35, 45)))),
            FilterParam('color_b', '前景色 B', PARAM_TYPE_COLOR, _list(d.get('color_b', (210, 210, 220)))),
            FilterParam('background', '背景色', PARAM_TYPE_COLOR, _list(d.get('background', (20, 20, 25)))),
            FilterParam('anti_alias', '抗锯齿', PARAM_TYPE_BOOL, bool(d.get('anti_alias', True))),
        ]
        entries.append(_entry(
            f'texture:{gid}', f"纹理 · {preset_names.get(gid, kind.title())}", 'texture', params,
            f'{kind} 图案纹理（processors/texture_studio/pattern.py）'))

    # G'MIC 纹理（processors/texture_studio/gmic.py）：CLI 缺失时 available=False
    # 置灰（§9.7）。blend_mode 是 1.0 元信息中渲染路径未消费的键，不进参数表。
    for n in ('paper', 'canvas', 'grunge', 'noise_blend'):
        gid = f'gmic:{n}'
        d = preset_params.get(gid, GMIC_DEFAULTS)
        params = [
            FilterParam('intensity', '强度', PARAM_TYPE_FLOAT, float(d.get('intensity', 25)), 0, 100, 1),
            FilterParam('grain_size', '颗粒尺寸', PARAM_TYPE_FLOAT,
                        float(d.get('grain_size', 3)), 0.5, 64, 0.5),
            FilterParam('seed', '随机种子', PARAM_TYPE_INT, int(d.get('seed', 42)), 0, 999999, 1),
            FilterParam('contrast', '对比度', PARAM_TYPE_FLOAT,
                        float(d.get('contrast', 1.0)), 0.1, 4.0, 0.05),
            FilterParam('brightness', '亮度', PARAM_TYPE_FLOAT,
                        float(d.get('brightness', 0.0)), -1.0, 1.0, 0.01),
            FilterParam('color_tint', '着色', PARAM_TYPE_COLOR, _list(d.get('color_tint', (220, 205, 180, 255)))),
        ]
        gmic_ok = gmic_processor.available()
        entries.append(_entry(
            f'texture:{gid}', f"纹理 · {preset_names.get(gid, n.title())}", 'texture', params,
            f"G'MIC 纹理 {n}（processors/texture_studio/gmic.py；CLI 缺失时置灰）",
            available=gmic_ok, optional_deps=[] if gmic_ok else ['gmic']))

    # SDF 光线步进（processors/texture_studio/raymarch.py）。light_direction 为
    # vec3、无对应参数类型，不进参数表（仍经 RAYMARCH_DEFAULTS 透传到渲染）。
    d = dict(RAYMARCH_PARAM_DEFAULTS)
    params = [
        FilterParam('steps', '步数', PARAM_TYPE_INT, int(d['steps']), 8, 256, 1),
        FilterParam('max_distance', '最大步进距离', PARAM_TYPE_FLOAT, float(d['max_distance']), 1.0, 20.0, 0.1),
        FilterParam('surface_threshold', '表面阈值', PARAM_TYPE_FLOAT,
                    float(d['surface_threshold']), 0.0002, 0.05, 0.0001),
        FilterParam('ambient', '环境光', PARAM_TYPE_FLOAT, float(d['ambient']), 0.0, 1.0, 0.01),
        FilterParam('diffuse', '漫反射', PARAM_TYPE_FLOAT, float(d['diffuse']), 0.0, 2.0, 0.01),
        FilterParam('specular', '高光', PARAM_TYPE_FLOAT, float(d['specular']), 0.0, 2.0, 0.01),
        FilterParam('fresnel', '菲涅尔', PARAM_TYPE_FLOAT, float(d['fresnel']), 0.0, 1.0, 0.01),
        FilterParam('gradient', '背景渐变', PARAM_TYPE_FLOAT, float(d['gradient']), 0.0, 1.0, 0.01),
        FilterParam('color_a', '表面色 A', PARAM_TYPE_COLOR, _list(d['color_a'])),
        FilterParam('color_b', '表面色 B', PARAM_TYPE_COLOR, _list(d['color_b'])),
        FilterParam('background', '背景色', PARAM_TYPE_COLOR, _list(d['background'])),
        FilterParam('seed', '随机种子', PARAM_TYPE_INT, int(d['seed']), 0, 999999, 1),
    ]
    entries.append(_entry(
        'texture:raymarch:orb', '纹理 · Raymarch Orb', 'texture', params,
        'CPU SDF 光线步进纹理（processors/texture_studio/raymarch.py）'))
    return entries


def _gradient_entries() -> list[dict[str, Any]]:
    return [
        _entry('gradient:linear', '渐变 · 线性', 'gradient', [
            FilterParam('color_a', '起始色', PARAM_TYPE_COLOR, [255, 0, 128]),
            FilterParam('color_b', '结束色', PARAM_TYPE_COLOR, [0, 255, 255]),
            FilterParam('angle', '角度', PARAM_TYPE_FLOAT, 0.0, 0.0, 360.0, 1.0),
        ], '线性双色渐变（processors/gradients.py linear_gradient）'),
        _entry('gradient:radial', '渐变 · 径向', 'gradient', [
            FilterParam('color_a', '中心色', PARAM_TYPE_COLOR, [255, 0, 128]),
            FilterParam('color_b', '边缘色', PARAM_TYPE_COLOR, [0, 255, 255]),
            FilterParam('cx', '中心 X', PARAM_TYPE_FLOAT, 0.5, 0.0, 1.0, 0.01),
            FilterParam('cy', '中心 Y', PARAM_TYPE_FLOAT, 0.5, 0.0, 1.0, 0.01),
        ], '径向双色渐变（processors/gradients.py radial_gradient）'),
        _entry('gradient:mesh', '渐变 · 网格', 'gradient', [
            FilterParam('preset', '预设', PARAM_TYPE_ENUM, 'piretti', None, None, 1,
                        choices=['piretti', 'sunset', 'ocean']),
        ], '网格渐变预设（processors/gradients.py MESH_PRESETS）'),
    ]


def _shader_entries() -> list[dict[str, Any]]:
    """shader:preview 恒为 available=False（优雅降级，Phase 6C 任务要求）：
    Worker 进程没有 OpenGL 运行时（1.0 的着色器渲染发生在 Qt/GL 侧）；
    glslangValidator 是 processors/shader_studio/validator.py 的外部校验依赖，
    缺失时一并列入 optional_deps（置灰原因如实、不虚构可用状态）。"""
    deps = ['opengl']
    if shutil.which('glslangValidator') is None:
        deps.append('glslangValidator')
    return [_entry(
        'shader:preview', '着色器 · GLSL 预览', 'shader', [],
        'GLSL 片段着色器预览渲染（Worker 无 OpenGL 运行时，恒不可用；'
        'processors/shader_studio/validator.py 依赖外部 glslangValidator）',
        available=False, optional_deps=deps)]


def _build_registry() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    # 分形 2D（processors/fractal.py _2D_FORMULAS 的全部公式）
    for formula in fractal_processor.formula_keys():
        entries.append(_fractal_2d_entry(formula))
    # 分形 3D（processors/fractal.py render_mandelbulb）
    entries.append(_entry(
        'fractal:mandelbulb', '分形 · Mandelbulb (3D)', 'fractal', [
            FilterParam('power', '幂次 (power)', PARAM_TYPE_FLOAT, 8.0, 1.0, 10.0, 0.1),
            FilterParam('iterations', '迭代次数', PARAM_TYPE_INT, 64, 1, 1000, 1),
        ], '3D Mandelbulb 光线步进渲染（processors/fractal.py render_mandelbulb）'))
    entries.extend(_texture_entries())
    entries.extend(_gradient_entries())
    entries.extend(_shader_entries())
    return entries


def _registry() -> dict[str, dict[str, Any]]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = {entry['key']: entry for entry in _build_registry()}
    return _REGISTRY


# ---- generate.list（docs/ipc-protocol.md §3.7）------------------------------

def _param_to_dict(param: FilterParam) -> dict[str, Any]:
    """参数描述形状与 filter.list 的参数元素一致（filter_adapter._param_to_dict）。"""
    return {
        'name': param.name,
        'label': param.label,
        'type': param.type,
        'default': param.default,
        'minimum': param.minimum,
        'maximum': param.maximum,
        'step': param.step,
        'choices': param.choices,
        'description': param.description,
    }


def list_generators() -> list[dict[str, Any]]:
    """generate.list：与 filter.list 同构的生成器目录（排序规则同款）。"""
    items: list[dict[str, Any]] = []
    for entry in _registry().values():
        items.append({
            'key': entry['key'],
            'name': entry['name'],
            'category': entry['category'],
            'category_label': GENERATOR_CATEGORY_LABELS.get(entry['category'], entry['category']),
            'description': entry['description'],
            'available': entry['available'],
            'optional_deps': list(entry['optional_deps']),
            'params': [_param_to_dict(p) for p in entry['params']],
        })
    items.sort(key=lambda item: (item['category'], item['name']))
    return items


# ---- generate.render（docs/ipc-protocol.md §3.7）----------------------------

_HEX_COLOR = re.compile(r'#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})')


def _hex_to_rgb(value: str) -> tuple[int, ...]:
    text = value.strip()
    if _HEX_COLOR.fullmatch(text):
        digits = text[1:]
        if len(digits) == 3:
            digits = ''.join(c * 2 for c in digits)
        return tuple(int(digits[i:i + 2], 16) for i in range(0, len(digits), 2))
    raise WorkerError('INVALID_PARAMS', f'颜色格式非法: {value}（须为 [r,g,b] 或 #RGB/#RRGGBB）')


def _coerce_color(value: Any, label: str) -> tuple[int, ...] | list[int]:
    """渲染侧颜色统一为整数元组/列表（processors 各实现按 np.array 消费，
    不接受 hex 字符串）。"""
    if isinstance(value, str):
        return _hex_to_rgb(value)
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return list(value)
    raise WorkerError('INVALID_PARAMS', f'{label} 颜色非法: {value!r}')


def _require_side(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (
            isinstance(value, float) and not float(value).is_integer()):
        raise WorkerError('INVALID_PARAMS', f'{label} 必须是整数')
    side = int(value)
    if not 1 <= side <= MAX_RENDER_SIDE:
        raise WorkerError('INVALID_PARAMS', f'{label} 必须 1..{MAX_RENDER_SIDE}，得到 {side}')
    return side


def _build_fractal_params(formula: str, width: int, height: int,
                          merged: dict[str, Any]):
    """协议参数 → processors/fractal.py FractalParams（与 _make_processor 的
    裁剪逻辑一致：不支持的参数回落公式缺省）。"""
    info = fractal_processor.formula_info(formula)
    if info is None:
        raise ValueError(f'未知分形公式: {formula}')
    return fractal_processor.FractalParams(
        width=int(width), height=int(height),
        cx=float(merged.get('cx', -0.5)),
        cy=float(merged.get('cy', 0.0)),
        scale=float(merged.get('scale', 3.0)),
        power=(float(merged.get('power', info['default_power']))
               if info['can_power'] else info['default_power']),
        iterations=int(merged.get('iterations', 256)),
        bailout=float(merged.get('bailout', 2.0)) if info['can_bailout'] else 2.0,
        coloring=fractal_processor.FractalColoring(str(merged.get('coloring', 'smooth'))),
        julia_c=fractal_processor.JuliaConstant(
            real=float(merged.get('julia_c_x', -0.8)),
            imag=float(merged.get('julia_c_y', 0.156))),
        phoenix_c=fractal_processor.PhoenixConstant(
            real=float(merged.get('phoenix_c_x', -0.5)),
            imag=float(merged.get('phoenix_c_y', 0.0))),
        nova_relaxation=float(merged.get('nova_relaxation', 1.0)),
    )


def prepare_render(key: str, width: int, height: int,
                   user_params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """提交前校验与参数装配（非法 → INVALID_PARAMS，不产生 task_id）。

    - 未知 / 不可用生成器（optional_deps 未满足）→ 同步拒绝；
    - 协议参数逐项经 FilterParam.validate（1.0 资产，含 int/float/enum/color
      取值域），值域错误在提交前报出；
    - 分形参数经 FractalParams.validate 同步校验（与提交前判定的既有先例
      image.transform crop 越界检查同一口径）。
    """
    entry = _registry().get(key)
    if entry is None:
        raise WorkerError('INVALID_PARAMS', f'未知生成器: {key}')
    if not entry['available']:
        raise WorkerError(
            'INVALID_PARAMS',
            f'生成器不可用: {key}（缺少可选依赖: {", ".join(entry["optional_deps"])}）')
    for param in entry['params']:
        if param.name in user_params:
            ok, message = param.validate(user_params[param.name])
            if not ok:
                raise WorkerError('INVALID_PARAMS', f'{key}.{param.name}: {message}')

    merged: dict[str, Any] = {**entry['defaults'], **user_params}
    for param in entry['params']:
        if param.type == PARAM_TYPE_COLOR and isinstance(merged.get(param.name), str):
            merged[param.name] = _hex_to_rgb(merged[param.name])

    prepared: dict[str, Any] = {'width': width, 'height': height, 'merged': merged}
    if key.startswith('fractal:') and key != 'fractal:mandelbulb':
        try:
            fractal_params = _build_fractal_params(
                key[len('fractal:'):], width, height, merged)
            fractal_params.validate()  # FractalParams 取值域（width/scale/迭代…）
        except (TypeError, ValueError) as exc:
            # FractalColoring 非法值 / 数值转换失败 / FractalParams.validate
            raise WorkerError('INVALID_PARAMS', f'{key}: {exc}') from exc
        prepared['fractal_params'] = fractal_params
    return entry, prepared


def validate_render_request(params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """generate.render 参数形状校验（dispatcher 任务工厂的提交前判定）。

    generator_key 为规范字段（native StudioService.render 上送同名键）；
    generator 作为同名别名兼容接受（任务单书写）。"""
    key = params.get('generator_key') or params.get('generator')
    if not isinstance(key, str) or not key.strip():
        raise WorkerError('INVALID_PARAMS', '缺少 generator_key')
    width = _require_side(params.get('width'), 'width')
    height = _require_side(params.get('height'), 'height')
    user_params = params.get('params')
    if user_params is None:
        user_params = {}
    if not isinstance(user_params, dict):
        raise WorkerError('INVALID_PARAMS', 'params 必须是对象')
    return prepare_render(key.strip(), width, height, user_params)


def _progress_with(progress_cb: Callable[..., None] | None, message: str):
    """processors 渲染回调只发 int 进度；任务体补 message（§2.3 task.progress）。"""
    if progress_cb is None:
        return None

    def _cb(value: int) -> None:
        progress_cb(int(value), message)

    return _cb


def _check_cancel(cancel_token) -> None:
    if cancel_token is not None:
        cancel_token.raise_if_cancelled()


def render_generator(entry: dict[str, Any], prepared: dict[str, Any],
                     progress_cb: Callable[..., None] | None,
                     cancel_token) -> np.ndarray:
    """统一渲染入口：分发到 processors 既有生成器实现，返回 RGB ndarray。"""
    key = entry['key']
    width, height = int(prepared['width']), int(prepared['height'])
    merged: dict[str, Any] = prepared['merged']

    if key.startswith('fractal:'):
        if key == 'fractal:mandelbulb':
            result = fractal_processor.render_mandelbulb(
                width, height,
                power=float(merged.get('power', 8.0)),
                iterations=int(merged.get('iterations', 64)),
                cancel_token=cancel_token,
                progress_cb=_progress_with(progress_cb, '渲染 Mandelbulb'))
            return np.asarray(result.image)
        result = fractal_processor.render_fractal(
            width, height, key[len('fractal:'):], prepared['fractal_params'],
            cancel_token=cancel_token,
            progress_cb=_progress_with(progress_cb, '渲染分形'))
        return np.asarray(result.image)

    if key.startswith('texture:'):
        # texture_studio 生成是同步 CPU 计算（无内部检查点）：取消在任务体
        # 边界检查（§7 协作取消在该族生成器上的最小区间）。
        _check_cancel(cancel_token)
        image = texture_generators.generate(key[len('texture:'):], width, height, merged)
        _check_cancel(cancel_token)
        return np.asarray(image)

    if key == 'gradient:linear':
        _check_cancel(cancel_token)
        return gradients.linear_gradient(
            width, height,
            _coerce_color(merged.get('color_a'), 'color_a'),
            _coerce_color(merged.get('color_b'), 'color_b'),
            float(merged.get('angle', 0.0)))

    if key == 'gradient:radial':
        _check_cancel(cancel_token)
        return gradients.radial_gradient(
            width, height,
            _coerce_color(merged.get('color_a'), 'color_a'),
            _coerce_color(merged.get('color_b'), 'color_b'),
            float(merged.get('cx', 0.5)), float(merged.get('cy', 0.5)))

    if key == 'gradient:mesh':
        _check_cancel(cancel_token)
        preset = str(merged.get('preset', 'piretti'))
        if preset not in gradients.MESH_PRESETS:
            # 枚举已在提交前由 FilterParam.validate 拒绝；此处为兜底如实失败。
            raise WorkerError('ENGINE_ERROR', f'未知网格渐变预设: {preset}')
        return gradients.mesh_gradient(width, height, gradients.MESH_PRESETS[preset])

    raise WorkerError('ENGINE_ERROR', f'生成器 {key} 缺少渲染实现')


def write_render(image: np.ndarray, temp_dir: Path, generator_key: str,
                 width: int, height: int) -> dict[str, Any]:
    """generate.render 结果落盘：复用 filter_adapter.write_preview 的 §4 临时
    PNG 通道（path/sha256，无 Base64）。max_side 取请求尺寸（≥ 图像最长边），
    downscale_preview 因此不降采样——generate.render 按请求的 width/height
    原尺寸交付。文件按生成器 key 覆盖命名（§4 防临时文件堆积规则）。"""
    safe_key = generator_key.replace(':', '-').replace('/', '_')
    return filter_adapter.write_preview(
        np.ascontiguousarray(image), temp_dir, f'generate-{safe_key}',
        max_side=max(int(width), int(height)))
