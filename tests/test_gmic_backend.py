import unittest
from backends.gmic_backend import GMICBackend
from processors.texture_studio.gmic import generate_gmic_texture
class GmicTests(unittest.TestCase):
 def test_available_and_version(self):
  b=GMICBackend(); self.assertTrue(b.is_available()); self.assertIn('Version',b.get_version())
 def test_cli_run(self):
  b=GMICBackend(timeout=5); r=b.run('-input','16,16,1,1','-noise','5'); self.assertEqual(r.returncode,0)
 def test_unavailable_fallback(self):
  class No(GMICBackend):
   def __init__(self): super().__init__(path='/nonexistent/gmic')
  im,mode=generate_gmic_texture('paper',64,48,{'intensity':20,'grain_size':3,'seed':1,'contrast':1,'brightness':0,'color_tint':(255,255,255,255)},No()); self.assertEqual(im.size,(64,48)); self.assertEqual(mode,'numpy-degraded')
 def test_timeout_and_error(self):
  b=GMICBackend(timeout=.001)
  with self.assertRaises(TimeoutError): b.run('-input','2048,2048,1,1','-blur','20','-repeat','10')
  b=GMICBackend()
  with self.assertRaises(RuntimeError): b.run('-this-command-does-not-exist')
 def test_four_textures(self):
  p={'intensity':20,'grain_size':3,'seed':2,'contrast':1,'brightness':0,'color_tint':(255,255,255,255)}
  for n in ['paper','canvas','grunge','noise_blend']:
   im,mode=generate_gmic_texture(n,32,32,p); self.assertEqual(im.size,(32,32)); self.assertIn(mode,('gmic','numpy-degraded'))
if __name__=='__main__':unittest.main()
