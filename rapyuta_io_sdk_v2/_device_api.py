# Copyright 2026 Rapyuta Robotics

"""Pure routing, payload validation, and response parsing for Device calls."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

import httpx
from pydantic import TypeAdapter
from pydantic import ValidationError as ModelValidationError

from rapyuta_io_sdk_v2.exceptions import (
    DeviceContractError,
    UnknownError,
    ValidationError,
)
from rapyuta_io_sdk_v2.models.device import (
    DeviceData,
    DeviceEnvelope,
    DeviceLabelsCreate,
    DeviceListQuery,
    DeviceUpdate,
    DeviceVPNUpdate,
)
from rapyuta_io_sdk_v2.models.device_command import (
    CommandBudget,
    DeviceCommand,
    DeviceCommandJob,
    DeviceCommandOutputs,
    DeviceCommandPendingResponse,
    DeviceCommandResultQuery,
    DeviceCommandResultResponse,
    DeviceCommandSubmissionData,
    DeviceCommandSubmissionResponse,
    _CommandJobAcknowledgment,
    _CommandJobIdentity,
)
from rapyuta_io_sdk_v2.utils import handle_server_errors

if TYPE_CHECKING:
    from pydantic import BaseModel

    from rapyuta_io_sdk_v2.config import Configuration


ASCII_SPACE = 32
ASCII_DELETE = 127


def device_base(config: Configuration) -> str:
    """Resolve the configured core service on each operation.

    Args:
        config: Supplied client's environment and service configuration.
    """
    host = config.hosts.get("core_api_host")
    if not host:
        message = "Device APIs require core_api_host or LOCAL_COREAPI_HOST"
        raise ValidationError(message)
    return f"{host.rstrip('/')}/api/device-manager/v0"


def routing_id(value: str) -> str:
    """Encode one literal nonblank routing identifier, never a path.

    Args:
        value: Device or opaque job identifier.
    """
    if not isinstance(value, str) or not value.strip():
        message = "Device routing identifier must be a nonblank string"
        raise ValidationError(message)
    if value in {".", ".."} or any(c in value for c in ("/", "\\")):
        message = "Device routing identifier must be one literal path segment"
        raise ValidationError(message)
    if any(ord(c) < ASCII_SPACE or ord(c) == ASCII_DELETE for c in value):
        message = "Device routing identifier must not contain control characters"
        raise ValidationError(message)
    return quote(value, safe="")


def record_id(value: int) -> str:
    """Validate a strict positive record identity for label/config routing.

    Args:
        value: Returned integer record identifier.
    """
    if type(value) is not int or value <= 0:
        message = "Device record identifier must be a positive integer"
        raise ValidationError(message)
    return str(value)


def wire_payload[T: BaseModel](model: T, expected: type[T]) -> object:
    """Revalidate copied model data and preserve aliases and supplied fields.

    Args:
        model: Named validated request body or query; raw dictionaries fail.
        expected: Operation's request model type.
    """
    payload = model.model_dump(by_alias=True, exclude_unset=True, mode="json")
    return expected.model_validate(payload).model_dump(
        by_alias=True, exclude_unset=True, mode="json"
    )


def device_response[T: BaseModel](response: httpx.Response, model: type[T]) -> T:
    """Validate an actual platform response without inventing result fields.

    Args:
        response: HTTP response from one platform operation.
        model: Named success response contract.
    """
    handle_server_errors(response)
    if not response.is_success:
        message = f"Unexpected Device response status: {response.status_code}"
        raise UnknownError(message)
    try:
        return model.model_validate_json(response.content)
    except ModelValidationError as error:
        message = f"Invalid Device response for {model.__name__}"
        raise DeviceContractError(message) from error


def update_payload(device_guid: str, body: DeviceUpdate) -> object:
    """Inject the validated routing identity into a fresh update body."""
    routing_id(device_guid)
    payload = wire_payload(body, DeviceUpdate)
    return dict(payload, device_id=device_guid)


def command_payload(body: DeviceCommand) -> DeviceCommand:
    """Revalidate a copied command, preserving explicit operational defaults."""
    payload = body.model_dump(by_alias=True, mode="json")
    return DeviceCommand.model_validate(payload)


def command_json(body: DeviceCommand) -> object:
    """Emit operational defaults and omit null optional strings."""
    return command_payload(body).model_dump(
        by_alias=True, mode="json", exclude_none=True
    )


def command_query(query: DeviceCommandResultQuery) -> list[tuple[str, str]]:
    """Serialize repeated singular device_id keys in caller order."""
    query = DeviceCommandResultQuery.model_validate(
        wire_payload(query, DeviceCommandResultQuery)
    )
    return [("device_id", value) for value in query.device_ids]


def command_timeout(default: httpx.Timeout, cap: float | None) -> httpx.Timeout:
    """Bound each phase by a positive finite remaining budget."""
    if cap is None:
        return default
    cap = TypeAdapter(CommandBudget).validate_python(cap)
    values = {
        name: cap if value is None else min(value, cap)
        for name, value in default.as_dict().items()
    }
    return httpx.Timeout(**values)


def command_submission(
    response: httpx.Response, body: DeviceCommand
) -> DeviceCommandSubmissionResponse:
    """Validate the returned data against the requested execution mode."""
    model = DeviceCommandJob if body.run_async and not body.bg else DeviceCommandOutputs
    try:
        parsed = device_response(response, DeviceEnvelope[model])
    except DeviceContractError as error:
        identity_model = (
            _CommandJobIdentity
            if model is DeviceCommandJob
            else _CommandJobAcknowledgment
        )
        error.jid = _known_command_job(response, identity_model, body.device_ids)
        raise
    data = DeviceCommandSubmissionData(parsed.response.data)
    return DeviceCommandSubmissionResponse(
        response=DeviceData(data=data), status="success"
    )


def command_result(
    response: httpx.Response,
) -> DeviceCommandResultResponse | DeviceCommandPendingResponse:
    """Recognize only exact retrieval pending before shared HTTP handling."""
    if response.status_code == httpx.codes.BAD_REQUEST:
        try:
            return DeviceCommandPendingResponse.model_validate_json(response.content)
        except ModelValidationError:
            pass
    return device_response(response, DeviceCommandResultResponse)


def labels_payload(body: DeviceLabelsCreate) -> object:
    """Reject empty standalone label creation, unlike registration defaults."""
    payload = wire_payload(body, DeviceLabelsCreate)
    if not payload:
        message = "Standalone label creation requires at least one label"
        raise ValidationError(message)
    return payload


def vpn_payload(body: DeviceVPNUpdate) -> object:
    """Materialize nested route defaults and retain explicit disable."""
    body = DeviceVPNUpdate.model_validate(wire_payload(body, DeviceVPNUpdate))
    return body.model_dump(by_alias=True, exclude_none=True, mode="json")


def _known_command_job(
    response: httpx.Response,
    model: type[_CommandJobIdentity],
    targets: tuple[str, ...],
) -> str | None:
    """Recover identity unless it can be a requested device's string output."""
    if "jid" in targets:
        try:
            DeviceEnvelope[DeviceCommandOutputs].model_validate_json(response.content)
        except ModelValidationError:
            pass
        else:
            return None
    try:
        parsed = DeviceEnvelope[model].model_validate_json(response.content)
    except ModelValidationError:
        return None
    return parsed.response.data.jid


def list_query(query: DeviceListQuery | None) -> object:
    """Omit null optional filters instead of sending an empty name."""
    query = DeviceListQuery.model_validate(
        wire_payload(query if query is not None else DeviceListQuery(), DeviceListQuery)
    )
    return query.model_dump(by_alias=True, exclude_none=True, mode="json")
