"""Static and lifecycle guards for app/main_window.py.

These target bug classes that are invisible to ordinary unit tests because the
defects only appear when a user clicks a specific button:

1. Calls to methods that do not exist on the collaborating object
   (``self.preview.get_image()`` -- 14 call sites, 13 features).
2. Bare references to a module that the enclosing function never imported
   (``lut`` / ``gradients`` / ``utils`` -> NameError at click time).
3. Touching panel widgets after the panel was torn down by switching tools
   ("RuntimeError: Internal C++ object already deleted").
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW = ROOT / "app" / "main_window.py"


class TestNoMissingPreviewMethods(unittest.TestCase):
    def test_every_preview_method_used_exists(self):
        from app.preview_widget import ImagePreview
        src = MAIN_WINDOW.read_text(encoding="utf-8")
        used = set(re.findall(r"self\.preview\.([A-Za-z_]\w*)", src))
        missing = sorted(n for n in used if not hasattr(ImagePreview, n))
        self.assertEqual(missing, [], f"app/main_window.py calls non-existent ImagePreview members: {missing}")


class TestNoMissingModuleImports(unittest.TestCase):
    """A bare `mod.attr` inside a function must be bound in that scope."""

    def _audit(self, path: Path, modules: set[str]) -> list[str]:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        module_level = {
            a.asname or a.name.split(".")[0]
            for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for a in node.names
        }

        def fn_local(fn) -> set[str]:
            names = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs} | {
                a.arg for a in fn.args.posonlyargs}
            for n in ast.walk(fn):
                if n is fn:
                    continue
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    for a in n.names:
                        names.add(a.asname or a.name.split(".")[0])
                elif isinstance(n, ast.Assign):
                    for t in n.targets:
                        if isinstance(t, ast.Name):
                            names.add(t.id)
            return names

        problems = []
        for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            seg = ast.get_source_segment(src, fn) or ""
            used = set(re.findall(r"\b([a-z_][a-z0-9_]*)\.\w", seg))
            for name in sorted((used & modules) - fn_local(fn) - module_level):
                problems.append(f"{fn.name}() line {fn.lineno} uses undefined '{name}'")
        return problems

    def test_main_window_module_references_are_imported(self):
        modules = {p.stem for p in (ROOT / "processors").glob("*.py") if p.stem != "__init__"}
        modules |= {"img_core"}
        self.assertEqual(self._audit(MAIN_WINDOW, modules), [])


class TestStaleWidgetGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        from app.main_window import MainWindow
        w = MainWindow()
        img = np.random.default_rng(0).integers(0, 255, (32, 48, 3), np.uint8)
        w.preview.set_image(img)
        w._applied_image = img.copy()
        return w

    def test_widget_alive_helper(self):
        from PySide6.QtWidgets import QListWidget
        from app.main_window import _widget_alive
        self.assertFalse(_widget_alive(None))
        widget = QListWidget()
        self.assertTrue(_widget_alive(widget))
        widget.setParent(None)
        widget.deleteLater()
        from PySide6.QtCore import QEvent
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertFalse(_widget_alive(widget))

    def test_undo_and_reset_survive_panel_teardown(self):
        from PySide6.QtCore import QEvent
        w = self._window()
        w._build_filter_panel()
        self.assertTrue(hasattr(w, "_chain_list"))
        w._push_history("测试")
        # Switching tools destroys the Filter panel's widgets via deleteLater().
        w._build_color_panel()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        # Both used to raise "Internal C++ object (QListWidget) already deleted".
        w.undo()
        w.reset_all()
        w.close()

    def test_reset_all_without_ever_building_the_filter_panel(self):
        # Reachable via the preview's Escape shortcut on any tool.
        w = self._window()
        w.reset_all()
        w.close()


if __name__ == "__main__":
    unittest.main()
