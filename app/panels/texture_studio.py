from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt,QSettings,QTimer,QRunnable,QThreadPool,Signal,QObject
from PySide6.QtGui import QImage,QPixmap,QColor
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QSplitter,QListWidget,QListWidgetItem,QLineEdit,QPushButton,QLabel,QFormLayout,QDoubleSpinBox,QSpinBox,QGroupBox,QSlider,QComboBox,QColorDialog,QFileDialog,QMessageBox,QCheckBox
from processors.texture_studio.library import TextureLibrary
from processors.texture_studio.presets import BUILTIN_PRESETS
from processors.texture_studio.generators import generate
class Signals(QObject): done=Signal(object)
class Job(QRunnable):
 def __init__(self,g,w,h,p): super().__init__(); self.g,self.w,self.h,self.p=g,w,h,p; self.signals=Signals()
 def run(self):
  try:self.signals.done.emit(generate(self.g,self.w,self.h,self.p))
  except Exception as e:self.signals.done.emit(e)
class TextureStudioPanel(QWidget):
 def __init__(self,settings:QSettings,parent=None):
  super().__init__(parent); self.settings=settings; self.library=TextureLibrary(Path(settings.value('texture/library',str(Path.home()/'.local/share/toolbox/textures')))); self.pool=QThreadPool(self); self.specs=list(self.library.list()); self._build(); self._select(0)
 def _build(self):
  root=QVBoxLayout(self); split=QSplitter(Qt.Horizontal); root.addWidget(split)
  left=QWidget(); ll=QVBoxLayout(left); self.search=QLineEdit(); self.search.setPlaceholderText('搜索名称 / 分类 / 标签…'); ll.addWidget(self.search); self.category=QComboBox(); self.category.addItems(['All','Noise','Pattern']); ll.addWidget(self.category); self.list=QListWidget(); ll.addWidget(self.list); split.addWidget(left)
  center=QWidget(); cl=QVBoxLayout(center); self.preview=QLabel(alignment=Qt.AlignCenter); self.preview.setMinimumSize(480,360); self.preview.setText('Preview'); cl.addWidget(self.preview,1); self.status=QLabel(); cl.addWidget(self.status); split.addWidget(center)
  right=QWidget(); self.form=QFormLayout(right); self.params={}; split.addWidget(right); split.setSizes([220,700,330]); self.search.textChanged.connect(self._refresh_list); self.category.currentTextChanged.connect(self._refresh_list); self.list.currentRowChanged.connect(self._select); self._refresh_list()
  bar=QHBoxLayout(); self.fav=QPushButton('☆ 收藏'); self.random=QPushButton('随机 Seed'); self.reset=QPushButton('重置'); self.save=QPushButton('保存 Preset'); self.export=QPushButton('导出');
  for b in (self.fav,self.random,self.reset,self.save,self.export): bar.addWidget(b)
  root.addLayout(bar); self.fav.clicked.connect(self._toggle_fav); self.random.clicked.connect(self._random_seed); self.reset.clicked.connect(self._reset); self.save.clicked.connect(self._save); self.export.clicked.connect(self._export)
 def _refresh_list(self):
  q=self.search.text().lower(); cat=self.category.currentText(); self.specs=[p for p in self.library.list() if (not q or q in p.name.lower() or q in p.generator_id.lower() or any(q in t.lower() for t in p.tags)) and (cat=='All' or (cat=='Noise' and not p.generator_id.startswith('pattern:')) or (cat=='Pattern' and p.generator_id.startswith('pattern:')) )]; self.list.blockSignals(True); self.list.clear(); [self.list.addItem(QListWidgetItem(('★ ' if p.generator_id in self.library.favorites else '')+p.name)) for p in self.specs]; self.list.blockSignals(False)
 def _select(self,row):
  if row<0 or row>=len(self.specs): return
  self.current=self.specs[row]; self._make_form(); self._render()
 def _make_form(self):
  while self.form.count(): w=self.form.takeAt(0).widget(); w and w.deleteLater()
  self.params={}; d=self.current.params.copy(); keys=['scale','octaves','persistence','lacunarity','seed','contrast','brightness','warp'] if not self.current.generator_id.startswith('pattern:') else ['size','spacing','angle']
  for k in keys:
   c=QDoubleSpinBox() if isinstance(d.get(k),float) else QSpinBox(); c.setRange(-100000,100000); c.setValue(d[k]); c.valueChanged.connect(self._render); self.params[k]=c; self.form.addRow(k,c)
  if self.current.generator_id.startswith('pattern:'):
   for k,v in [('color_a',(35,35,45)),('color_b',(210,210,220)),('background',(20,20,25))]:
    b=QPushButton(str(v)); b.clicked.connect(lambda _,kk=k,bb=b:self._color(kk,bb)); self.params[k]=v; self.form.addRow(k,b)
 def _color(self,k,b):
  c=QColorDialog.getColor(parent=self)
  if c.isValid(): self.params[k]=(c.red(),c.green(),c.blue()); b.setText(str(self.params[k])); self._render()
 def _values(self): return {k:(c.value() if hasattr(c,'value') else v) for k,(c,v) in [(k,(c,self.current.params.get(k))) for k,c in self.params.items()]}
 def _render(self):
  if not hasattr(self,'current'):return
  p=self._values(); job=Job(self.current.generator_id,512,384,p); job.signals.done.connect(self._done); self.pool.start(job)
 def _done(self,result):
  if isinstance(result,Exception): self.status.setText('❌ '+str(result)); return
  rgba=result.convert('RGBA'); data=rgba.tobytes('raw','RGBA'); img=QImage(data,rgba.width,rgba.height,QImage.Format_RGBA8888).copy(); self.preview.setPixmap(QPixmap.fromImage(img));
  if not self.preview.pixmap().isNull(): self.preview.setPixmap(self.preview.pixmap().scaled(self.preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation)); self._last=result; self.status.setText('✓ Preview updated')
 def _toggle_fav(self): self.library.toggle_favorite(self.current.generator_id); self._refresh_list()
 def _random_seed(self):
  import secrets
  if 'seed' in self.params:self.params['seed'].setValue(secrets.randbelow(2_147_483_647))
 def _reset(self):
  for k,c in self.params.items():
   if hasattr(c,'setValue'): c.setValue(self.current.params.get(k,0))
 def _save(self):
  from processors.texture_studio.model import TexturePreset
  name,_=__import__('PySide6.QtWidgets',fromlist=['QInputDialog']).QInputDialog.getText(self,'保存 Preset','名称')
  if name:self.library.save(TexturePreset(name,self.current.generator_id,self._values())); self._refresh_list()
 def _export(self):
  if not hasattr(self,'_last'): return
  path=QFileDialog.getSaveFileName(self,'导出纹理','texture.png','PNG (*.png);;JPEG (*.jpg *.jpeg);;WebP (*.webp)')[0]
  if path:
   ext=Path(path).suffix.lower(); self._last.save(path,quality=95 if ext in ('.jpg','.jpeg','.webp') else None); self.status.setText('✓ '+path)

 def closeEvent(self,event):
  self.pool.waitForDone(5000); super().closeEvent(event)
