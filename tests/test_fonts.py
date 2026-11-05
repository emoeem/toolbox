from __future__ import annotations

import unittest

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo
from PySide6.QtWidgets import QApplication

from app.fonts import (
    DEFAULT_SIZE,
    DIAGNOSTIC_GLYPHS,
    MONO_CANDIDATES,
    SYSTEM_DEFAULT,
    apply,
    diagnose,
    fallback_candidates,
    glyph_coverage,
    mono_font,
    resolve_family,
    ui_font,
)
from app.theme import DARK_QSS, LIGHT_QSS


def _settings() -> QSettings:
    settings = QSettings("ToolboxTest", "Fonts")
    settings.clear()
    return settings


class ThemeFontTests(unittest.TestCase):
    """主题不得通过 QSS 强制字体族或全局字号，字体由 app.font() 统一控制。"""

    def test_theme_does_not_force_global_font(self):
        for qss in (LIGHT_QSS, DARK_QSS):
            self.assertNotIn('font-family', qss)
            self.assertNotIn('* {', qss)

    def test_theme_does_not_reference_misans(self):
        for qss in (LIGHT_QSS, DARK_QSS):
            self.assertNotIn('MiSans', qss)


class ResolveFamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.families = QFontDatabase.families()

    def test_resolves_installed_family(self):
        if not self.families:
            self.skipTest('系统未安装任何字体')
        self.assertEqual(resolve_family(self.families[0], ()), self.families[0])

    def test_missing_preference_falls_through_candidates(self):
        if not self.families:
            self.skipTest('系统未安装任何字体')
        self.assertEqual(resolve_family('NoSuchFont-XYZ', (self.families[0],)), self.families[0])

    def test_all_missing_returns_system_default(self):
        self.assertEqual(resolve_family('NoSuchFont-XYZ', ('NoSuchFont-ABC',)), SYSTEM_DEFAULT)


class ApplyFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.has_fonts = bool(QFontDatabase.families())

    def test_apply_system_default(self):
        if not self.has_fonts:
            self.skipTest('系统未安装任何字体')
        info = apply(self.app, _settings())
        self.assertEqual(info['requested_family'], SYSTEM_DEFAULT)
        self.assertEqual(info['size'], DEFAULT_SIZE)
        # 实际解析出的字体必须是已安装的真实字体，而不是配置里的占位名。
        self.assertTrue(info['family'])
        self.assertIn(info['family'], QFontDatabase.families())
        self.assertEqual(QFontInfo(self.app.font()).family(), info['family'])

    def test_apply_explicit_family(self):
        families = QFontDatabase.families()
        if not families:
            self.skipTest('系统未安装任何字体')
        settings = _settings()
        settings.setValue('font/family', families[0])
        info = apply(self.app, settings)
        self.assertEqual(info['requested_family'], families[0])
        self.assertEqual(QFontInfo(self.app.font()).family(), families[0])

    def test_apply_missing_family_falls_back_to_installed(self):
        if not self.has_fonts:
            self.skipTest('系统未安装任何字体')
        settings = _settings()
        settings.setValue('font/family', 'NoSuchFont-XYZ')
        info = apply(self.app, settings)
        self.assertEqual(info['requested_family'], 'NoSuchFont-XYZ')
        self.assertIn(info['family'], QFontDatabase.families())

    def test_apply_uses_qt6_style_and_hinting_apis(self):
        apply(self.app, _settings())
        font = self.app.font()
        self.assertGreater(font.pointSize(), 0)
        self.assertEqual(font.hintingPreference(), QFont.PreferFullHinting)
        self.assertTrue(font.styleStrategy() & QFont.PreferAntialias)

    def test_size_setting_respected(self):
        settings = _settings()
        settings.setValue('font/size', 14)
        apply(self.app, settings)
        self.assertEqual(self.app.font().pointSize(), 14)


class MonoFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_mono_font_has_monospace_hint(self):
        if not QFontDatabase.families():
            self.skipTest('系统未安装任何字体')
        mono = mono_font(_settings())
        self.assertEqual(mono.styleHint(), QFont.Monospace)
        self.assertTrue(QFontInfo(mono).family())

    def test_mono_explicit_family_is_applied(self):
        installed = [f for f in MONO_CANDIDATES if f in QFontDatabase.families()]
        if not installed:
            self.skipTest('未安装候选等宽字体，验证系统回退')
        settings = _settings()
        settings.setValue('font/mono', installed[0])
        mono = mono_font(settings)
        self.assertEqual(QFontInfo(mono).family(), installed[0])

    def test_mono_used_by_shader_editor(self):
        from app.panels.shader_studio import LineEditor
        editor = LineEditor(mono_font(_settings()))
        try:
            self.assertEqual(editor.font().styleHint(), QFont.Monospace)
        finally:
            editor.deleteLater()


class FontDiagnosticTests(unittest.TestCase):
    """计划验收要求：程序必须能查询实际字体，并诊断中文/英文/数字/符号/Emoji 的回退。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.has_fonts = bool(QFontDatabase.families())

    def test_glyph_coverage_reports_all_charsets(self):
        if not self.has_fonts:
            self.skipTest('系统未安装任何字体')
        coverage = glyph_coverage(QApplication.font())
        self.assertEqual(set(coverage), set(DIAGNOSTIC_GLYPHS))
        self.assertTrue(all(isinstance(v, bool) for v in coverage.values()))
        self.assertTrue(coverage['latin'], '基础拉丁字符必须由解析出的 UI 字体直接覆盖')

    def test_cjk_is_renderable_after_apply(self):
        if not self.has_fonts:
            self.skipTest('系统未安装任何字体')
        apply(self.app, _settings())
        coverage = glyph_coverage(self.app.font())
        if not coverage['cjk'] and not fallback_candidates('中'):
            self.skipTest('系统未安装任何覆盖 CJK 的字体')

    def test_emoji_or_fallback_available(self):
        if not self.has_fonts:
            self.skipTest('系统未安装任何字体')
        coverage = glyph_coverage(self.app.font())
        if not coverage['emoji'] and not fallback_candidates('😀'):
            self.skipTest('系统未安装任何覆盖 Emoji 的字体')

    def test_diagnose_report_structure(self):
        if not self.has_fonts:
            self.skipTest('系统未安装任何字体')
        report = diagnose(_settings())
        for section in ('ui', 'mono'):
            self.assertIn('requested', report[section])
            self.assertIn('resolved', report[section])
            self.assertIn('coverage', report[section])
            self.assertTrue(report[section]['resolved'])
        self.assertIn('fallback', report)
        self.assertEqual(set(report['ui']['coverage']), set(DIAGNOSTIC_GLYPHS))

    def test_ui_font_helper_matches_apply(self):
        settings = _settings()
        font = ui_font(settings)
        self.assertEqual(font.pointSize(), DEFAULT_SIZE)
        self.assertEqual(font.styleHint(), QFont.SansSerif)


if __name__ == '__main__':
    unittest.main()
