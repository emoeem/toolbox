from __future__ import annotations
import re
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QSplitter,QPlainTextEdit,QListWidget,QListWidgetItem,QLineEdit,QPushButton,QLabel,QFormLayout,QDoubleSpinBox,QSpinBox,QComboBox,QCheckBox,QFileDialog,QMessageBox,QGroupBox,QColorDialog
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram, QOpenGLTexture, QOpenGLBuffer, QOpenGLVertexArrayObject
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QImage, QPainter
from processors.shader_studio import ShaderLibrary, ShaderPreset, parse_uniforms, validate_glsl

VERTEX='''#version 330 core\nlayout(location=0) in vec2 a_pos;\nout vec2 v_uv;\nvoid main(){ v_uv=(a_pos+1.0)*0.5; gl_Position=vec4(a_pos,0.0,1.0); }'''

class GLSLHighlighter(QSyntaxHighlighter):
    def __init__(self,doc): super().__init__(doc); self.rules=[]
    def _fmt(self,color,bold=False):
        f=QTextCharFormat(); f.setForeground(QColor(color));
        if bold: f.setFontWeight(QFont.Bold)
        return f
    def highlightBlock(self,text):
        for pat,color,bold in [(r'\\b(void|vec[234]|float|int|bool|sampler2D|uniform|in|out|const|return|if|else|for|while)\\b','#cba6f7',True),(r'\\b(gl_Position|gl_FragCoord|texture|mix|dot|sin|cos|pow|smoothstep|clamp)\\b','#89b4fa',False),(r'//.*$','#6c7086',False),(r'#[A-Za-z]+','#f9e2af',False),(r'\\b\\d+(?:\\.\\d+)?f?\\b','#a6e3a1',False)]:
            for m in re.finditer(pat,text): self.setFormat(m.start(),m.end()-m.start(),self._fmt(color,bold))

class LineEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__(); self.setFont(QFont('Maple Mono',11)); self.setTabStopDistance(32); self.highlighter=GLSLHighlighter(self.document())
        self.blockCountChanged.connect(lambda _: self.setViewportMargins(48,0,0,0)); self.updateRequest.connect(self._update); self._update_gutter_width()
    def _update_gutter_width(self): self.setViewportMargins(48,0,0,0)
    def _update(self,rect,dy):
        if dy: self._gutter.scroll(0,dy)
        else: self._gutter.update(0,rect.y(),48,rect.height())
    def resizeEvent(self,e): super().resizeEvent(e); self._gutter= getattr(self,'_gutter',None) or QWidget(self); self._gutter.setGeometry(0,0,48,self.height()); self._gutter.paintEvent=self._paint_gutter; self._gutter.show()
    def _paint_gutter(self,event):
        p=QPainter(self._gutter); p.fillRect(event.rect(),QColor('#181825')); block=self.firstVisibleBlock(); n=block.blockNumber(); top=int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top<=event.rect().bottom():
            if block.isVisible() and top+int(self.blockBoundingRect(block).height())>=event.rect().top(): p.setPen(QColor('#6c7086')); p.drawText(4,top,40,20,Qt.AlignRight,str(n+1))
            block=block.next(); top+=int(self.blockBoundingRect(block).height()); n+=1
        p.end()

