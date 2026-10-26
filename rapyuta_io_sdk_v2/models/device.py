# Copyright 2026 Rapyuta Robotics

"""Typed contracts for the legacy Device Management service."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    ConfigDict,
    Field,
    JsonValue,
    RootModel,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.daemons import Daemon


class DeviceEmptyData(SDKModel):
    """An explicitly empty platform acknowledgment, never invented data."""

    model_config = ConfigDict(extra="forbid")


class DeviceData[T](SDKModel):
    """Named inner response retaining the platform data field."""

    model_config = ConfigDict(extra="forbid")
    data: T


class DeviceEnvelope[T](SDKModel):
    """A successful legacy response with its original nested envelope."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["success"]
    response: DeviceData[T]


class DeviceMutationResponse(DeviceEnvelope[DeviceEmptyData]):
    """Confirmed mutation with empty platform data."""


class DeviceStatus(StrEnum):
    """Reported Device Manager states."""

    NEW = "NEW"
    REGISTERED = "REGISTERED"
    REJECTED = "REJECTED"
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DELETED = "DELETED"
    INITIALIZING = "INITIALIZING"
    ERROR = "ERROR"
    FAILED = "FAILED"


type DeviceUpdateStatus = Literal[
    "REGISTERED", "REJECTED", "DELETED", "INITIALIZING", "ONLINE", "OFFLINE", "FAILED"
]
type LabelText = Annotated[
    StrictStr, Field(pattern=r"^[0-9a-zA-Z][a-zA-Z0-9_-]{0,49}$")
]
type ConfigurationKey = Annotated[
    StrictStr, Field(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]{0,255}$")
]
type DeviceIdentity = Annotated[StrictStr, Field(min_length=1)]
type PositiveRecordID = Annotated[StrictInt, Field(gt=0)]


class DeviceRequest(SDKModel):
    """Reject unsupported request fields."""

    model_config = ConfigDict(extra="forbid")


class DeviceLabel(SDKModel):
    """A stored label and its record identity."""

    id: PositiveRecordID
    key: LabelText
    value: LabelText


class DeviceLabelsCreate(RootModel[dict[LabelText, LabelText]]):
    """Flat label map; empty is permitted for registration."""


class DeviceConfigVariable(SDKModel):
    """Configuration record; reported values may be empty."""

    id: PositiveRecordID
    key: ConfigurationKey
    value: StrictStr
    type: str | None = None


def _creation_value(key: str, *, value: str | bool) -> None:
    if key in {"runtime_docker", "runtime_preinstalled"}:
        if value not in (True, False, "True", "False"):
            message = "Runtime flags require a boolean or True/False string"
            raise ValueError(message)
    elif not isinstance(value, str):
        message = "Configuration values require strings"
        raise ValueError(message)


class DeviceCreationConfig(RootModel[dict[ConfigurationKey, StrictStr | StrictBool]]):
    """Registration configuration with at least one enabled runtime."""

    @model_validator(mode="after")
    def validate_runtime(self) -> Self:
        """Validate runtime flags and string configuration values."""
        runtime_keys = {"runtime_docker", "runtime_preinstalled"}
        for key, value in self.root.items():
            _creation_value(key, value=value)
        if not any(self.root.get(key) in (True, "True") for key in runtime_keys):
            message = "Enable at least one registration runtime"
            raise ValueError(message)
        return self


class DeviceDaemonReport(RootModel[dict[str, JsonValue]]):
    """Extensible reported daemon status, without mutation operations."""


class DeviceInterfaces(RootModel[dict[str, JsonValue]]):
    """Reported interface collections."""


class DeviceDeployment(SDKModel):
    """Legacy deployment summary attached to a device."""

    model_config = ConfigDict(extra="allow")
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)
    io_deployment_id: str
    deployment_id: str
    phase: str
    error_code: str | None = None
    created_at: datetime | None = None


