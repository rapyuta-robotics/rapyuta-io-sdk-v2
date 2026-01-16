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
# from rapyuta_io_sdk_v2.config import Configuration
import json
import os
import sys
import typing

import httpx

import rapyuta_io_sdk_v2.exceptions as exceptions


def handle_server_errors(response: httpx.Response):
    status_code: int = response.status_code

    if status_code < 400:
        return

    err = ""
    try:
        err = response.json().get("error")
    except json.JSONDecodeError:
        err = response.text

    # If err is empty, use exception type and status code
    def format_err(exc_name):
        return f"{exc_name} (status_code={status_code})" if not err else err

    if status_code == httpx.codes.BAD_REQUEST:
        raise exceptions.MethodNotAllowedError(format_err("MethodNotAllowedError"))
    if status_code == httpx.codes.FORBIDDEN:
        raise exceptions.MethodNotAllowedError(format_err("MethodNotAllowedError"))
    if status_code == httpx.codes.NOT_FOUND:
        raise exceptions.HttpNotFoundError(format_err("HttpNotFoundError"))
    if status_code == httpx.codes.METHOD_NOT_ALLOWED:
        raise exceptions.MethodNotAllowedError(format_err("MethodNotAllowedError"))
    if status_code == httpx.codes.CONFLICT:
        raise exceptions.HttpAlreadyExistsError(format_err("HttpAlreadyExistsError"))
    if status_code == httpx.codes.INTERNAL_SERVER_ERROR:
        raise exceptions.InternalServerError(format_err("InternalServerError"))
    if status_code == httpx.codes.NOT_IMPLEMENTED:
        raise exceptions.NotImplementedError(format_err("NotImplementedError"))
    if status_code == httpx.codes.BAD_GATEWAY:
        raise exceptions.BadGatewayError(format_err("BadGatewayError"))
    if status_code == httpx.codes.SERVICE_UNAVAILABLE:
        raise exceptions.ServiceUnavailableError(format_err("ServiceUnavailableError"))
    if status_code == httpx.codes.GATEWAY_TIMEOUT:
        raise exceptions.GatewayTimeoutError(format_err("GatewayTimeoutError"))
    if status_code == httpx.codes.UNAUTHORIZED:
        raise exceptions.UnauthorizedAccessError(format_err("UnauthorizedAccessError"))

    if status_code > 400:
        raise exceptions.UnknownError(format_err("UnknownError"))


def get_default_app_dir(app_name: str) -> str:
    """Get the default application directory based on OS."""
    # On Windows
    if os.name == "nt":
        appdata = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if appdata:
            return os.path.join(appdata, app_name)

    # On macOS
    if sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~"), "Library", "Application Support", app_name
        )

    # On Linux and other Unix-like systems
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(xdg_config_home, app_name)


def walk_pages(
    func: typing.Callable,
    *args,
    limit: int = 50,
    cont: int = 0,
    **kwargs,
):
    """A generator function to paginate through list API results.

    Args:
        func (callable): The API function to call, must accept `cont` and `limit` as arguments.
        *args: Positional arguments to pass to the API function.
        limit (int, optional): Maximum number of items to return. Defaults to 50.
        cont (int, optional): Initial continuation token. Defaults to 0.
        **kwargs: Additional keyword arguments to pass to the API function.

    Yields:
        Dict[str, Any]: Each item from the API response.
    """
    while True:
        call_kwargs = dict(kwargs or {})
        if "cont" not in call_kwargs:
            call_kwargs["cont"] = cont
        if "limit" not in call_kwargs:
            call_kwargs["limit"] = limit

        data = func(*args, **call_kwargs)

        items = getattr(data, "items", None) or []
        if not items:
            break

        yield items

        cont: int | None = getattr(getattr(data, "metadata", {}), "continue_", None)
        if cont is None:
            break


async def walk_pages_async(
    func: typing.Callable,
    *args,
    limit: int = 50,
    cont: int = 0,
    **kwargs,
) -> typing.AsyncGenerator:
    """A generator function to paginate through list API results.

    Args:
        func (callable): The API function to call, must accept `cont` and `limit` as arguments.
        *args: Positional arguments to pass to the API function.
        limit (int, optional): Maximum number of items to return. Defaults to 50.
        cont (int, optional): Initial continuation token. Defaults to 0.
        **kwargs: Additional keyword arguments to pass to the API function.

    Yields:
        Dict[str, Any]: Each item from the API response.
    """
    while True:
        call_kwargs = dict(kwargs or {})
        if "cont" not in call_kwargs:
            call_kwargs["cont"] = cont
        if "limit" not in call_kwargs:
            call_kwargs["limit"] = limit

        data = await func(*args, **call_kwargs)

        items = getattr(data, "items", None) or []
        if not items:
            break

        yield items

        cont: int | None = getattr(getattr(data, "metadata", {}), "continue_", None)
        if cont is None:
            break
