# Copyright 2026 Rapyuta Robotics
"""Typed Device command operations and immutable workflow outcomes."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    ConfigDict,
    Field,
    RootModel,
    StrictBool,
    StrictStr,
    field_validator,
)

from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.device import (
    DeviceEmptyData,
    DeviceEnvelope,
    DeviceRequest,
)

type CommandBudget = Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]


def command_targets(values: tuple[str, ...]) -> tuple[str, ...]:
    """Require explicit, unique, nonblank command targets."""
    if not values or len(set(values)) != len(values):
        message = "Supply nonempty unique device targets"
        raise ValueError(message)
    if any(not value.strip() for value in values):
        message = "Device targets must not be blank"
        raise ValueError(message)
    return values


def nonblank(value: str) -> str:
    """Preserve exact text while rejecting blank strings."""
    if not value.strip():
        message = "Value must not be blank"
        raise ValueError(message)
    return value


class DeviceCommand(DeviceRequest):
    """One command request; timeout limits remote execution."""

    device_ids: tuple[StrictStr, ...]
    cmd: StrictStr
    shell: StrictStr | None = None
    runas: StrictStr | None = None
    cwd: StrictStr | None = None
    env: dict[StrictStr, StrictStr] = Field(default_factory=dict, repr=False)
    bg: StrictBool = False
    run_async: StrictBool = False
    timeout: CommandBudget = 300
    _targets = field_validator("device_ids")(command_targets)
    _command = field_validator("cmd")(nonblank)

    @field_validator("env")
    @classmethod
    def validate_environment(cls, value: dict[str, str]) -> dict[str, str]:
        """Validate POSIX variable names without changing values."""
        if any(re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", key) is None for key in value):
            message = "Invalid environment variable name"
            raise ValueError(message)
        return value


class DeviceCommandResultQuery(DeviceRequest):
    """Explicit targets for one command result lookup."""

    device_ids: tuple[StrictStr, ...]
    _targets = field_validator("device_ids")(command_targets)


class DeviceCommandOutputs(RootModel[dict[StrictStr, StrictStr]]):
    """Output map; an empty string is a received response."""


def job_identity(value: str) -> str:
    """Validate an opaque, URL-routable job identifier without coercion."""
    nonblank(value)
    if re.fullmatch(r"(?!\.{1,2}$)[^/\\\x00-\x1f\x7f]+", value) is None:
        message = "Job identity must be one literal path segment"
        raise ValueError(message)
    return value


def optional_job_identity(value: str | None) -> str | None:
    """Validate a known JID while retaining unknown remote acceptance."""
    return None if value is None else job_identity(value)


class _CommandJobIdentity(SDKModel):
    """Recover only a validated identity from a malformed acknowledgment."""

    jid: StrictStr
    _jid = field_validator("jid")(job_identity)


class _CommandJobAcknowledgment(_CommandJobIdentity):
    """Recognize job shape without treating a string output key as identity."""

    minions: tuple[StrictStr, ...]


class DeviceCommandJob(DeviceRequest):
    """Opaque deferred command acknowledgment."""

    jid: StrictStr
    minions: tuple[StrictStr, ...]
    _jid = field_validator("jid")(job_identity)


class DeviceCommandSubmissionData(RootModel[DeviceCommandOutputs | DeviceCommandJob]):
    """Mode-validated immediate/launch outputs or deferred job."""


class DeviceCommandSubmissionResponse(DeviceEnvelope[DeviceCommandSubmissionData]):
    """One command submission response."""


class DeviceCommandResultResponse(DeviceEnvelope[DeviceCommandOutputs]):
    """One result snapshot, without polling."""


class DeviceCommandPendingData(DeviceRequest):
    """The exact server marker conflating unknown and incomplete jobs."""

    error: Literal["Job not found or incomplete"]
    data: DeviceEmptyData


class DeviceCommandPendingResponse(DeviceRequest):
    """Only the corresponding HTTP400 retrieval envelope is pending."""

    status: Literal["error"]
    response: DeviceCommandPendingData


class DeviceCommandFailureStage(StrEnum):
    """Attributable command workflow failure stages."""

    VALIDATION = "validation"
    SUBMISSION = "submission"
    RETRIEVAL = "retrieval"
    CONTRACT = "contract"
    INCOMPLETE_RESULT = "incomplete_result"
    TIMEOUT = "timeout"
    CANCELLATION = "cancellation"


class DeviceCommandWaitOptions(SDKModel):
    """Immutable local waiting budget, separate from execution timeout."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    wait_timeout: CommandBudget = 300
    poll_interval: CommandBudget = 10


class DeviceCommandDeviceResult(SDKModel):
    """One immutable received output, including empty output."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    device_guid: StrictStr
    output: StrictStr


class DeviceCommandOutcome(SDKModel):
    """Ordered immutable snapshot of command progress."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    requested_devices: tuple[StrictStr, ...]
    jid: StrictStr | None = None
    _jid = field_validator("jid")(optional_job_identity)
    responses: tuple[DeviceCommandDeviceResult, ...]
    missing_devices: tuple[StrictStr, ...]


class DeviceCommandFailure(SDKModel):
    """Redacted immutable failure identity; outputs live in the outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    _jid = field_validator("jid")(optional_job_identity)
    stage: DeviceCommandFailureStage
    message: Annotated[StrictStr, Field(min_length=1)]
    jid: StrictStr | None = None
    requested_devices: tuple[StrictStr, ...]
    missing_devices: tuple[StrictStr, ...]
