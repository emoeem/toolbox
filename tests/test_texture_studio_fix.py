import tempfile,unittest
from pathlib import Path
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from app.panels.texture_studio import TextureStudioPanel,TextureLibraryModel
from app.widgets.labeled_slider import LabeledSlider
from app.widgets.color_field import ColorField
from processors.texture_studio.library import TextureLibrary
class TextureFixTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
 def test_slider_bidirectional(self):
  s=LabeledSlider('x',0,10,2,.5,1); s.setValue(4.5); self.assertAlmostEqual(s.value(),4.5); s.slider.setValue(70); self.assertAlmostEqual(s.value(),7)
 def test_color_field_alpha(self):
  from PySide6.QtGui import QColor
  c=ColorField('x',QColor(17,34,51,68),True); self.assertEqual(c.color().alpha(),68); self.assertEqual(c.color().red(),17)
 def test_model_search_and_thumbnail_cache(self):
  with tempfile.TemporaryDirectory() as d:
   lib=TextureLibrary(Path(d)); m=TextureLibraryModel(lib); self.assertEqual(m.rowCount(),15); m.set_filter('worley'); self.assertEqual(m.rowCount(),1); p=m.items[0]; first=m.thumbnail(p); second=m.thumbnail(p); self.assertFalse(first.isNull()); self.assertEqual(first.toImage(),second.toImage()); self.assertTrue((m.cache_dir/m.thumb_key(p)).exists())
 def test_request_ids_discard_stale(self):
  p=TextureStudioPanel(QSettings('ToolboxTest','TextureFix')); p._select_row(0); p.request_id=2; p._done(1,object()); self.assertEqual(p.request_id,2); p.close()
if __name__=='__main__':unittest.main()
