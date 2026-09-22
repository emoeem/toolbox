from __future__ import annotations
import hashlib, json, secrets
from pathlib import Path
from PySide6.QtCore import Qt,QSettings,QRunnable,QThreadPool,Signal,QObject,QAbstractListModel,QModelIndex,QSize,QRect,QEventLoop,QTimer
from PySide6.QtGui import QImage,QPixmap,QColor,QPainter,QFont
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QSplitter,QListView,QLineEdit,QPushButton,QLabel,QFormLayout,QSpinBox,QDoubleSpinBox,QComboBox,QFileDialog,QInputDialog,QMessageBox,QStyledItemDelegate,QAbstractItemView
from processors.texture_studio.library import TextureLibrary
from processors.texture_studio.presets import BUILTIN_PRESETS
from processors.texture_studio.generators import generate
from app.widgets.labeled_slider import LabeledSlider
from app.widgets.color_field import ColorField
CACHE=Path.home()/'.cache/toolbox/texture_thumbs'
class RenderSignals(QObject): done=Signal(int,object)
class RenderJob(QRunnable):
    def __init__(self,rid,g,w,h,p,cancel): super().__init__(); self.rid=rid; self.g=g; self.w=w; self.h=h; self.p=p; self.cancel=cancel; self.signals=RenderSignals()
    def run(self):
        if self.cancel.is_set(): return
        try:
            p=dict(self.p); preference=p.pop('_backend_preference','auto'); result=generate(self.g,self.w,self.h,p,preference)
            if not self.cancel.is_set(): self.signals.done.emit(self.rid,result)
        except Exception as e:
            if not self.cancel.is_set(): self.signals.done.emit(self.rid,e)
class TextureLibraryModel(QAbstractListModel):
    def __init__(self,library,parent=None): super().__init__(parent); self.library=library; self.all_items=[]; self.items=[]; self.query=''; self.category='All'; self.cache_dir=CACHE; self.cache_dir.mkdir(parents=True,exist_ok=True); self.reload()
    def reload(self):
        self.beginResetModel(); self.all_items=self.library.list(); self._filter(); self.endResetModel()
    def _filter(self):
        q=self.query.lower(); c=self.category
        def cat(p):
            if c=='All': return True
            if c=='Noise': return not any(p.generator_id.startswith(x) for x in ('pattern:','gmic:','raymarch:'))
            if c=='Pattern': return p.generator_id.startswith('pattern:')
            if c=='GMIC': return p.generator_id.startswith('gmic:')
            if c=='Raymarch': return p.generator_id.startswith('raymarch:')
            return True
        self.items=[p for p in self.all_items if (not q or q in p.name.lower() or q in p.generator_id.lower() or any(q in t.lower() for t in p.tags)) and cat(p)]
    def set_filter(self,q=None,category=None):
        if q is not None:self.query=q
        if category is not None:self.category=category
        self.beginResetModel(); self._filter(); self.endResetModel()
    def rowCount(self,parent=QModelIndex()): return 0 if parent.isValid() else len(self.items)
    def data(self,index,role=Qt.DisplayRole):
        if not index.isValid() or index.row()>=len(self.items): return None
        p=self.items[index.row()]
        if role==Qt.DisplayRole:return ('★ ' if p.generator_id in self.library.favorites else '')+p.name
        if role==Qt.UserRole:return p
        return None
    def thumb_key(self,p): return hashlib.sha256(json.dumps([p.generator_id,p.params],sort_keys=True,default=str).encode()).hexdigest()[:24]+'.png'
    def thumbnail(self,p):
        path=self.cache_dir/self.thumb_key(p)
        if path.exists(): return QPixmap(str(path))
        try:
            im=generate(p.generator_id,128,80,p.params); im.save(path,'PNG'); return QPixmap.fromImage(QImage(str(path)))
        except Exception:return QPixmap()
class TextureLibraryDelegate(QStyledItemDelegate):
    def sizeHint(self,opt,index): return QSize(190,104)
    def paint(self,painter,opt,index):
        painter.save(); r=opt.rect.adjusted(4,4,-4,-4); item=index.data(Qt.UserRole); model=index.model(); thumb=model.thumbnail(item)
        if not thumb.isNull(): painter.drawPixmap(r.left(),r.top(),r.width(),78,thumb)
        if opt.state & opt.State_Selected: painter.fillRect(QRect(r.left(),r.bottom()-22,r.width(),22),QColor(90,70,120,190))
        painter.setPen(QColor('white') if opt.state & opt.State_Selected else QColor('lightgray')); painter.drawText(QRect(r.left()+6,r.bottom()-20,r.width()-12,18),Qt.AlignLeft|Qt.AlignVCenter,index.data(Qt.DisplayRole)); painter.restore()
