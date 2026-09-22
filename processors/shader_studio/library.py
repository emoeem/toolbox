from __future__ import annotations
import json
from pathlib import Path
from .model import ShaderPreset

BUILTINS=[
ShaderPreset("Color Invert","vec4 c = texture(u_image, v_uv);\nfragColor = vec4(1.0-c.rgb,c.a);",description="Invert RGB"),
ShaderPreset("Grayscale","vec4 c = texture(u_image, v_uv);\nfloat y = dot(c.rgb, vec3(0.299,0.587,0.114));\nfragColor = vec4(vec3(y),c.a);",description="Luminance grayscale"),
ShaderPreset("Tint","// @min 0.0\n// @max 1.0\n// @step 0.01\nuniform float amount;\nvec4 c = texture(u_image, v_uv);\nfragColor = mix(c, vec4(1.0,0.25,0.7,1.0), amount);",description="Pink tint",tags=["color"]),
]

class ShaderLibrary:
    def __init__(self, root:Path):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def list(self):
        out=list(BUILTINS)
        for p in sorted(self.root.glob("*.json")):
            try: out.append(ShaderPreset.from_dict(json.loads(p.read_text(encoding="utf-8"))))
            except (OSError,ValueError,TypeError): pass
        return out
    def save(self,preset):
        safe="".join(c if c.isalnum() or c in "-_" else "_" for c in preset.name).strip("_") or "shader"
        (self.root/f"{safe}.json").write_text(json.dumps(preset.to_dict(),ensure_ascii=False,indent=2),encoding="utf-8")
    def delete(self,name):
        for p in self.root.glob("*.json"):
            try:
                if json.loads(p.read_text(encoding="utf-8")).get("name")==name: p.unlink()
            except: pass
    def export_json(self,preset,path): Path(path).write_text(json.dumps(preset.to_dict(),ensure_ascii=False,indent=2),encoding="utf-8")
    def import_json(self,path): return ShaderPreset.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
