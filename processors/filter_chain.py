from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .filter_defs import FilterDefRegistry

SCHEMA_VERSION = 1


class FilterStepError(RuntimeError):
    def __init__(self, step_index: int, filter_key: str, message: str, original: Exception | None = None):
        super().__init__(f"步骤 {step_index + 1} [{filter_key}]: {message}")
        self.step_index = step_index
        self.filter_key = filter_key
        self.original = original


@dataclass
class FilterStep:
    filter_key: str
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    @property
    def filter_def(self):
        return FilterDefRegistry.instance().get(self.filter_key)

    def validate(self) -> tuple[bool, list[str]]:
        defn = self.filter_def
        if defn is None:
            return False, [f"未知 Filter key: '{self.filter_key}'"]
        ok, errors, _merged = defn.validate_params(self.params)
        return ok, errors

    def apply(self, image: np.ndarray, cancel_token=None) -> np.ndarray:
        defn = self.filter_def
        if defn is None:
            raise FilterStepError(
                -1, self.filter_key, f"未知 Filter key: '{self.filter_key}'",
            )
        ok, errors, merged = defn.validate_params(self.params)
        if not ok:
            raise FilterStepError(
                -1, self.filter_key,
                "参数验证失败: " + "; ".join(errors),
            )
        try:
            return defn.apply(image, merged, cancel_token=cancel_token)
        except FilterStepError:
            raise
        except Exception as exc:
            raise FilterStepError(
                -1, self.filter_key,
                f"processor 执行异常: {exc}", original=exc,
            ) from exc

    def clone(self) -> FilterStep:
        return FilterStep(
            filter_key=self.filter_key,
            params=copy.deepcopy(self.params),
            enabled=self.enabled,
        )

    def to_dict(self) -> dict:
        return {
            "filter_key": self.filter_key,
            "params": copy.deepcopy(self.params),
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> FilterStep:
        if not isinstance(data, dict):
            raise ValueError("FilterStep.from_dict 需要 dict")
        key = data.get("filter_key")
        if not key:
            raise ValueError("FilterStep.from_dict 缺少 filter_key")
        params = data.get("params", {})
        enabled = data.get("enabled", True)
        return cls(filter_key=str(key), params=dict(params), enabled=bool(enabled))


@dataclass
class FilterChain:
    steps: list[FilterStep] = field(default_factory=list)
    name: str = ""

    def clone(self) -> FilterChain:
        return FilterChain(
            steps=[s.clone() for s in self.steps],
            name=self.name,
        )

    def __len__(self) -> int:
        return len(self.steps)

    def __iter__(self):
        return iter(self.steps)

    def __getitem__(self, idx: int) -> FilterStep:
        return self.steps[idx]

    def add(self, filter_key: str, params: dict[str, Any] | None = None, enabled: bool = True) -> FilterStep:
        defn = FilterDefRegistry.instance().get(filter_key)
        if defn is None:
            raise KeyError(f"未知 Filter key: '{filter_key}'")
        merged = defn.default_params()
        if params:
            merged.update(params)
        step = FilterStep(filter_key=filter_key, params=merged, enabled=enabled)
        self.steps.append(step)
        return step

    def add_step(self, step: FilterStep) -> FilterStep:
        defn = FilterDefRegistry.instance().get(step.filter_key)
        if defn is None:
            raise KeyError(f"未知 Filter key: '{step.filter_key}'")
        merged = defn.default_params()
        merged.update(step.params)
        new_step = FilterStep(filter_key=step.filter_key, params=merged, enabled=step.enabled)
        self.steps.append(new_step)
        return new_step

    def remove(self, index: int) -> FilterStep:
        return self.steps.pop(index)

    def clear(self) -> None:
        self.steps.clear()

    def move_up(self, index: int) -> bool:
        if index <= 0 or index >= len(self.steps):
            return False
        self.steps[index - 1], self.steps[index] = self.steps[index], self.steps[index - 1]
        return True

    def move_down(self, index: int) -> bool:
        if index < 0 or index >= len(self.steps) - 1:
            return False
        self.steps[index + 1], self.steps[index] = self.steps[index], self.steps[index + 1]
        return True

    def duplicate(self, index: int) -> FilterStep:
        step = self.steps[index]
        new_step = step.clone()
        self.steps.insert(index + 1, new_step)
        return new_step

    def enable(self, index: int, enabled: bool = True) -> None:
        self.steps[index].enabled = enabled

    def disable(self, index: int) -> None:
        self.steps[index].enabled = False

    def set_params(self, index: int, params: dict[str, Any]) -> None:
        step = self.steps[index]
        defn = FilterDefRegistry.instance().get(step.filter_key)
        if defn is None:
            raise KeyError(f"未知 Filter key: '{step.filter_key}'")
        merged = defn.default_params()
        merged.update(params)
        ok, errors, final = defn.validate_params(merged)
        if not ok:
            raise ValueError("; ".join(errors))
        step.params = final

    def validate_all(self) -> tuple[bool, list[str]]:
        errors: list[str] = []
        for i, step in enumerate(self.steps):
            if not step.enabled:
                continue
            defn = step.filter_def
            if defn is None:
                errors.append(f"步骤 {i + 1}: 未知 Filter key '{step.filter_key}'")
                continue
            ok, errs, _ = defn.validate_params(step.params)
            if not ok:
                for e in errs:
                    errors.append(f"步骤 {i + 1} [{defn.display_name}]: {e}")
        return (len(errors) == 0), errors

    def apply(self, image: np.ndarray, cancel_token=None) -> np.ndarray:
        ok, errors = self.validate_all()
        if not ok:
            raise FilterStepError(-1, "", "FilterChain 参数验证失败: " + " | ".join(errors))
        current = image
        for i, step in enumerate(self.steps):
            if not step.enabled:
                continue
            if cancel_token is not None:
                cancel_token.raise_if_cancelled()
            try:
                current = step.apply(current, cancel_token=cancel_token)
            except FilterStepError as exc:
                raise FilterStepError(i, step.filter_key, exc.args[0], original=exc.original)
            except Exception as exc:
                raise FilterStepError(i, step.filter_key, f"执行失败: {exc}", original=exc) from exc
        return current

    def enabled_steps(self) -> list[FilterStep]:
        return [s for s in self.steps if s.enabled]

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "steps": [s.to_dict() for s in self.steps],
        }

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> FilterChain:
        if not isinstance(data, dict):
            raise ValueError("FilterChain.from_dict 需要 dict")
        version = data.get("schema_version", 0)
        if version > SCHEMA_VERSION:
            raise ValueError(
                f"不支持的 FilterChain schema_version {version}，当前最高 {SCHEMA_VERSION}"
            )
        chain = cls(name=data.get("name", ""))
        for sd in data.get("steps", []):
            try:
                chain.add_step(FilterStep.from_dict(sd))
            except Exception as exc:
                raise ValueError(f"FilterChain.from_dict: 步骤解析失败: {exc}") from exc
        return chain

    @classmethod
    def from_json(cls, text: str) -> FilterChain:
        import json
        data = json.loads(text)
        return cls.from_dict(data)
