# Copyright 2024 Rapyuta Robotics
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""HTTP error handling and resource pagination utilities."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from yaml import safe_load
from yaml.reader import ReaderError

from rapyuta_io_sdk_v2 import exceptions

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

_HTTP_ERROR_TYPES: dict[int, type[Exception]] = {
    httpx.codes.BAD_REQUEST: exceptions.MethodNotAllowedError,
    httpx.codes.FORBIDDEN: exceptions.MethodNotAllowedError,
    httpx.codes.NOT_FOUND: exceptions.HttpNotFoundError,
    httpx.codes.METHOD_NOT_ALLOWED: exceptions.MethodNotAllowedError,
    httpx.codes.CONFLICT: exceptions.HttpAlreadyExistsError,
    httpx.codes.INTERNAL_SERVER_ERROR: exceptions.InternalServerError,
    httpx.codes.NOT_IMPLEMENTED: exceptions.NotImplementedError,
    httpx.codes.BAD_GATEWAY: exceptions.BadGatewayError,
    httpx.codes.SERVICE_UNAVAILABLE: exceptions.ServiceUnavailableError,
    httpx.codes.GATEWAY_TIMEOUT: exceptions.GatewayTimeoutError,
    httpx.codes.UNAUTHORIZED: exceptions.UnauthorizedAccessError,
}


def _get_page(data: object) -> tuple[list[Any], int | None]:
    if isinstance(data, dict):
        return data.get("items", []), data.get("metadata", {}).get("continue")
    items = getattr(data, "items", [])
    metadata = getattr(data, "metadata", {})
    return items, getattr(metadata, "continue_", None)


def handle_server_errors(response: httpx.Response) -> None:
    """Raise the SDK exception associated with an HTTP error response.

    Args:
        response: HTTP response whose status and error body should be inspected.
    """
    status_code = response.status_code
    if status_code < httpx.codes.BAD_REQUEST:
        return
    try:
        error = response.json().get("error")
    except json.JSONDecodeError:
        error = response.text
    error_type = _HTTP_ERROR_TYPES.get(status_code, exceptions.UnknownError)
    message = error or f"{error_type.__name__} (status_code={status_code})"
    raise error_type(message)


def decode_config_key_content(response: httpx.Response) -> object:
    """Decode textual config keys as YAML and preserve binary keys as bytes.

    Args:
        response: Successful config-key download response.
    """
    media_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
    media_type = media_type.lower()
    textual = (
        media_type.startswith("text/")
        or media_type.endswith(("+json", "+yaml"))
        or media_type
        in (
            "",
            "application/json",
            "application/yaml",
            "application/x-yaml",
            "application/vnd.yaml",
        )
    )
    if not textual:
        return response.content
    try:
        return safe_load(response.content.decode(response.encoding or "utf-8"))
    except (UnicodeDecodeError, ReaderError):
        # Undeclared binary bodies must also survive without lossy text decoding.
        return response.content


def get_default_app_dir(app_name: str) -> str:
    """Return the platform-specific directory for application configuration.

    Args:
        app_name: Application directory name.
    """
    if os.name == "nt":
        appdata = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if appdata:
            return str(Path(appdata) / app_name)
    if sys.platform == "darwin":
        return str(Path.home() / "Library" / "Application Support" / app_name)
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return str(Path(xdg_config_home) / app_name)


def walk_pages(
    func: Callable[..., object],
    *args: object,
    limit: int = 50,
    cont: int = 0,
    **kwargs: object,
) -> Iterator[list[Any]]:
    """Yield item lists from dictionary or SDK-model pagination responses.

    Args:
        func: API function accepting continuation and limit keyword arguments.
        *args: Positional arguments forwarded to the API function.
        limit: Maximum number of items requested per page.
        cont: Initial continuation token.
        **kwargs: Additional API arguments, including pagination overrides.

    Yields:
        The items from each nonempty page.
    """
    while True:
        call_kwargs = dict(kwargs)
        call_kwargs.setdefault("cont", cont)
        call_kwargs.setdefault("limit", limit)
        items, cont_next = _get_page(func(*args, **call_kwargs))
        if not items:
            break
        yield items
        if cont_next is None or len(items) < limit:
            break
        cont = cont_next


async def walk_pages_async(
    func: Callable[..., Awaitable[object]],
    *args: object,
    limit: int = 50,
    cont: int = 0,
    **kwargs: object,
) -> AsyncIterator[list[Any]]:
    """Yield item lists from dictionary or SDK-model pagination responses.

    Args:
        func: API function accepting continuation and limit keyword arguments.
        *args: Positional arguments forwarded to the API function.
        limit: Maximum number of items requested per page.
        cont: Initial continuation token.
        **kwargs: Additional API arguments, including pagination overrides.

    Yields:
        The items from each nonempty page.
    """
    while True:
        call_kwargs = dict(kwargs)
        call_kwargs.setdefault("cont", cont)
        call_kwargs.setdefault("limit", limit)
        items, cont_next = _get_page(await func(*args, **call_kwargs))
        if not items:
            break
        yield items
        if cont_next is None or len(items) < limit:
            break
        cont = cont_next