class Device(SDKModel):
    """Device identity and optional reported details."""

    model_config = ConfigDict(extra="allow")
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)
    uuid: DeviceIdentity
    name: StrictStr
    status: DeviceStatus
    description: str | None = None
    created_by: str | None = None
    registration_time: datetime | None = None
    last_online: datetime | None = None
    last_status_update_time: datetime | None = None
    python_version: str | None = Field(default=None, alias="device_version")
    daemon_status: DeviceDaemonReport | None = Field(
        default=None, alias="daemons_status"
    )
    labels: tuple[DeviceLabel, ...] | None = None
    config_variables: tuple[DeviceConfigVariable, ...] | None = None
    deployments: tuple[DeviceDeployment, ...] | None = None
    installation_metadata: JsonValue = None
    error_code: str | None = None
    error_message: str | None = None
    host: str | None = None
    username: str | None = None
    saltversion: str | None = None
    ip_interfaces: DeviceInterfaces | None = None
    mac_addresses: DeviceInterfaces | None = None
    os: str | None = None
    osarch: str | None = None
    osrelease: str | None = None
    cpuarch: str | None = None


def device_name(value: str) -> str:
    """Validate names using the service's Unicode-aware Python expression."""
    if re.fullmatch(r"(?=.{3,256}$)[a-zA-Z]+[ \w-]*[^\W_-]", value) is None:
        message = "Invalid device name"
        raise ValueError(message)
    return value


class DeviceCreate(DeviceRequest):
    """Register a Python 3 device and request onboarding authorization."""

    name: StrictStr
    description: Annotated[StrictStr, Field(max_length=256)] | None = None
    config_variables: DeviceCreationConfig
    labels: DeviceLabelsCreate = Field(default_factory=lambda: DeviceLabelsCreate({}))
    python_version: Literal["3"] = "3"
    _name = field_validator("name")(device_name)


class DeviceUpdate(DeviceRequest):
    """Explicit updates; null/empty descriptions are service no-ops."""

    name: StrictStr | None = None
    status: DeviceUpdateStatus | None = None
    description: Annotated[StrictStr, Field(max_length=256)] | None = None

    @model_validator(mode="after")
    def validate_update(self) -> Self:
        """Require an explicit update and validate nonnull names/statuses."""
        if not self.model_fields_set:
            message = "Supply at least one update field"
            raise ValueError(message)
        if "name" in self.model_fields_set:
            if self.name is None:
                message = "Device name cannot be null"
                raise ValueError(message)
            device_name(self.name)
        if "status" in self.model_fields_set and self.status is None:
            message = "Device status cannot be null"
            raise ValueError(message)
        return self


class DeviceListQuery(DeviceRequest):
    """Optional exact name filter; no pagination is invented."""

    name: StrictStr | None = None


class DeviceSelectionRecord(SDKModel):
    """Compact selection result with separate numeric and UUID identities."""

    uuid: DeviceIdentity
    id: PositiveRecordID
    name: StrictStr
    status: DeviceStatus


class DeviceLabelLeaf(DeviceRequest):
    """Label equality/inequality predicate."""

    operator: Literal["$eq", "$ne"]
    args: tuple[StrictStr, StrictStr]


class DeviceLabelLogical(DeviceRequest):
    """Recursive label predicate; empty logical arrays are supported."""

    operator: Literal["$and", "$or"]
    args: tuple[DeviceLabelExpression, ...]


type DeviceLabelExpression = Annotated[
    DeviceLabelLeaf | DeviceLabelLogical, Field(discriminator="operator")
]


class DeviceSpecLeaf(DeviceRequest):
    """Grain predicate; $in uses server substring semantics."""

    operator: Literal["$eq", "$ne", "$in"]
    args: tuple[StrictStr, StrictStr | StrictInt | StrictBool | float | None]


class DeviceSpecLogical(DeviceRequest):
    """Nonempty recursive grain predicate."""

    operator: Literal["$and", "$or"]
    args: Annotated[tuple[DeviceSpecExpression, ...], Field(min_length=1)]


type DeviceSpecExpression = Annotated[
    DeviceSpecLeaf | DeviceSpecLogical, Field(discriminator="operator")
]


class DeviceSelection(DeviceRequest):
    """Explicit platform selection expression."""

    operator: Literal["$and", "$or"]
    labels: DeviceLabelExpression | None = None
    specs: DeviceSpecExpression | None = None


DeviceLabelLogical.model_rebuild()
DeviceSpecLogical.model_rebuild()


class DeviceTokenData(SDKModel):
    """Onboarding token and siblings; token is omitted from representations."""

    model_config = ConfigDict(extra="forbid")
    data: Annotated[StrictStr, Field(min_length=1, repr=False)]
    device_id: DeviceIdentity
    script_command: Annotated[StrictStr, Field(min_length=1)]


