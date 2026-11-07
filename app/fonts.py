from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase, QFontInfo, QRawFont
from PySide6.QtWidgets import QApplication

# 空 family 表示"系统默认"，由 Qt 平台解析（Linux 上交给 fontconfig）。
SYSTEM_DEFAULT = ''

# UI 字体候选：仅在用户显式选择后生效；不再把任何固定字体强加给系统默认。
SANS_CANDIDATES = (
    'Noto Sans CJK SC', 'Sarasa UI SC', 'Source Han Sans SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', 'WenQuanYi Zen Hei', 'LXGW ZhenKai',
)

# 等宽字体候选；全部未命中时由 QFont.Monospace style hint 回退到系统等宽字体。
MONO_CANDIDATES = (
    'Maple Mono Normal NF CN', 'Maple Mono NF CN', 'Maple Mono', 'JetBrains Mono',
    'Cascadia Mono', 'Cascadia Code', 'Consolas', 'Noto Sans Mono CJK SC', 'DejaVu Sans Mono',
)

DEFAULT_SIZE = 11

# 诊断用字符集：检查字体对中文/英文/数字/符号/Emoji 的实际覆盖。
DIAGNOSTIC_GLYPHS = {
    'latin': 'Ag',
    'digit': '09',
    'cjk': '中文像素',
    'symbol': '→€',
    'emoji': '😀',
}


def resolve_family(preferred, candidates) -> str:
    """按优先级解析出实际可用的字体族；全部未命中时返回 SYSTEM_DEFAULT。"""
    fams = set(QFontDatabase.families())
    for x in (preferred, *candidates):
        if x and x in fams:
            return x
    return SYSTEM_DEFAULT


def resolve_size(settings) -> int:
    try:
        return int(settings.value('font/size', DEFAULT_SIZE))
    except (TypeError, ValueError):
        return DEFAULT_SIZE


def ui_font(settings) -> QFont:
    family = resolve_family(settings.value('font/family', SYSTEM_DEFAULT), SANS_CANDIDATES)
    font = QFont(family, resolve_size(settings))
    font.setStyleHint(QFont.SansSerif)
    font.setStyleStrategy(QFont.PreferAntialias)
    font.setHintingPreference(QFont.PreferFullHinting)
    return font


def mono_font(settings) -> QFont:
    """等宽字体：显式选择 > 候选链 > 系统 default mono（QFont.Monospace hint）。"""
    family = resolve_family(settings.value('font/mono', SYSTEM_DEFAULT), MONO_CANDIDATES)
    font = QFont(family, resolve_size(settings))
    font.setStyleHint(QFont.Monospace)
    return font


def actual_family(font: QFont) -> str:
    """查询 Qt 为该 QFont 实际解析出的字体族（而非配置里的名字）。"""
    return QFontInfo(font).family()


def apply(app: QApplication, settings) -> dict:
    """应用字体设置到整个应用；返回实际解析结果供诊断与设置页回显。"""
    font = ui_font(settings)
    mono = mono_font(settings)
    app.setFont(font)
    return {
        'requested_family': settings.value('font/family', SYSTEM_DEFAULT),
        'family': actual_family(font),
        'size': font.pointSize(),
        'mono_requested': settings.value('font/mono', SYSTEM_DEFAULT),
        'mono': actual_family(mono),
    }


def _covers(raw: QRawFont, chars: str) -> bool:
    return raw.isValid() and all(raw.supportsCharacter(ord(c)) for c in chars)


def glyph_coverage(font: QFont) -> dict:
    """主字体对各诊断字符集的覆盖情况；未覆盖部分由 Qt 逐字符回退机制接管。"""
    raw = QRawFont.fromFont(font)
    return {name: _covers(raw, chars) for name, chars in DIAGNOSTIC_GLYPHS.items()}


def fallback_candidates(chars: str, limit: int = 8) -> list[str]:
    """在已安装字体中查找能覆盖给定字符的字体族，用于确认回退可用。"""
    found: list[str] = []
    for fam in QFontDatabase.families():
        try:
            if _covers(QRawFont.fromFont(QFont(fam)), chars[:1]):
                found.append(fam)
        except RuntimeError:
            continue
        if len(found) >= limit:
            break
    return found


def diagnose(settings) -> dict:
    """字体解析完整诊断：请求值、实际解析值、覆盖情况与回退可用性。"""
    font, mono = ui_font(settings), mono_font(settings)
    ui_coverage = glyph_coverage(font)
    report = {
        'ui': {
            'requested': settings.value('font/family', SYSTEM_DEFAULT),
            'resolved': actual_family(font),
            'size': font.pointSize(),
            'coverage': ui_coverage,
        },
        'mono': {
            'requested': settings.value('font/mono', SYSTEM_DEFAULT),
            'resolved': actual_family(mono),
            'size': mono.pointSize(),
            'coverage': glyph_coverage(mono),
        },
        'fallback': {},
    }
    for name, chars in DIAGNOSTIC_GLYPHS.items():
        if not ui_coverage[name]:
            report['fallback'][name] = fallback_candidates(chars)
    return report