class TextureStudioPanel(QWidget):
    def __init__(self,settings:QSettings,parent=None):
        super().__init__(parent); self.settings=settings; self.library=TextureLibrary(Path(settings.value('texture/library',str(Path.home()/'.local/share/toolbox/textures')))); self.pool=QThreadPool(self); self.request_id=0; self.cancel_token=__import__('threading').Event(); self._last=None; self._build(); self._select_row(0)
    def _build(self):
        root=QVBoxLayout(self); split=QSplitter(Qt.Horizontal); root.addWidget(split)
        left=QWidget(); ll=QVBoxLayout(left); self.search=QLineEdit(); self.search.setPlaceholderText('搜索名称 / 分类 / 标签…'); ll.addWidget(self.search); self.category=QComboBox(); self.category.addItems(['All','Noise','Pattern','GMIC','Raymarch']); ll.addWidget(self.category); self.backend_choice=QComboBox(); self.backend_choice.addItems(['自动 / GMIC native','优先 numpy 降级']); ll.addWidget(self.backend_choice); self.backend_choice.currentIndexChanged.connect(lambda _: self._render()); self.model=TextureLibraryModel(self.library); self.view=QListView(); self.view.setModel(self.model); self.view.setItemDelegate(TextureLibraryDelegate(self.view)); self.view.setIconSize(QSize(180,78)); self.view.setSelectionMode(QAbstractItemView.SingleSelection); ll.addWidget(self.view); split.addWidget(left)
        center=QWidget(); cl=QVBoxLayout(center); self.preview=QLabel(alignment=Qt.AlignCenter); self.preview.setMinimumSize(480,360); cl.addWidget(self.preview,1); self.status=QLabel(); cl.addWidget(self.status); split.addWidget(center)
        self.right=QWidget(); self.form=QFormLayout(self.right); split.addWidget(self.right); split.setSizes([250,700,380]);
        self.search.textChanged.connect(lambda q:self.model.set_filter(q=q)); self.category.currentTextChanged.connect(lambda c:self.model.set_filter(category=c)); self.view.clicked.connect(lambda i:self._select_row(i.row()))
        bar=QHBoxLayout(); self.fav=QPushButton('☆ 收藏'); self.random=QPushButton('随机 Seed'); self.reset=QPushButton('重置'); self.save=QPushButton('保存 Preset'); self.export=QPushButton('导出')
        for b in (self.fav,self.random,self.reset,self.save,self.export):bar.addWidget(b)
        root.addLayout(bar); self.fav.clicked.connect(self._toggle_fav); self.random.clicked.connect(self._random_seed); self.reset.clicked.connect(self._reset); self.save.clicked.connect(self._save); self.export.clicked.connect(self._export)
    def _select_row(self,row):
        if row<0 or row>=self.model.rowCount():return
        self.current=self.model.items[row]; self._make_form(); self._render()
    def _make_form(self):
        while self.form.count(): w=self.form.takeAt(0).widget(); w and w.deleteLater()
        self.params={}; d=self.current.params.copy()
        if self.current.generator_id.startswith('raymarch:'):
            keys=['steps','max_distance','surface_threshold','light_x','light_y','light_z','ambient','diffuse','specular','fresnel','gradient','seed']
            ranges={'steps':(8,256,1,0),'max_distance':(1,20,.1,1),'surface_threshold':(.0002,.05,.0005,4),'light_x':(-1,1,.01,2),'light_y':(-1,1,.01,2),'light_z':(-1,1,.01,2),'ambient':(0,1,.01,2),'diffuse':(0,2,.01,2),'specular':(0,2,.01,2),'fresnel':(0,1,.01,2),'gradient':(0,1,.01,2),'seed':(0,2147483647,1,0)}
            ld=d.get('light_direction',(0.55,0.7,0.45)); d.update({'light_x':ld[0],'light_y':ld[1],'light_z':ld[2]})
        elif self.current.generator_id.startswith('pattern:'):
            keys=['size','spacing','angle','anti_alias']; ranges={'size':(1,512,1,0),'spacing':(0,512,1,0),'angle':(-180,180,1,0)}
        else:
            keys=['scale','octaves','persistence','lacunarity','seed','contrast','brightness','warp']
            ranges={'scale':(1,512,1,0),'octaves':(1,12,1,0),'persistence':(0,1,.01,2),'lacunarity':(.1,8,.05,2),'seed':(0,2147483647,1,0),'contrast':(0,4,.01,2),'brightness':(-1,1,.01,2),'warp':(0,1,.01,2)}
        for k in keys:
            if k=='anti_alias':
                from PySide6.QtWidgets import QCheckBox
                c=QCheckBox('抗锯齿'); c.setChecked(bool(d.get(k,True))); c.stateChanged.connect(self._render)
            else:
                lo,hi,step,dec=ranges[k]; c=LabeledSlider(k,lo,hi,d[k],step,dec); c.valueChanged.connect(self._render)
            self.params[k]=c; self.form.addRow(c)
        if self.current.generator_id.startswith('raymarch:'):
            for k,v in [('color_a',(75,105,210)),('color_b',(225,105,155)),('background',(10,12,22))]:
                cf=ColorField(k,QColor(*v)); cf.colorChanged.connect(lambda c:self._render()); self.params[k]=cf; self.form.addRow(cf)
        if self.current.generator_id.startswith('pattern:'):
            for k,v in [('color_a',(35,35,45)),('color_b',(210,210,220)),('background',(20,20,25))]:
                cf=ColorField(k,QColor(*v)); cf.colorChanged.connect(lambda c,kk=k:self._color_changed(kk,c)); self.params[k]=cf; self.form.addRow(cf)
    def _color_changed(self,k,c): self._render()
    def _values(self):
        out={}
        for k,c in self.params.items():
            if isinstance(c,ColorField): q=c.color(); out[k]=(q.red(),q.green(),q.blue(),q.alpha())
            elif hasattr(c,'value'): out[k]=c.value()
            elif hasattr(c,'isChecked'): out[k]=c.isChecked()
        if self.current.generator_id.startswith('raymarch:'):
            out['light_direction']=(out.pop('light_x'),out.pop('light_y'),out.pop('light_z'))
        return out
    def _render(self):
        if not hasattr(self,'current'):return
        self.request_id+=1; rid=self.request_id; self.cancel_token.set(); self.cancel_token=__import__('threading').Event(); preference='numpy' if self.backend_choice.currentIndex()==1 else 'auto'; params=self._values(); params['_backend_preference']=preference; job=RenderJob(rid,self.current.generator_id,512,384,params,self.cancel_token); job.signals.done.connect(self._done); self.pool.start(job); self.status.setText(f'生成中… #{rid}')
    def _done(self,rid,result):
        if rid!=self.request_id:return
        if isinstance(result,Exception):self.status.setText('❌ '+str(result));return
        rgba=result.convert('RGBA'); data=rgba.tobytes('raw','RGBA'); img=QImage(data,rgba.width,rgba.height,QImage.Format_RGBA8888).copy(); self.preview.setPixmap(QPixmap.fromImage(img).scaled(self.preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation)); self._last=result; self.status.setText(f'✓ Preview #{rid}')
    def _toggle_fav(self): self.library.toggle_favorite(self.current.generator_id); self.model.reload()
    def _random_seed(self):
        if 'seed' in self.params:self.params['seed'].setValue(secrets.randbelow(2147483647))
    def _reset(self): self._make_form(); self._render()
    def _save(self):
        name,_=QInputDialog.getText(self,'保存 Preset','名称')
        if name:
            from processors.texture_studio.model import TexturePreset
            p=TexturePreset(name,self.current.generator_id,self._values()); self.library.save(p); self.model.reload()
    def _export(self):
        if self._last is None:return
        path=QFileDialog.getSaveFileName(self,'导出纹理','texture.png','PNG (*.png);;JPEG (*.jpg *.jpeg);;WebP (*.webp)')[0]
        if path:
            self._last.save(path,quality=95 if Path(path).suffix.lower() in ('.jpg','.jpeg','.webp') else None); self.status.setText('✓ '+path)
    def closeEvent(self,event): self.cancel_token.set(); self.pool.waitForDone(5000); super().closeEvent(event)