class DeviceRegistrationResponse(SDKModel):
    """Registration authorization, not a Device detail response."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["success"]
    response: DeviceTokenData


class DeviceOnboardingResponse(DeviceRegistrationResponse):
    """Fresh onboarding authorization for an existing device."""


class DeviceListResponse(DeviceEnvelope[tuple[Device, ...]]):
    """Device list envelope."""


class DeviceResponse(DeviceEnvelope[Device]):
    """Device detail envelope."""


class DeviceUpdateResponse(DeviceEnvelope[Device]):
    """Device update summary; does not imply a detail lookup."""


class DeviceSelectionResponse(DeviceEnvelope[tuple[DeviceSelectionRecord, ...]]):
    """Compact selected devices."""


class DeviceLabelUpdate(DeviceRequest):
    """Update a label by returned record ID, preserving omission."""

    key: LabelText | None = None
    value: LabelText | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> Self:
        """Require at least one explicitly supplied nonnull label field."""
        if not self.model_fields_set or any(
            getattr(self, name) is None for name in self.model_fields_set
        ):
            message = "Supply at least one nonnull label field"
            raise ValueError(message)
        return self


class DeviceConfigVariableCreate(DeviceRequest):
    """Create a configuration record on one online device."""

    key: ConfigurationKey
    value: Annotated[StrictStr, Field(min_length=1)]


class DeviceConfigVariableUpdate(DeviceRequest):
    """Update a configuration value without renaming its key."""

    value: Annotated[StrictStr, Field(min_length=1)]


class DeviceMigration(DeviceRequest):
    """Destination project; caller authorization remains in source context."""

    project: StrictStr

    @field_validator("project")
    @classmethod
    def validate_project(cls, value: str) -> str:
        """Reject blank destination projects."""
        if not value.strip():
            message = "Destination project must not be blank"
            raise ValueError(message)
        return value


class DeviceVPNRouteConfiguration(DeviceRequest):
    """Request project-configured routes using a strict boolean."""

    advertise_routes: StrictBool = False


class DeviceVPNConfiguration(DeviceRequest):
    """Only VPN-specific configuration may be changed."""

    vpn: DeviceVPNRouteConfiguration


class DeviceVPNUpdate(DeviceRequest):
    """Enable/disable VPN on one explicit device; no readiness waiting."""

    vpn: StrictBool
    config: DeviceVPNConfiguration | None = None

    @model_validator(mode="after")
    def validate_advertisement(self) -> Self:
        """Reject route advertisement when disabling VPN."""
        if (
            not self.vpn
            and self.config is not None
            and self.config.vpn.advertise_routes
        ):
            message = "Cannot advertise routes while disabling VPN"
            raise ValueError(message)
        return self


class DeviceParameterApply(DeviceRequest):
    """Apply selected or all Parameter trees to explicit targets."""

    device_list: tuple[StrictStr, ...]
    tree_names: tuple[StrictStr, ...] | None = None

    @field_validator("device_list")
    @classmethod
    def validate_targets(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Require nonempty unique nonblank target identities."""
        if (
            not values
            or len(set(values)) != len(values)
            or any(not value.strip() for value in values)
        ):
            message = "Supply nonempty unique device targets"
            raise ValueError(message)
        return values


class DeviceParameterApplyItem(SDKModel):
    """Actual per-device outcome; unknown IDs may be absent."""

    device_id: DeviceIdentity
    success: StrictBool
    error: str | None = None


class DeviceLabelListResponse(DeviceEnvelope[tuple[DeviceLabel, ...]]):
    """Label listing envelope."""


class DeviceLabelsCreateResponse(DeviceEnvelope[tuple[DeviceLabel, ...]]):
    """Created label records and their IDs."""


class DeviceConfigVariableListResponse(
    DeviceEnvelope[tuple[DeviceConfigVariable, ...]]
):
    """Default configuration view envelope."""


class DeviceConfigVariableResponse(DeviceEnvelope[DeviceConfigVariable]):
    """Created/updated configuration record."""


class DeviceVPNResponse(DeviceEnvelope[Daemon]):
    """Actual daemon resource acknowledging a VPN change."""


class DeviceParameterApplyResponse(
    DeviceEnvelope[tuple[DeviceParameterApplyItem, ...]]
):
    """Reported Parameter outcomes without synthetic unknown-target entries."""
