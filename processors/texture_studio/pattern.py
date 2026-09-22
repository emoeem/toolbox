import numpy as np
def pattern(kind,w,h,size=32,spacing=8,angle=0,color_a=(30,30,30),color_b=(220,220,220),background=(0,0,0),anti_alias=True):
    y,x=np.mgrid[:h,:w]; a=np.deg2rad(angle); u=x*np.cos(a)+y*np.sin(a); v=-x*np.sin(a)+y*np.cos(a); size=max(.1,float(size)); spacing=max(0,float(spacing));
    if kind=='stripes': m=(np.mod(u,size+spacing)<size).astype(float)
    elif kind=='rings': m=(np.mod(np.sqrt((x-w/2)**2+(y-h/2)**2),size+spacing)<size).astype(float)
    elif kind=='checker': m=((np.floor(x/size)+np.floor(y/size))%2).astype(float)
    elif kind=='dots': m=((np.mod(x,size+spacing)<size*.5)&(np.mod(y,size+spacing)<size*.5)).astype(float)
    else: m=((np.mod(u,size+spacing)<size)&(np.mod(v,size+spacing)<size)).astype(float)
    if anti_alias:
        m=(m+np.roll(m,1,0)+np.roll(m,-1,0)+np.roll(m,1,1)+np.roll(m,-1,1))/5
    ca=np.array(color_a,dtype=np.float32); cb=np.array(color_b,dtype=np.float32); bg=np.array(background,dtype=np.float32); rgb=ca[None,None,:]*m[...,None]+cb[None,None,:]*(1-m[...,None]); rgb=rgb*(m[...,None]*.9+.1)+bg[None,None,:]*0; return np.clip(rgb,0,255).astype(np.uint8)
