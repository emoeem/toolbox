from __future__ import annotations
import os, shutil, subprocess, tempfile

def wrap_shader(source:str, helper:str="") -> str:
    import re
    uniforms='\n'.join(re.findall(r'^\s*uniform\s+(?:float|int|bool|vec2|vec3|vec4|sampler2D)\s+[A-Za-z_]\w*\s*(?:=\s*[^;]+)?\s*;', source, re.M))
    source=re.sub(r'^\s*uniform\s+(?:float|int|bool|vec2|vec3|vec4|sampler2D)\s+[A-Za-z_]\w*\s*(?:=\s*[^;]+)?\s*;\s*$','',source,flags=re.M)
    return '#version 330 core\nin vec2 v_uv;\nout vec4 fragColor;\nuniform sampler2D u_image;\nuniform float u_time;\nuniform vec2 u_resolution;\n'+uniforms+'\n'+helper+'\nvoid main(){\n'+ '\n'.join('  '+x for x in source.splitlines()) +'\n}\n'

def validate_glsl(source:str, helper:str="") -> tuple[bool,str]:
    exe=shutil.which("glslangValidator")
    if not exe: return False,"glslangValidator 未安装"
    import re
    uniforms='\n'.join(re.findall(r'^\s*uniform\s+(?:float|int|bool|vec2|vec3|vec4|sampler2D)\s+[A-Za-z_]\w*\s*(?:=\s*[^;]+)?\s*;', source, re.M))
    source=re.sub(r'^\s*uniform\s+(?:float|int|bool|vec2|vec3|vec4|sampler2D)\s+[A-Za-z_]\w*\s*(?:=\s*[^;]+)?\s*;\s*$', '', source, flags=re.M)
    text=wrap_shader(uniforms+'\n'+source,helper)
    with tempfile.TemporaryDirectory() as td:
        path=os.path.join(td,"shader.frag")
        with open(path,"w",encoding="utf-8") as fh: fh.write(text)
        p=subprocess.run([exe,"-S","frag",path],capture_output=True,text=True,timeout=15)
        return p.returncode==0,(p.stdout+p.stderr).strip()
