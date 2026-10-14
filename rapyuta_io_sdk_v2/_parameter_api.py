# Copyright 2026 Rapyuta Robotics

"""Pure routing and wire validation for the v1 Parameter service."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import quote

from rapyuta_io_sdk_v2.exceptions import UnknownError, ValidationError
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.parameter import (
    ParameterErrorResponse,
    ParameterUploadMetadata,
)
from rapyuta_io_sdk_v2.utils import handle_server_errors

if TYPE_CHECKING:
    import httpx

    from rapyuta_io_sdk_v2._client_options import HeaderOptions
    from rapyuta_io_sdk_v2.config import Configuration

TREE_NAME = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]{0,49}$")
CHILD_PATH = re.compile(
    r"^/([0-9A-Za-z][0-9A-Za-z._-]{0,49}/)*"
    r"[0-9A-Za-z][0-9A-Za-z._-]{0,49}(/|\.[0-9A-Za-z.]+)?$"
)


def parameter_base(config: Configuration) -> str:
    """Resolve the core host on each operation, failing only Parameter calls."""
    host = config.hosts.get("core_api_host")
    if not host:
        message = "Parameter APIs require core_api_host or LOCAL_COREAPI_HOST"
        raise ValidationError(message)
    return f"{host.rstrip('/')}/api/paramserver"


def tree_name(name: str) -> str:
    """Validate a tree name and return its literal URL component."""
    if not TREE_NAME.fullmatch(name):
        message = f"Invalid Parameter tree name: {name!r}"
        raise ValidationError(message)
    return quote(name, safe="")


def child_path(path: str) -> str:
    """Reject unsafe paths without silently cleaning or renaming components."""
    parts = path.split("/")
    if "/" not in path or "\\" in path or any(p in {"", ".", ".."} for p in parts):
        message = f"Invalid Parameter child path: {path!r}"
        raise ValidationError(message)
    tree_name(parts[0])
    return "/".join(quote(part, safe="") for part in parts)


def blob_id(value: str) -> str:
    """Validate a positive decimal blob reference without coercing its type."""
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*", value):
        message = "blob_ref_id must be a nonzero decimal string"
        raise ValidationError(message)
    return value


def wire_payload(
    model: SDKModel, expected: type[SDKModel] | None = None
) -> dict[str, object]:
    """Revalidate a model and preserve explicit fields and wire aliases."""
    payload = model.model_dump(by_alias=True, exclude_unset=True, mode="json")
    return (
        (expected or type(model))
        .model_validate(payload)
        .model_dump(by_alias=True, exclude_unset=True, mode="json")
    )


def upload_headers(
    config: Configuration, metadata: ParameterUploadMetadata, options: HeaderOptions
) -> dict[str, str]:
    """Project typed preparation headers over generic caller header options."""
    metadata = ParameterUploadMetadata.model_validate(wire_payload(metadata))
    headers = config.get_headers(**options)
    headers.pop("X-Checksum", None)
    headers.update(
        {
            "X-Rapyuta-Params-Version": str(metadata.version),
            "Checksum": metadata.checksum,
            "Content-Type": metadata.content_type,
        }
    )
    if metadata.content_encoding is not None:
        headers["Content-Encoding"] = metadata.content_encoding
    return headers


def parameter_response[T: SDKModel](response: httpx.Response, model: type[T]) -> T:
    """Reject non-success statuses and validate the exact v1 response envelope."""
    handle_server_errors(response)
    if not response.is_success:
        message = f"Unexpected Parameter status: {response.status_code}"
        raise UnknownError(message)
    parsed = model.model_validate_json(response.content)
    # Error envelopes cannot acknowledge a write, even if they contain data.
    payload = response.json()
    if isinstance(payload, dict) and "error" in payload:
        raise UnknownError(ParameterErrorResponse.model_validate(payload).error)
    return parsed
