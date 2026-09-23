import ast
import importlib
from pathlib import Path


def _processor_modules():
    return {".".join(p.relative_to(Path(".")).with_suffix("").parts) for p in Path("processors").rglob("*.py")}


def test_all_processor_imports_exist_and_import_cleanly():
    modules = _processor_modules()
    failures = []
    for path in Path("app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module or not node.module.startswith("processors.") or node.level:
                continue
            if node.module not in modules:
                failures.append(f"{path}:{node.lineno}: missing module {node.module}")
                continue
            try:
                module = importlib.import_module(node.module)
            except Exception as exc:
                failures.append(f"{path}:{node.lineno}: import {node.module}: {exc}")
                continue
            for alias in node.names:
                if alias.name != "*" and not hasattr(module, alias.name):
                    failures.append(f"{path}:{node.lineno}: missing {node.module}.{alias.name}")
    assert not failures, "\\n".join(failures)
