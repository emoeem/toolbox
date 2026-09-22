import json
from pathlib import Path
from .model import TexturePreset
from .presets import BUILTIN_PRESETS
class TextureLibrary:
    def __init__(self,root):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self.fav_path=self.root/'favorites.json'; self.favorites=set(json.loads(self.fav_path.read_text()) if self.fav_path.exists() else [])
    def list(self):
        result=list(BUILTIN_PRESETS)
        for p in self.root.glob('*.json'):
            if p.name=='favorites.json': continue
            q=self._read(p)
            if q: result.append(q)
        return result
    def _read(self,p):
        try:
            d=json.loads(p.read_text()); return TexturePreset(d['name'],d['generator_id'],d['params'],d.get('tags',[]))
        except (OSError,ValueError,KeyError,TypeError): return None
    def save(self,p):
        data={'name':p.name,'generator_id':p.generator_id,'params':p.params,'tags':p.tags,'version':1,'backend':getattr(p,'backend','numpy')}
        (self.root/(p.name.replace('/','_')+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2))
    def delete(self,name):
        path=self.root/(name.replace('/','_')+'.json')
        if path.exists(): path.unlink()
    def toggle_favorite(self,gid):
        if gid in self.favorites:self.favorites.remove(gid)
        else:self.favorites.add(gid)
        self.fav_path.write_text(json.dumps(sorted(self.favorites),ensure_ascii=False))
