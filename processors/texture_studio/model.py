from dataclasses import dataclass, field
from typing import Any
@dataclass
class TextureSpec:
    id:str; name:str; category:str; tags:list[str]=field(default_factory=list); defaults:dict[str,Any]=field(default_factory=dict)
@dataclass
class TexturePreset:
    name:str; generator_id:str; params:dict[str,Any]; tags:list[str]=field(default_factory=list)
