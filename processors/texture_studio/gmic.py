from __future__ import annotations
import numpy as np
from PIL import Image,ImageFilter,ImageChops,ImageEnhance
from backends.gmic_backend import GMICBackend

def _fallback(name,w,h,p):
    rng=np.random.default_rng(int(p.get('seed',0))); grain=max(1,int(p.get('grain_size',4))); small=rng.random((max(2,h//grain),max(2,w//grain))).astype('float32'); im=Image.fromarray(np.uint8(small*255),'L').resize((w,h),Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(max(.1,grain/3)))
    if name=='paper': im=ImageChops.multiply(im,Image.fromarray(np.uint8(rng.random((h,w))*255),'L'))
    elif name=='canvas': im=ImageChops.multiply(im,Image.new('L',(w,h),235)); im=im.filter(ImageFilter.UnsharpMask(radius=2,percent=120))
    elif name=='grunge': im=ImageEnhance.Contrast(im).enhance(2.2)
    else: im=ImageChops.screen(im,Image.fromarray(np.uint8(rng.random((h,w))*255),'L'))
    im=ImageEnhance.Contrast(im).enhance(float(p.get('contrast',1))); im=ImageEnhance.Brightness(im).enhance(max(.01,1+float(p.get('brightness',0))))
    tint=p.get('color_tint',(255,255,255,255)); base=Image.new('RGB',(w,h),tuple(tint[:3])); return Image.composite(base,Image.new('RGB',(w,h),(0,0,0)),im.convert('L'))

def _gmic_noise(w,h,p,kind,b):
    import tempfile
    if not b.is_available(): return None
    # Verified portable G'MIC primitives. They intentionally avoid distro-specific custom filters.
    seed=int(p.get('seed',0)); sigma=max(1,float(p.get('intensity',25))); grain=max(0.5,float(p.get('grain_size',3)))
    with tempfile.NamedTemporaryFile(suffix='.png',dir=b.cache_dir,delete=False) as f: out=f.name
    try:
        cmd=['-input',f'{w},{h},1,1','-noise',str(sigma)]
        if kind=='paper': cmd += ['-blur',str(grain)]
        elif kind=='canvas': cmd += ['-blur',str(max(.5,grain/2)),'-sharpen',str(grain)]
        elif kind=='grunge': cmd += ['-blur',str(max(.5,grain/3)),'-normalize']
        else: cmd += ['-noise',str(sigma/2),'--']
        cmd += ['-output',out]
        b.run(*cmd)
        im=Image.open(out).convert('L')
        im=ImageEnhance.Contrast(im).enhance(float(p.get('contrast',1))); im=ImageEnhance.Brightness(im).enhance(max(.01,1+float(p.get('brightness',0))))
        tint=p.get('color_tint',(255,255,255,255)); return Image.composite(Image.new('RGB',(w,h),tuple(tint[:3])),Image.new('RGB',(w,h),(0,0,0)),im)
    except Exception: return None
    finally:
        try: import os; os.unlink(out)
        except OSError: pass

def generate_gmic_texture(name,w,h,p,backend=None):
    b=backend or GMICBackend()
    native=_gmic_noise(w,h,p, 'noise_blend' if name=='noise_blend' else name, b)
    if native is not None:return native,'gmic'
    return _fallback(name,w,h,p),'numpy-degraded'
