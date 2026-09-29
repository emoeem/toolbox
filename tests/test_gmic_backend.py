import unittest
import json,shutil,tempfile
from pathlib import Path
from backends.gmic_backend import GMICBackend
from processors.texture_studio.gmic import generate_gmic_texture

# The G'MIC CLI is an optional external backend and is not installed on every
# machine (notably the CI runner), so tests that need a working binary skip
# instead of failing. Tests that assert graceful degradation always run.
HAS_GMIC = shutil.which("gmic") is not None
needs_gmic = unittest.skipUnless(HAS_GMIC, "gmic CLI not installed")

class GmicTests(unittest.TestCase):
 @needs_gmic
 def test_available_and_version(self):
  b=GMICBackend(); self.assertTrue(b.is_available()); self.assertIn('Version',b.get_version())
 @needs_gmic
 def test_cli_run(self):
  # Mirrors real usage (every call site passes -output).  Invoking G'MIC with
  # no -output stage makes it wait on its command pipeline and hang, which is
  # not what the backend is ever asked to do.
  with tempfile.TemporaryDirectory() as d:
   out=str(Path(d)/"out.png")
   b=GMICBackend(timeout=60); r=b.run('-input','16,16,1,1','-noise','5','-output',out)
   self.assertEqual(r.returncode,0); self.assertTrue(Path(out).exists())
 def test_missing_binary_version_is_safe(self):
  class No(GMICBackend):
   def __init__(self): super().__init__(path="/nonexistent/gmic")
  b=No(); self.assertFalse(b.is_available()); self.assertEqual(b.get_version(), "")

 def test_unavailable_fallback(self):
  class No(GMICBackend):
   def __init__(self): super().__init__(path='/nonexistent/gmic')
  im,mode=generate_gmic_texture('paper',64,48,{'intensity':20,'grain_size':3,'seed':1,'contrast':1,'brightness':0,'color_tint':(255,255,255,255)},No()); self.assertEqual(im.size,(64,48)); self.assertEqual(mode,'numpy-degraded')
 @needs_gmic
 def test_timeout_and_error(self):
  b=GMICBackend(timeout=.001)
  with self.assertRaises(TimeoutError): b.run('-input','2048,2048,1,1','-blur','20','-repeat','10')
  b=GMICBackend()
  with self.assertRaises(RuntimeError): b.run('-this-command-does-not-exist')
 def test_four_textures(self):
  p={'intensity':20,'grain_size':3,'seed':2,'contrast':1,'brightness':0,'color_tint':(255,255,255,255)}
  for n in ['paper','canvas','grunge','noise_blend']:
   im,mode=generate_gmic_texture(n,32,32,p); self.assertEqual(im.size,(32,32)); self.assertIn(mode,('gmic','numpy-degraded'))
 @needs_gmic
 def test_filter_cache_and_version_invalidation(self):
  with tempfile.TemporaryDirectory() as d:
   b=GMICBackend(cache_dir=d); first=b.list_filters(refresh=True); self.assertTrue((Path(d)/'filters.json').exists()); self.assertEqual(first,b.list_filters())
   p=Path(d)/'filters.json'; data=json.loads(p.read_text()); data['version']='old-version'; p.write_text(json.dumps(data)); refreshed=b.list_filters(); self.assertEqual(refreshed,first); self.assertEqual(json.loads(p.read_text())['version'],b.get_version())
if __name__=='__main__':unittest.main()
