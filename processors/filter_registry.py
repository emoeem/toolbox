from __future__ import annotations

import numpy as np

from . import filters as legacy
from .filter_defs import (
    FilterCategory,
    FilterDefRegistry,
    FilterParam,
    PARAM_TYPE_BOOL,
    PARAM_TYPE_ENUM,
    PARAM_TYPE_FLOAT,
    PARAM_TYPE_INT,
    register_filter,
)


def register_curated_filters() -> int:
    reg = FilterDefRegistry.instance()
    count = 0

    def _register(key, zh_name, func, category, params, desc=""):
        if reg.has(key):
            return 0
        register_filter(
            key=key,
            display_name=zh_name,
            processor=func,
            category=category,
            params=params,
            description=desc or zh_name,
        )
        return 1

    # ===== BLUR =====
    count += _register("gaussian_blur", "高斯模糊", legacy.gaussian_blur, FilterCategory.BLUR, [
        FilterParam(name="ksize", label="核大小", type=PARAM_TYPE_INT, default=11, minimum=1, maximum=51, step=2),
        FilterParam(name="sigma", label="Sigma", type=PARAM_TYPE_FLOAT, default=2.0, minimum=0.1, maximum=20.0, step=0.1),
    ], "高斯模糊，最常用的模糊滤镜")

    count += _register("box_blur", "方框模糊", legacy.box_blur, FilterCategory.BLUR, [
        FilterParam(name="ksize", label="核大小", type=PARAM_TYPE_INT, default=9, minimum=1, maximum=51, step=2),
    ], "均匀方框模糊")

    count += _register("median_blur", "中值模糊", legacy.median_blur, FilterCategory.BLUR, [
        FilterParam(name="ksize", label="核大小", type=PARAM_TYPE_INT, default=5, minimum=1, maximum=51, step=2),
    ], "中值模糊，对椒盐噪声有效")

    count += _register("bilateral_blur", "双边模糊", legacy.bilateral_blur, FilterCategory.BLUR, [
        FilterParam(name="d", label="邻域直径", type=PARAM_TYPE_INT, default=9, minimum=1, maximum=50, step=1),
        FilterParam(name="sigma_color", label="颜色 Sigma", type=PARAM_TYPE_FLOAT, default=75.0, minimum=1.0, maximum=300.0, step=1.0),
        FilterParam(name="sigma_space", label="空间 Sigma", type=PARAM_TYPE_FLOAT, default=75.0, minimum=1.0, maximum=300.0, step=1.0),
    ], "保边模糊")

    count += _register("motion_blur", "运动模糊", legacy.motion_blur, FilterCategory.BLUR, [
        FilterParam(name="ksize", label="核大小", type=PARAM_TYPE_INT, default=15, minimum=3, maximum=101, step=2),
        FilterParam(name="angle", label="角度", type=PARAM_TYPE_FLOAT, default=0.0, minimum=0.0, maximum=360.0, step=1.0),
    ], "模拟运动方向的模糊")

    count += _register("zoom_blur", "缩放模糊", legacy.zoom_blur, FilterCategory.BLUR, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=0.5, minimum=0.0, maximum=3.0, step=0.01),
    ], "从中心向外的缩放模糊")

    count += _register("vignette_blur", "虚化边缘", legacy.vignette_blur, FilterCategory.BLUR, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=0.5, minimum=0.0, maximum=3.0, step=0.01),
    ], "四角虚化")

    # ===== NOISE =====
    count += _register("noise", "噪声", legacy.noise, FilterCategory.NOISE, [
        FilterParam(name="std", label="标准差", type=PARAM_TYPE_FLOAT, default=20.0, minimum=0.0, maximum=150.0, step=1.0),
    ], "高斯噪声")

    count += _register("film_grain", "胶片颗粒", legacy.film_grain, FilterCategory.NOISE, [
        FilterParam(name="amount", label="颗粒量", type=PARAM_TYPE_FLOAT, default=0.3, minimum=0.0, maximum=1.0, step=0.01),
    ], "模拟胶片颗粒")

    count += _register("halftone", "半色调", legacy.halftone, FilterCategory.NOISE, [
        FilterParam(name="dot_size", label="点大小", type=PARAM_TYPE_INT, default=6, minimum=1, maximum=50, step=1),
    ], "半色调印刷效果")

    count += _register("dither_bayer", "Bayer 抖动", legacy.dither_bayer, FilterCategory.NOISE, [
        FilterParam(name="levels", label="色阶数", type=PARAM_TYPE_INT, default=4, minimum=2, maximum=16, step=1),
        FilterParam(name="order", label="矩阵阶数", type=PARAM_TYPE_INT, default=4, minimum=2, maximum=8, step=2),
    ], "Bayer 有序抖动")

    count += _register("floyd_steinberg", "Floyd-Steinberg 抖动", legacy.floyd_steinberg, FilterCategory.NOISE, [
        FilterParam(name="levels", label="色阶数", type=PARAM_TYPE_INT, default=4, minimum=2, maximum=16, step=1),
    ], "Floyd-Steinberg 误差扩散抖动")

    count += _register("denoise", "降噪", legacy.denoise, FilterCategory.NOISE, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=10.0, minimum=1.0, maximum=100.0, step=1.0),
    ], "NLMeans 降噪")

    # ===== COLOR =====
    count += _register("exposure_linear", "曝光校正", legacy.exposure_linear, FilterCategory.COLOR, [
        FilterParam(name="stops", label="曝光 (EV)", type=PARAM_TYPE_FLOAT, default=0.0, minimum=-5.0, maximum=5.0, step=0.1),
    ], "线性曝光调整")

    count += _register("sepia", "复古棕", legacy.sepia, FilterCategory.COLOR, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=0.0, maximum=1.0, step=0.01),
    ], "经典棕褐色调")

    count += _register("cool", "冷色", legacy.cool, FilterCategory.COLOR, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=0.0, maximum=1.0, step=0.01),
    ], "冷色调")

    count += _register("warm", "暖色", legacy.warm, FilterCategory.COLOR, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=0.0, maximum=1.0, step=0.01),
    ], "暖色调")

    count += _register("dehaze", "去雾", legacy.dehaze, FilterCategory.COLOR, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=0.0, maximum=3.0, step=0.01),
    ], "去除雾霾效果")

    count += _register("haze", "雾化", legacy.haze, FilterCategory.COLOR, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=0.3, minimum=0.0, maximum=3.0, step=0.01),
    ], "添加雾化效果")

    count += _register("solarize", "曝光反转", legacy.solarize, FilterCategory.COLOR, [
        FilterParam(name="threshold", label="阈值", type=PARAM_TYPE_INT, default=128, minimum=0, maximum=255, step=1),
    ], "特定阈值反色")

    count += _register("black_and_white", "黑白", legacy.black_and_white, FilterCategory.COLOR, [
        FilterParam(name="threshold", label="阈值", type=PARAM_TYPE_INT, default=128, minimum=0, maximum=255, step=1),
    ], "阈值化黑白")

    count += _register("posterize", "色调分离", legacy.posterize, FilterCategory.COLOR, [
        FilterParam(name="levels", label="色阶数", type=PARAM_TYPE_INT, default=4, minimum=2, maximum=16, step=1),
    ], "减少颜色层次")

    count += _register("false_color", "伪彩色", legacy.false_color, FilterCategory.COLOR, [
        FilterParam(name="colormap", label="色图", type=PARAM_TYPE_ENUM, default="jet",
                    choices=["jet", "viridis", "plasma", "inferno", "magma", "cool", "hot", "hsv"]),
    ], "应用伪彩色映射")

    count += _register("clahe_apply", "CLAHE", legacy.clahe_apply, FilterCategory.COLOR, [
        FilterParam(name="clip_limit", label="裁剪限制", type=PARAM_TYPE_FLOAT, default=2.0, minimum=0.5, maximum=20.0, step=0.1),
        FilterParam(name="tile_size", label="瓷砖大小", type=PARAM_TYPE_INT, default=8, minimum=2, maximum=32, step=1),
    ], "自适应直方图均衡")

    count += _register("white_balance_filter", "白平衡", legacy.white_balance_filter, FilterCategory.COLOR, [
        FilterParam(name="temperature", label="色温", type=PARAM_TYPE_FLOAT, default=0.0, minimum=-100.0, maximum=100.0, step=1.0),
        FilterParam(name="tint", label="色调", type=PARAM_TYPE_FLOAT, default=0.0, minimum=-100.0, maximum=100.0, step=1.0),
    ], "调整色温色调")

    count += _register("grayscale_standard", "灰度", legacy.grayscale_standard, FilterCategory.COLOR, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=0.0, maximum=1.0, step=0.01),
    ], "加权灰度转换")

    # ===== DISTORTION =====
    count += _register("bulge", "鼓胀", legacy.bulge, FilterCategory.DISTORTION, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=0.5, minimum=-2.0, maximum=2.0, step=0.01),
    ], "中心鼓胀变形")

    count += _register("pinch", "收缩", legacy.pinch, FilterCategory.DISTORTION, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=0.5, minimum=-2.0, maximum=2.0, step=0.01),
    ], "中心收缩变形")

    count += _register("wave", "波浪", legacy.wave, FilterCategory.DISTORTION, [
        FilterParam(name="amplitude", label="振幅", type=PARAM_TYPE_FLOAT, default=8.0, minimum=0.0, maximum=50.0, step=1.0),
        FilterParam(name="wavelength", label="波长", type=PARAM_TYPE_FLOAT, default=50.0, minimum=5.0, maximum=200.0, step=1.0),
    ], "波浪扭曲")

    count += _register("swirl", "漩涡", legacy.swirl, FilterCategory.DISTORTION, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=0.0, maximum=10.0, step=0.1),
    ], "漩涡旋转")

    count += _register("twirl", "扭转", legacy.twirl, FilterCategory.DISTORTION, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=10.0, minimum=-50.0, maximum=50.0, step=1.0),
    ], "角向扭转")

    count += _register("fish_eye", "鱼眼", legacy.fish_eye, FilterCategory.DISTORTION, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=-2.0, maximum=2.0, step=0.01),
    ], "鱼眼镜头效果")

    count += _register("crystallize", "结晶", legacy.crystallize, FilterCategory.DISTORTION, [
        FilterParam(name="cell_size", label="晶格大小", type=PARAM_TYPE_INT, default=12, minimum=2, maximum=50, step=1),
    ], "Voronoi 结晶效果")

    count += _register("mosaic", "马赛克", legacy.mosaic, FilterCategory.DISTORTION, [
        FilterParam(name="block_size", label="块大小", type=PARAM_TYPE_INT, default=12, minimum=2, maximum=50, step=1),
    ], "块马赛克")

    # ===== EDGE =====
    count += _register("edge_detection", "边缘检测", legacy.edge_detection, FilterCategory.EDGE, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=0.0, maximum=3.0, step=0.01),
    ], "Canny 边缘检测")

    count += _register("emboss", "浮雕", legacy.emboss, FilterCategory.EDGE, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=0.0, maximum=5.0, step=0.01),
    ], "浮雕效果")

    count += _register("sketch", "素描", legacy.sketch, FilterCategory.EDGE, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=0.0, maximum=3.0, step=0.01),
    ], "铅笔素描效果")

    # ===== SHARPEN =====
    count += _register("sharpen_simple", "锐化", legacy.sharpen_simple, FilterCategory.SHARPEN, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=0.0, maximum=5.0, step=0.01),
    ], "卷积锐化")

    count += _register("unsharp_mask", "USM 锐化", legacy.unsharp_mask, FilterCategory.SHARPEN, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=0.0, maximum=5.0, step=0.01),
        FilterParam(name="sigma", label="Sigma", type=PARAM_TYPE_FLOAT, default=1.5, minimum=0.1, maximum=10.0, step=0.1),
    ], "Unsharp Mask 锐化")

    count += _register("sharpen_unsharp", "USM 锐化2", legacy.sharpen_unsharp, FilterCategory.SHARPEN, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=1.5, minimum=0.0, maximum=5.0, step=0.01),
    ], "USM 锐化的另一种实现")

    # ===== STYLIZE =====
    count += _register("glitch", "故障效果", legacy.glitch, FilterCategory.STYLIZE, [
        FilterParam(name="amount", label="故障量", type=PARAM_TYPE_FLOAT, default=0.1, minimum=0.0, maximum=1.0, step=0.01),
    ], "数字故障效果")

    count += _register("bloom", "泛光", legacy.bloom, FilterCategory.STYLIZE, [
        FilterParam(name="threshold", label="阈值", type=PARAM_TYPE_FLOAT, default=0.7, minimum=0.0, maximum=1.0, step=0.01),
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=0.5, minimum=0.0, maximum=3.0, step=0.01),
    ], "泛光/光晕")

    count += _register("glow", "光晕", legacy.glow, FilterCategory.STYLIZE, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=0.5, minimum=0.0, maximum=3.0, step=0.01),
    ], "柔光泛光")

    count += _register("neon", "霓虹", legacy.neon, FilterCategory.STYLIZE, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=1.0, minimum=0.0, maximum=3.0, step=0.01),
    ], "霓虹发光效果")

    count += _register("oil_paint", "油画", legacy.oil_paint, FilterCategory.STYLIZE, [
        FilterParam(name="radius", label="半径", type=PARAM_TYPE_INT, default=4, minimum=1, maximum=20, step=1),
    ], "油画效果")

    count += _register("water_color", "水彩", legacy.water_color, FilterCategory.STYLIZE, [
        FilterParam(name="strength", label="强度", type=PARAM_TYPE_FLOAT, default=0.5, minimum=0.0, maximum=1.0, step=0.01),
    ], "水彩效果")

    # ===== PIXELATE =====
    count += _register("pixelate", "像素化", legacy.pixelate, FilterCategory.DISTORTION, [
        FilterParam(name="block_size", label="块大小", type=PARAM_TYPE_INT, default=8, minimum=2, maximum=50, step=1),
    ], "经典像素化")

    count += _register("enhanced_pixelation", "强像素化", legacy.enhanced_pixelation, FilterCategory.DISTORTION, [
        FilterParam(name="block_size", label="块大小", type=PARAM_TYPE_INT, default=12, minimum=2, maximum=50, step=1),
    ], "增强像素化")

    count += _register("circular_pixelation", "圆形像素", legacy.circular_pixelation, FilterCategory.DISTORTION, [
        FilterParam(name="block_size", label="块大小", type=PARAM_TYPE_INT, default=10, minimum=2, maximum=50, step=1),
    ], "圆形像素化")

    count += _register("pixellate_bw", "黑白像素", legacy.pixellate_bw, FilterCategory.DISTORTION, [
        FilterParam(name="block_size", label="块大小", type=PARAM_TYPE_INT, default=8, minimum=2, maximum=50, step=1),
    ], "黑白像素化")

    # ===== TEXTURE =====
    count += _register("dust_scratches", "粉尘划痕", legacy.dust_scratches, FilterCategory.TEXTURE, [
        FilterParam(name="amount", label="数量", type=PARAM_TYPE_FLOAT, default=0.1, minimum=0.0, maximum=1.0, step=0.01),
    ], "添加划痕和粉尘")

    count += _register("color_halftone", "彩色半调", legacy.color_halftone, FilterCategory.TEXTURE, [
        FilterParam(name="dot_size", label="点大小", type=PARAM_TYPE_INT, default=8, minimum=1, maximum=50, step=1),
    ], "CMYK 彩色半调")

    # ===== FRACTAL =====
    try:
        from processors.fractal import register_fractal_filters
        fractal_n = register_fractal_filters()
        count += fractal_n
    except Exception:
        pass

    return count
