from __future__ import annotations
import shutil,time
from pathlib import Path
from .gmic_backend import GMICBackend
class BackendInfo:
    def __init__(self,name,available,version,path,last_checked,usage=0): self.name=name; self.available=available; self.version=version; self.path=path; self.last_checked=last_checked; self.usage=usage

INSTALL_HINTS = {
    'GMIC': '安装 gmic', 'ImageMagick': '安装 imagemagick', 'ffmpeg': '安装 ffmpeg',
    'exiftool': '安装 perl-image-exiftool', 'potrace': '安装 potrace', 'tesseract': '安装 tesseract + 语言包',
}

def inspect_backends(usage=None):
    usage=usage or {}; now=time.time(); out=[]
    g=GMICBackend(); out.append(BackendInfo('GMIC',g.is_available(),g.get_version(),g.get_path(),now,usage.get('GMIC',0)))
    for name,cmd in [('ImageMagick','magick'),('ffmpeg','ffmpeg'),('exiftool','exiftool'),('potrace','potrace'),('tesseract','tesseract')]:
        path=shutil.which(cmd); version=''
        if path:
            try:
                import subprocess; p=subprocess.run([path,'--version'],capture_output=True,text=True,timeout=3,check=False); version=(p.stdout or p.stderr).splitlines()[0] if (p.stdout or p.stderr) else ''
            except Exception: pass
        out.append(BackendInfo(name,bool(path),version,path or '',now,usage.get(name,0)))
    return out
