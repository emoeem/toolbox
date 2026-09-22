import os, ast

print("=== processors 模块 ===")
for root, _, fns in os.walk("processors"):
    for fn in sorted(fns):
        if fn.endswith(".py"):
            path = os.path.join(root, fn)
            with open(path) as fh:
                tree = ast.parse(fh.read())
            funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            public = [f for f in funcs if not f.startswith("_")]
            print(f"  {fn:<25} {len(public):>3d} funcs")

print("\n=== main_window.py 面板构建 ===")
with open("app/main_window.py") as f:
    src = f.read()

panel_line = src.split("TOOL_ITEMS = [\n", 1)[1].split("]\n", 1)[0]
panels = [(l.split(",")[0].strip().strip('("'), l.split(",")[1].strip().strip('("'))
          for l in panel_line.split("\n") if l.strip()]
print(f"  TOOL_ITEMS: {len(panels)} 个面板")
for i, (icon, name) in enumerate(panels):
    print(f"    [{i}] {icon} {name}")

builders = [l.strip().split("self.")[1].rstrip(",") for l in src.split("builders = [")[1].split("]")[0].split("\n") if "_build_" in l]
print(f"\n  builders 列表: {len(builders)}")
for b in builders: print(f"    {b}")

print("\n=== 实际 _build_ 方法 ===")
for line in src.split("\n"):
    if line.strip().startswith("def _build_"):
        print(f"    {line.strip()}")

print("\n=== TOOL_ITEMS vs builders vs 实际方法 对照 ===")
for i, (icon, name) in enumerate(panels):
    expected_method = f"_build_{['adjust','filter','format','pdf','exif','ocr','watermark','color','crop','transform','shape_mask','histogram','compare','checksum','barcode','gradient','stitch','batch','lut','smart_resize','about'][i]}_panel" if i < 21 else None
    in_builders = f"self.{expected_method}" in builders if expected_method else False
    actual_exists = f"def {expected_method}" in src if expected_method else False
    mark = "✅" if in_builders and actual_exists else "❌"
    print(f"  [{i:>2}] {icon} {name:<10}  method={expected_method:<30} in_builders={in_builders} actual={actual_exists} {mark}")

print("\n=== 滤镜数量 ===")
import sys; sys.path.insert(0, ".")
from processors import advanced_filters
from processors.filters import ALL_FILTERS
print(f"  ALL_FILTERS 总数: {len(ALL_FILTERS)}")
