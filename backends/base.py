from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
@dataclass
class BackendResult:
    data: object=None; stderr:str=''; returncode:int=0; backend:str=''; degraded:bool=False
class Backend(ABC):
    @abstractmethod
    def is_available(self)->bool: ...
    @abstractmethod
    def get_version(self)->str: ...
    @abstractmethod
    def get_path(self)->str: ...
    @abstractmethod
    def run(self,*args,**kwargs)->BackendResult: ...
    def list_filters(self,*args,**kwargs): return []
