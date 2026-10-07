"""Internal helpers shared by the sync and async Device Management methods."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
import httpx

from rapyuta_io_sdk_v2.exceptions import BadRequestError
from rapyuta_io_sdk_v2.models.device import DeviceCommandResponse
from rapyuta_io_sdk_v2.utils import handle_server_errors


def _unwrap(response: httpx.Response) -> Any:
    """Check HTTP and v1 JSON envelope errors, then return response.data."""
    handle_server_errors(response)
    try:
        payload = response.json()
    except (ValueError, UnicodeDecodeError):
        if not response.content:
            return None
        return response.text
    if isinstance(payload, Mapping):
        envelope = payload.get("response")
        failed = payload.get("status") == "error" or payload.get("success") is False
        if failed:
            error = payload.get("error") or payload.get("message")
            if not error and isinstance(envelope, Mapping):
                error = envelope.get("error") or envelope.get("message")
            raise BadRequestError(
                str(error or "Device Management API request failed"),
                status_code=response.status_code,
                response=response,
                details=payload,
            )
        if isinstance(envelope, Mapping) and "data" in envelope:
            return envelope["data"]
    return payload


def _require_device_ids(device_ids: Sequence[str]) -> list[str]:
    if isinstance(device_ids, (str, bytes)):
        raise TypeError("device_ids must be a sequence of strings")
    values = list(device_ids)
    if not values or any(not isinstance(item, str) or not item for item in values):
        raise ValueError("device_ids must contain at least one non-empty string")
    return values


def _command_response(
    payload: Any, *, response: httpx.Response | None = None
) -> DeviceCommandResponse:
    if payload is None:
        command_response = DeviceCommandResponse()
    elif isinstance(payload, Mapping) and not (
        {"jid", "data", "status"} & payload.keys()
    ):
        command_response = DeviceCommandResponse(data=payload)
    elif isinstance(payload, Mapping):
        command_response = DeviceCommandResponse.model_validate(payload)
    else:
        command_response = DeviceCommandResponse(data=payload)

    if response is None:
        return command_response

    envelope_status = None
    try:
        body = response.json()
    except (ValueError, UnicodeDecodeError):
        body = None
    if (
        isinstance(body, Mapping)
        and isinstance(body.get("response"), Mapping)
        and "data" in body["response"]
    ):
        status = body.get("status")
        envelope_status = status if isinstance(status, str) else None

    return command_response.model_copy(
        update={
            "http_status_code": response.status_code,
            "envelope_status": envelope_status,
        }
    )
