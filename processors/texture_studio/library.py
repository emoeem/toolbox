import json
from pathlib import Path
from .model import TexturePreset
from .presets import BUILTIN_PRESETS
class TextureLibrary:
    def __init__(self,root): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self.fav_path=self.root/'favorites.json'; self.favorites=set(json.loads(self.fav_path.read_text()) if self.fav_path.exists() else [])
    def list(self): return BUILTIN_PRESETS+[self._read(p) for p in self.root.glob('*.json') if p.name!='favorites.json' and self._read(p) is not None]
    def _read(self,p):
        try:
            d=json.loads(p.read_text()); return TexturePreset(d['name'],d['generator_id'],d['params'],d.get('tags',[]))
        except Exception:return None
    def save(self,p): (self.root/(p.name.replace('/','_')+'.json')).write_text(json.dumps(p.__dict__,ensure_ascii=False,indent=2))
    def delete(self,name):
        for p in self.root.glob('*.json'):
            if p.name!='favorites.json' and p.name == name.replace('/','_')+'.json': p.unlink()
    def toggle_favorite(self,gid):
        self.favorites.remove(gid) if gid in self.favorites else self.favorites.add(gid); self.fav_path.write_text(json.dumps(sorted(self.favorites)))
