import numpy as np

def _base(w,h,scale,seed):
    rng=np.random.default_rng(int(seed)); gh=max(2,int(h/scale)+2); gw=max(2,int(w/scale)+2); return rng.random((gh,gw),dtype=np.float32)
def _smooth(a):
    a=(a+np.roll(a,1,0)+np.roll(a,-1,0)+np.roll(a,1,1)+np.roll(a,-1,1))/5; return a
def value(w,h,scale,octaves,persistence,lacunarity,seed,warp=0):
    out=np.zeros((h,w),np.float32); amp=1.; total=0.; freq=1.
    for _ in range(max(1,int(octaves))):
        s=max(1,scale/freq); a=_base(w,h,s,seed+int(freq*17)); a=np.asarray(__import__('PIL').Image.fromarray((a*255).astype('uint8')).resize((w,h),__import__('PIL').Image.Resampling.BICUBIC),dtype=np.float32)/255
        if warp: a=np.roll(a,int(warp*3),0)
        out+=a*amp; total+=amp; amp*=persistence; freq*=lacunarity
    return out/total

def perlin(w,h,**kw):
    return _gradient_noise(w,h,kw)
def simplex(w,h,**kw):
    return _gradient_noise(w,h,kw,phase=0.37)
def _gradient_noise(w,h,kw,phase=0):
    a=value(w,h,kw['scale'],kw['octaves'],kw['persistence'],kw['lacunarity'],kw['seed'],kw.get('warp',0)); yy,xx=np.mgrid[:h,:w]; wave=(np.sin(xx/(kw['scale']+1)+phase)+np.cos(yy/(kw['scale']+1)-phase))*0.08; return np.clip(a+wave,0,1)
def worley(w,h,**kw):
    rng=np.random.default_rng(int(kw['seed'])); n=max(4,int((w*h)**0.5/kw['scale']*4)); pts=rng.random((n,2))*[w,h]; yy,xx=np.mgrid[:h,:w]; best=np.full((h,w),1e9,np.float32)
    for x,y in pts: best=np.minimum(best,(xx-x)**2+(yy-y)**2)
    return np.clip(np.sqrt(best)/(max(w,h)*0.35),0,1)
def cellular(w,h,**kw):
    return 1-worley(w,h,**kw)
GENERATORS={'perlin':perlin,'simplex':simplex,'value':value,'worley':worley,'cellular':cellular}
