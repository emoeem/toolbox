import tempfile,unittest
from pathlib import Path
from PIL import Image
from processors.texture_studio.generators import generate
from processors.texture_studio.presets import BUILTIN_PRESETS
from processors.texture_studio.library import TextureLibrary
class TextureTests(unittest.TestCase):
 def test_all_fastnoise_and_patterns_generate(self):
  for p in BUILTIN_PRESETS:
   im=generate(p.generator_id,96,64,p.params); self.assertEqual(im.size,(96,64)); self.assertEqual(im.mode,'RGB'); self.assertGreater(len(set(im.get_flattened_data())),1,p.name)
 def test_parameter_changes_output(self):
  p=BUILTIN_PRESETS[0]; a=generate(p.generator_id,96,64,p.params); q=dict(p.params); q['seed']+=1; b=generate(p.generator_id,96,64,q); self.assertNotEqual(a.tobytes(),b.tobytes())
 def test_library_persistence(self):
  with tempfile.TemporaryDirectory() as d:
   lib=TextureLibrary(Path(d)); p=BUILTIN_PRESETS[0]; custom=type(p)(p.name+' Custom',p.generator_id,p.params.copy(),p.tags); lib.save(custom); self.assertTrue(any(x.name==custom.name for x in lib.list() if x)); lib.toggle_favorite(p.generator_id); self.assertIn(p.generator_id,TextureLibrary(Path(d)).favorites); lib.delete(custom.name); self.assertFalse(any(x and x.name==custom.name for x in lib.list()))
 def test_export_readable(self):
  with tempfile.TemporaryDirectory() as d:
   im=generate('pattern:grid',64,64,BUILTIN_PRESETS[-1].params)
   for ext in ('png','jpg','webp'):
    path=Path(d)/f'x.{ext}'; im.save(path)
    with Image.open(path) as check: self.assertEqual(check.size,(64,64))
 def test_raymarch_default_and_parameter_change(self):
  p=next(x for x in BUILTIN_PRESETS if x.generator_id.startswith('raymarch:'))
  a=generate(p.generator_id,64,64,p.params); q=dict(p.params); q['seed']+=1; b=generate(p.generator_id,64,64,q)
  self.assertEqual(a.size,(64,64)); self.assertEqual(a.mode,'RGB'); self.assertNotEqual(a.tobytes(),b.tobytes())
if __name__=='__main__': unittest.main()
