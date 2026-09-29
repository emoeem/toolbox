from __future__ import annotations
import json, os, shutil, subprocess, tempfile, time
from pathlib import Path
from .base import Backend, BackendResult
class GMICBackend(Backend):
    def __init__(self, path=None, timeout=20, cache_dir=None):
        self.path=path or shutil.which('gmic'); self.timeout=timeout
        from processors.utils import ensure_writable_dir
        # A read-only ~/.cache used to make run() fail with a raw OSError.
        self.cache_dir=ensure_writable_dir(cache_dir or Path.home()/'.cache/toolbox/gmic')
        self.cache_file=self.cache_dir/'filters.json'
    def is_available(self): return bool(self.path and os.access(self.path,os.X_OK))
    def get_path(self): return self.path or ''
    def get_version(self):
        if not self.is_available(): return ''
        try:
            p=subprocess.run([self.path,'-version'],capture_output=True,text=True,timeout=5,check=False,stdin=subprocess.DEVNULL)
            text=(p.stdout or p.stderr).replace('\x1b[0;0;0m','').replace('\x1b[1m','').replace('\x1b[0m','')
            for line in text.splitlines():
                if 'Version' in line:return line.strip()
            return text.strip().splitlines()[0] if text.strip() else ''
        except (OSError,subprocess.TimeoutExpired): return ''
    def list_filters(self, refresh=False):
        version=self.get_version()
        if not refresh and self.cache_file.exists():
            try:
                d=json.loads(self.cache_file.read_text());
                if d.get('version')==version and isinstance(d.get('filters'),list): return d['filters']
            except (OSError,ValueError,TypeError): pass
        if not self.is_available(): return []
        try:
            p=subprocess.run([self.path,'-command','-list'],capture_output=True,text=True,timeout=8,check=False,stdin=subprocess.DEVNULL)
            filters=[x.strip() for x in p.stdout.splitlines() if x.strip()]
            self.cache_file.write_text(json.dumps({'version':version,'queried_at':time.time(),'filters':filters},ensure_ascii=False,indent=2))
            return filters
        except (OSError,subprocess.TimeoutExpired): return []
    def refresh_filters(self): return self.list_filters(refresh=True)
    def cache_info(self):
        try:return json.loads(self.cache_file.read_text())
        except (OSError,ValueError):return {}
    def run(self,*args,**kwargs):
        if not self.is_available(): raise RuntimeError('GMIC 不可用')
        temp=tempfile.TemporaryDirectory(prefix='run-',dir=self.cache_dir)
        try:
            cmd=[self.path,*map(str,args)]; timeout=kwargs.get('timeout',self.timeout)
            p=subprocess.run(cmd,cwd=temp.name,capture_output=True,text=True,timeout=timeout,check=False,stdin=subprocess.DEVNULL)
            if p.returncode: raise RuntimeError((p.stderr or p.stdout or 'GMIC 执行失败').strip())
            return BackendResult(p.stdout,p.stderr,p.returncode,'gmic',False)
        except subprocess.TimeoutExpired as e: raise TimeoutError(f'GMIC 超时（{timeout}s）') from e
        finally: temp.cleanup()
