from __future__ import annotations
from pathlib import Path
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

SANS=('MiSans','MiSans Normal','MiSans Regular','Noto Sans CJK SC','Source Han Sans SC','WenQuanYi Zen Hei','sans-serif')
MONO=('Maple Mono','JetBrains Mono','Fira Code','monospace')

def _families(): return set(QFontDatabase.families())

def resolve_family(preferred, candidates):
    fam=_families();
    for x in [preferred,*candidates]:
        if x and x in fam:return x,'system'
    return 'sans-serif','system'

def ensure_packaged_misans():
    loaded=[]
    for root in [Path.home()/'.local/share/fonts',Path('/usr/share/fonts'),Path.home()/'.fonts',Path(__file__).resolve().parent.parent/'assets/fonts']:
        if not root.exists(): continue
        for f in root.rglob('*MiSans*.otf'):
            if 'MiSans' in f.name and QFontDatabase.addApplicationFont(str(f))>=0: loaded.append(f)
    return loaded

def apply(app, settings):
    ensure_packaged_misans()
    preferred=settings.value('font/family','MiSans')
    family,source=resolve_family(preferred,SANS[1:])
    size=int(settings.value('font/size',11)); mono=settings.value('font/mono','Maple Mono')
    mono_family,_=resolve_family(mono,MONO[1:])
    font=QFont(family,size); font.setStyleHint(QFont.SansSerif); font.setStyleStrategy(QFont.PreferAntialias); font.setHintingPreference(QFont.PreferFullHinting); app.setFont(font)
    return {'family':family,'source':source,'size':size,'mono':mono_family}
