"""Pydantic models for v1 Device Management APIs."""

from __future__ import annotations

from enum import StrEnum
import re
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    ConfigDict,
    Field,
    JsonValue,
    RootModel,
    field_validator,
)

from .base import SDKModel


class DeviceArch(StrEnum):
    """Architecture names accepted by device selection filters."""

    ARM32V7 = "arm32v7"
    ARM64V8 = "arm64v8"
    AMD64 = "amd64"


class Device(SDKModel):
    """Device Management API response model."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    uuid: str = Field(min_length=1)
    name: str | None = None
    status: str | None = None
    description: str | None = None
    python_version: str | None = Field(default=None, alias="device_version")
    registration_time: str | None = None
    last_online: str | None = None
    config_variables: list[DeviceConfigVariable] = Field(default_factory=list)
    labels: list[DeviceLabel] = Field(default_factory=list)


class DeviceCreate(SDKModel):
    """Request body used to provision a device."""

    name: str = Field(min_length=1)
    python_version: Literal["2", "3"] = "2"
    description: str | None = None
    config_variables: dict[str, JsonValue] = Field(default_factory=dict)
    labels: dict[str, str] = Field(default_factory=dict)


class DeviceConfigVariable(SDKModel):
    id: int | str | None = None
    key: str
    value: Any


class DeviceConfigVariableCreate(SDKModel):
    key: str = Field(min_length=1)
    value: JsonValue

    @field_validator("value")
    @classmethod
    def require_truthy_value(cls, value: JsonValue) -> JsonValue:
        if not value:
            raise ValueError("value must be non-empty")
        return value


class DeviceConfigVariableUpdate(SDKModel):
    id: int | str
    key: str = Field(min_length=1)
    value: JsonValue

    @field_validator("value")
    @classmethod
    def require_present_value(cls, value: JsonValue) -> JsonValue:
        if value is None or value == "":
            raise ValueError("value is required")
        return value


class DeviceLabel(SDKModel):
    id: int | str | None = None
    key: str
    value: str


class DeviceLabelCreate(SDKModel):
    key: str = Field(min_length=1)
    value: str = Field(min_length=1)


class DeviceLabelUpdate(SDKModel):
    id: int | str
    key: str = Field(min_length=1)
    value: str = Field(min_length=1)


class DeviceCreateResponse(SDKModel):
    """Credential and script details returned by device provisioning."""

    token: str = Field(alias="data", repr=False)
    device_id: str
    script_command: str
    script_url: str | None = None


class DeviceApplyParameters(SDKModel):
    """Request body for applying Parameter trees to devices."""

    device_list: list[str] = Field(min_length=1)
    tree_names: list[str] | None = None

    @field_validator("device_list", "tree_names")
    @classmethod
    def validate_nonempty_strings(cls, values: list[str] | None) -> list[str] | None:
        if values is not None and any(
            not isinstance(value, str) or not value for value in values
        ):
            raise ValueError("values must contain non-empty strings")
        return values


class DeviceSelectionQuery(SDKModel):
    """Architecture selection query sent to the v1 device manager."""

    operator: str
    specs: dict[str, JsonValue]


class DeviceDaemonPatch(RootModel[dict[str, JsonValue]]):
    """Daemon feature toggles and optional v1 feature configuration."""

    @field_validator("root")
    @classmethod
    def validate_features(cls, features: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if not features or any(not key for key in features):
            raise ValueError("at least one non-empty daemon feature is required")
        if not any(key != "config" for key in features):
            raise ValueError("at least one daemon feature toggle is required")
        if "config" in features and not isinstance(features["config"], dict):
            raise ValueError("daemon config must be an object")
        for key, enabled in features.items():
            if key != "config" and not isinstance(enabled, bool):
                raise ValueError(f"daemon feature {key!r} must be a boolean")
        return features


class DeviceActionResponse(RootModel[JsonValue]):
    """Typed container for endpoint-specific v1 action result data."""


class DeviceCommand(SDKModel):
    """Command request body; device IDs are supplied by the operation."""

    cmd: str = Field(min_length=1)
    device_ids: list[str] = Field(default_factory=list)
    shell: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    bg: bool | None = False
    run_async: bool | None = False
    runas: str | None = None
    cwd: str | None = Field(default=None, validation_alias=AliasChoices("cwd", "pwd"))
    timeout: int = Field(default=300, gt=0)

    @field_validator("env")
    @classmethod
    def validate_environment_names(cls, env: dict[str, str]) -> dict[str, str]:
        if any(not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", key) for key in env):
            raise ValueError("environment variable names must be valid identifiers")
        return env


class DeviceCommandResponse(SDKModel):
    """Command submission or result payload, retaining service-specific fields."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    jid: str | None = None
    data: JsonValue | None = None
    status: str | None = None
    http_status_code: int | None = Field(default=None, exclude=True)
    envelope_status: str | None = Field(default=None, exclude=True)

    @property
    def is_pending(self) -> bool:
        """Whether the command result is still being processed."""
        if self.http_status_code in (202, 204):
            return True
        pending_statuses = {
            "pending",
            "queued",
            "running",
            "accepted",
        }
        return (self.status or "").lower() in pending_statuses or (
            self.envelope_status or ""
        ).lower() in pending_statuses
