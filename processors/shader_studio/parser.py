from __future__ import annotations
import re
from .model import UniformSpec

_UNIFORM=re.compile(r"^\s*uniform\s+(?P<type>float|int|bool|vec2|vec3|vec4|sampler2D)\s+(?P<name>[A-Za-z_]\w*)\s*(?:=\s*(?P<value>[^;]+))?\s*;",re.M)
_META=re.compile(r"//\s*@(?P<key>min|max|step|label|group)\s+(?P<value>[^\n]+)")

def _value(t,v):
    if not v:
        return {"float":0.5,"int":0,"bool":False,"vec2":[0.0,0.0],"vec3":[0.0,0.0,0.0],"vec4":[1.0,1.0,1.0,1.0],"sampler2D":None}[t]
    x=v.strip()
    if t=="bool": return x.lower()=="true"
    if t in ("float","int"): return float(x.rstrip('f')) if t=="float" else int(float(x))
    nums=[float(a.rstrip('f')) for a in re.findall(r"[-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?",x)]
    return nums[:int(t[-1])] if nums else _value(t,None)

def parse_uniforms(source: str) -> list[UniformSpec]:
    out=[]
    for m in _UNIFORM.finditer(source):
        t,n=m.group("type"),m.group("name")
        if t=="sampler2D": continue
        meta={}
        # Metadata may be placed immediately above the declaration.
        before=source[max(0,m.start()-500):m.start()]
        for mm in _META.finditer(before): meta[mm.group("key")]=mm.group("value").strip()
        def cast(v):
            if v is None:return None
            try:
                if t=="int": return int(float(v))
                if t.startswith("vec"): return _value(t,v)
                return float(v)
            except: return v
        out.append(UniformSpec(n,t,_value(t,m.group("value")),cast(meta.get("min")),cast(meta.get("max")),cast(meta.get("step")),meta.get("label",n),meta.get("group","General")))
    return out