class ShaderPreview(QOpenGLWidget):
    compileError=Signal(str); compiled=Signal(bool)
    def __init__(self):
        super().__init__(); self.program=None; self.texture=None; self.source=''; self.time=0.0; self.paused=False; self.timer=QTimer(self); self.timer.timeout.connect(self._tick); self.timer.start(33); self.setMinimumSize(420,300); self.vbo=None; self.vao=None
    def _tick(self):
        if not self.paused: self.time+=1/30; self.update()
    def set_source(self,source,uniforms=None): self.source=source; self.uniform_values=uniforms or {}; self.program=None; self.makeCurrent(); self._compile(); self.doneCurrent(); self.update()
    def _fragment(self):
        import re
        src=self.source
        uniforms='\n'.join(re.findall(r'^\s*uniform\s+(?:float|int|bool|vec2|vec3|vec4|sampler2D)\s+[A-Za-z_]\w*\s*(?:=\s*[^;]+)?\s*;',src,re.M))
        src=re.sub(r'^\s*uniform\s+(?:float|int|bool|vec2|vec3|vec4|sampler2D)\s+[A-Za-z_]\w*\s*(?:=\s*[^;]+)?\s*;\s*$','',src,flags=re.M)
        return '#version 330 core\nin vec2 v_uv;\nout vec4 fragColor;\nuniform sampler2D u_image;\nuniform float u_time;\nuniform vec2 u_resolution;\n'+uniforms+'\nvoid main(){ vec2 textureCoordinate=v_uv;\n'+ '\n'.join(' '+x for x in src.splitlines()) +'\n}'
    def initializeGL(self):
        from PySide6.QtGui import QOpenGLBuffer, QOpenGLVertexArrayObject
        self.vbo=QOpenGLBuffer(QOpenGLBuffer.VertexBuffer); self.vbo.create(); self.vbo.bind(); import array; self.vbo.allocate(array.array('f',[-1,-1,3,-1,-1,3]).tobytes(),24); self.vbo.release(); self.vao=QOpenGLVertexArrayObject(); self.vao.create(); self._make_default_texture(); self._compile()
    def _make_default_texture(self):
        img=QImage(512,512,QImage.Format_RGBA8888);
        for y in range(512):
            for x in range(512):
                v=230 if ((x//32+y//32)%2==0) else 80; img.setPixelColor(x,y,QColor(v,v,v,255))
        self.texture=QOpenGLTexture(img.mirrored()); self.texture.setMinificationFilter(QOpenGLTexture.Linear); self.texture.setMagnificationFilter(QOpenGLTexture.Linear); self.texture.setWrapMode(QOpenGLTexture.ClampToEdge)
    def _compile(self):
        if not self.source.strip() or not self.context(): return
        p=QOpenGLShaderProgram(self.context())
        if not p.addShaderFromSourceCode(QOpenGLShader.Vertex,VERTEX) or not p.addShaderFromSourceCode(QOpenGLShader.Fragment,self._fragment()) or not p.link():
            self.compileError.emit(p.log() or 'GLSL 编译/链接失败'); self.compiled.emit(False); self.program=None; return
        self.program=p; self.compiled.emit(True)
    def resizeGL(self,w,h): self.update()
    def paintGL(self):
        f=self.context().functions(); f.glClearColor(0.06,0.06,0.09,1); f.glClear(0x00004000)
        if self.program is None: return
        self.program.bind(); self.program.setUniformValue('u_time',float(self.time)); self.program.setUniformValue('u_resolution',float(self.width()),float(self.height()))
        for name,value in self.uniform_values.items():
            try:
                if isinstance(value,float): self.program.setUniformValue(name,value)
                elif isinstance(value,int): self.program.setUniformValue(name,value)
                elif isinstance(value,(list,tuple)) and len(value)==2: self.program.setUniformValue(name,float(value[0]),float(value[1]))
                elif isinstance(value,(list,tuple)) and len(value)==3: self.program.setUniformValue(name,float(value[0]),float(value[1]),float(value[2]))
                elif isinstance(value,(list,tuple)) and len(value)==4: self.program.setUniformValue(name,float(value[0]),float(value[1]),float(value[2]),float(value[3]))
            except Exception: pass
        if self.texture: self.texture.bind(0); self.program.setUniformValue('u_image',0)
        self.vbo.bind(); loc=self.program.attributeLocation('a_pos'); self.program.enableAttributeArray(loc); self.program.setAttributeBuffer(loc,0x1406,0,2,8); f.glDrawArrays(0x0004,0,3); self.program.disableAttributeArray(loc); self.vbo.release(); self.program.release()
    def set_image(self,image):
        self.makeCurrent();
        if self.texture: self.texture.destroy()
        if not image.isNull(): self.texture=QOpenGLTexture(image.mirrored()); self.texture.setMinificationFilter(QOpenGLTexture.Linear); self.texture.setMagnificationFilter(QOpenGLTexture.Linear); self.texture.setWrapMode(QOpenGLTexture.ClampToEdge)
        else: self._make_default_texture()
        self.doneCurrent(); self.update()
    def grab_image(self): return self.grabFramebuffer()

class ShaderStudioPanel(QWidget):
    def __init__(self, settings, source_image=None, parent=None):
        super().__init__(parent); self.settings=settings; self.library=ShaderLibrary(Path(settings.value('shader/library',str(Path.home()/'.local/share/toolbox/shaders')))); self.current=None; self.preview=ShaderPreview(); self._preview_timer=QTimer(self); self._preview_timer.setSingleShot(True); self._preview_timer.timeout.connect(self._refresh); self._build(); self._load_builtin(0)
        if source_image is not None: self.preview.set_image(source_image)
    def _build(self):
        root=QVBoxLayout(self); split=QSplitter(Qt.Horizontal); root.addWidget(split)
        left=QWidget(); ll=QVBoxLayout(left); self.search=QLineEdit(); self.search.setPlaceholderText('搜索 Shader / 标签…'); ll.addWidget(self.search); self.list=QListWidget(); ll.addWidget(self.list); self.search.textChanged.connect(self._filter); self.list.currentRowChanged.connect(self._load_row); split.addWidget(left)
        center=QWidget(); cl=QVBoxLayout(center); cl.addWidget(self.preview,2); self.status=QLabel(''); cl.addWidget(self.status); self.editor=LineEditor(); cl.addWidget(self.editor,3); split.addWidget(center)
        right=QWidget(); rl=QVBoxLayout(right); form=QFormLayout(); self.name=QLineEdit(); form.addRow('名称',self.name); self.res=QComboBox(); self.res.addItems(['预览分辨率','640×480','1280×720','1920×1080']); form.addRow('分辨率',self.res); self.play=QCheckBox('播放时间 uniform'); self.play.setChecked(True); form.addRow(self.play); rl.addLayout(form); self.uniform_box=QGroupBox('Uniform 参数'); self.uniform_layout=QFormLayout(self.uniform_box); rl.addWidget(self.uniform_box); btn=QHBoxLayout();
        for text,fn in [('验证',self.validate),('导入',self.import_preset),('导出',self.export_preset),('保存',self.save_preset),('删除',self.delete_preset),('导出图片',self.export_image)]: b=QPushButton(text); b.clicked.connect(fn); btn.addWidget(b)
        rl.addLayout(btn); rl.addStretch(); split.addWidget(right); split.setSizes([220,720,360]); self.editor.textChanged.connect(self._schedule); self.name.textChanged.connect(self._schedule); self.preview.compileError.connect(lambda e:self.status.setText('❌ '+e)); self.preview.compiled.connect(lambda ok:self.status.setText('✓ GLSL 编译通过' if ok else '❌ GLSL 编译失败'))
        self._populate()
    def _populate(self):
        self.list.clear(); q=self.search.text().lower(); self.presets=[p for p in self.library.list() if not q or q in p.name.lower() or any(q in t.lower() for t in p.tags)]
        for p in self.presets: self.list.addItem(QListWidgetItem(p.name))
    def _filter(self): self._populate()
    def _load_row(self,row):
        if row<0 or row>=len(self.presets): return
        p=self.presets[row]; self.current=p; self.name.setText(p.name); self.editor.blockSignals(True); self.editor.setPlainText(p.source); self.editor.blockSignals(False); self._render_uniforms(p); self._refresh()
    def _load_builtin(self,i):
        self.presets=self.library.list(); self.list.setCurrentRow(min(i,len(self.presets)-1))
    def _render_uniforms(self,preset):
        while self.uniform_layout.count(): w=self.uniform_layout.takeAt(0).widget(); w and w.deleteLater()
        self.controls={}
        for u in parse_uniforms(preset.source):
            if u.glsl_type=='float': c=QDoubleSpinBox(); c.setRange(float(u.minimum if u.minimum is not None else -100),float(u.maximum if u.maximum is not None else 100)); c.setSingleStep(float(u.step or .01)); c.setValue(float(u.default)); c.valueChanged.connect(self._schedule)
            elif u.glsl_type=='int': c=QSpinBox(); c.setRange(int(u.minimum if u.minimum is not None else -10000),int(u.maximum if u.maximum is not None else 10000)); c.setValue(int(u.default)); c.valueChanged.connect(self._schedule)
            else: c=QLineEdit(str(u.default))
            self.controls[u.name]=c; self.uniform_layout.addRow(u.label or u.name,c)
    def _schedule(self): self._preview_timer.start(120)
    def _refresh(self):
        src=self.editor.toPlainText(); ok,msg=validate_glsl(src)
        if not ok: self.status.setText('⚠ '+msg); return
        values={}
        for name,c in getattr(self,'controls',{}).items():
            if hasattr(c,'value'): values[name]=c.value()
        self.preview.set_source(src,values)
    def validate(self):
        ok,msg=validate_glsl(self.editor.toPlainText()); self.status.setText(('✓ ' if ok else '❌ ')+ (msg or 'GLSL 验证通过'))
    def save_preset(self):
        p=ShaderPreset(self.name.text().strip() or 'Untitled',self.editor.toPlainText()); ok,msg=validate_glsl(p.source)
        if not ok: QMessageBox.warning(self,'Shader 无法保存',msg); return
        self.library.save(p); self.current=p; self._populate(); self.status.setText('✓ 已保存到用户 Shader 库')
    def delete_preset(self):
        if self.current and self.current.name not in [p.name for p in self.library.list()[:3]]: self.library.delete(self.current.name); self._populate(); self.status.setText('已删除')
    def import_preset(self):
        path=QFileDialog.getOpenFileName(self,'导入 Shader','.','Shader preset (*.json);;GLSL (*.glsl)')[0]
        if not path:return
        try:
            if path.endswith('.json'): p=self.library.import_json(path)
            else: p=ShaderPreset(Path(path).stem,Path(path).read_text(encoding='utf-8'))
            self.library.save(p); self._populate(); self.status.setText('✓ 已导入')
        except Exception as e: QMessageBox.warning(self,'导入失败',str(e))
    def export_preset(self):
        if not self.current:return
        path=QFileDialog.getSaveFileName(self,'导出 Shader',self.current.name+'.json','JSON preset (*.json);;GLSL (*.glsl)')[0]
        if not path:return
        if path.endswith('.glsl'): Path(path).write_text(self.editor.toPlainText(),encoding='utf-8')
        else:self.library.export_json(ShaderPreset(self.name.text(),self.editor.toPlainText()),path)
    def export_image(self):
        path=QFileDialog.getSaveFileName(self,'导出 Shader 图片','shader.png','PNG (*.png)')[0]
        if path:self.preview.grab_image().save(path)
