import numpy as np
from PIL import Image,ImageFilter
from .noise import GENERATORS
from .pattern import pattern
from .gmic import generate_gmic_texture

def noise_image(g,w,h,p):
    gp={k:v for k,v in p.items() if k not in ('contrast','brightness')}; a=GENERATORS[g](w,h,**gp); a=np.clip((a-.5)*p.get('contrast',1)+.5+p.get('brightness',0),0,1); return Image.fromarray((a*255).astype('uint8'),'L').convert('RGB')
def generate(g,w,h,p,backend_preference='auto'):
    if g in GENERATORS:return noise_image(g,w,h,p)
    if g.startswith('gmic:'):
        from .gmic import GMICBackend
        backend=GMICBackend() if backend_preference!='numpy' else type('NoBackend',(),{'is_available':lambda self:False})()
        im,_backend=generate_gmic_texture(g.split(':',1)[1],w,h,p,backend); return im
    if g.startswith('pattern:'):
        return Image.fromarray(pattern(g.split(':',1)[1],w,h,p.get('size',32),p.get('spacing',8),p.get('angle',0),p.get('color_a',(30,30,30)),p.get('color_b',(220,220,220)),p.get('background',(0,0,0)),p.get('anti_alias',True)))
    raise ValueError(f'unknown texture generator: {g}')
