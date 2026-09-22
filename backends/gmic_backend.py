from __future__ import annotations
import os,shutil,subprocess,tempfile,re
from pathlib import Path
from .base import Backend,BackendResult
class GMICBackend(Backend):
    def __init__(self,path=None,timeout=20,cache_dir=None):
        self.path=path or shutil.which('gmic'); self.timeout=timeout; self.cache_dir=Path(cache_dir or Path.home()/'.cache/toolbox/gmic'); self.cache_dir.mkdir(parents=True,exist_ok=True)
    def is_available(self): return bool(self.path and os.access(self.path,os.X_OK))
    def get_path(self): return self.path or ''
    def get_version(self):
        if not self.is_available(): return ''
        try:
            p=subprocess.run([self.path,'-version'],capture_output=True,text=True,timeout=5,check=False)
            text=(p.stdout or p.stderr).replace('\x1b[0;0;0m','').replace('\x1b[1m','').replace('\x1b[0m','');
            for line in text.splitlines():
                if 'Version' in line: return line.strip()
            return text.strip().splitlines()[0] if text.strip() else ''
        except (OSError,subprocess.TimeoutExpired): return ''
    def run(self,*args,**kwargs):
        if not self.is_available(): raise RuntimeError('GMIC 不可用')
        temp=tempfile.TemporaryDirectory(prefix='run-',dir=self.cache_dir)
        try:
            cmd=[self.path,*map(str,args)]; p=subprocess.run(cmd,cwd=temp.name,capture_output=True,text=True,timeout=kwargs.get('timeout',self.timeout),check=False)
            if p.returncode: raise RuntimeError((p.stderr or p.stdout or 'GMIC 执行失败').strip())
            return BackendResult(stdout if False else p.stdout,p.stderr,p.returncode,'gmic',False)
        except subprocess.TimeoutExpired as e: raise TimeoutError(f'GMIC 超时（{kwargs.get("timeout",self.timeout)}s）') from e
        finally: temp.cleanup()
    def list_filters(self,*args,**kwargs):
        if not self.is_available(): return []
        try:
            p=subprocess.run([self.path,'-command','-list'],capture_output=True,text=True,timeout=5,check=False); return [x.strip() for x in p.stdout.splitlines() if x.strip()]
        except (OSError,subprocess.TimeoutExpired): return []
