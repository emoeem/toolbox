from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any

@dataclass
class UniformSpec:
    name: str
    glsl_type: str
    default: Any
    minimum: Any = None
    maximum: Any = None
    step: Any = None
    label: str = ""
    group: str = "General"

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, data): return cls(**data)

@dataclass
class ShaderPreset:
    name: str
    source: str
    helper_source: str = ""
    uniforms: list[UniformSpec] = field(default_factory=list)
    version: int = 1
    description: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self):
        d=asdict(self); d["uniforms"]=[u.to_dict() for u in self.uniforms]; return d
    @classmethod
    def from_dict(cls,data):
        d=dict(data); d["uniforms"]=[UniformSpec.from_dict(x) for x in d.get("uniforms",[])]; return cls(**d)
