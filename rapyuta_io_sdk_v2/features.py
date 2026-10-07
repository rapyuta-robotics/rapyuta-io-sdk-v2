"""Explicit feature switches and optional dependency checks."""

from importlib import import_module
from types import ModuleType
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

FeatureName = Literal["configtree_source", "apply", "charts"]


class FeatureDisabledError(RuntimeError):
    """An optional SDK operation was requested without enabling its feature."""


class MissingOptionalDependencyError(ImportError):
    """An enabled optional feature lacks its dependencies."""


class FeatureFlags(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    configtree_source: bool = False
    apply: bool = False
    charts: bool = False

    @field_validator("apply", "charts")
    @classmethod
    def charts_need_apply(cls, value: bool, info: ValidationInfo) -> bool:
        if info.field_name == "charts" and value and not info.data.get("apply"):
            raise ValueError("the charts feature requires the apply feature")
        if info.field_name == "apply" and not value and info.data.get("charts"):
            raise ValueError("disable charts before disabling the apply feature")
        return value

    def require(self, name: FeatureName) -> None:
        if name not in ("configtree_source", "apply", "charts"):
            raise ValueError(f"unknown SDK feature: {name}")
        if not getattr(self, name):
            raise FeatureDisabledError(f"enable features.{name} to use this operation")
        if name == "charts" and not self.apply:
            raise FeatureDisabledError("the charts feature requires features.apply")


def require_dependency(module_name: str, extra: str) -> ModuleType:
    """Import a feature dependency only when its operation is requested."""
    try:
        return import_module(module_name)
    except ImportError as exc:
        raise MissingOptionalDependencyError(
            f"install rapyuta-io-sdk-v2[{extra}] to use this feature "
            f"(missing dependency: {module_name})"
        ) from exc
