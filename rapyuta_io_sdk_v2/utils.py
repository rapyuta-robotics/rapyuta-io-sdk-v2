# -*- coding: utf-8 -*-
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
import asyncio
import json
import os
import sys
import typing
from functools import wraps

import httpx
from munch import Munch, munchify

import rapyuta_io_sdk_v2.exceptions as exceptions


def handle_server_errors(response: httpx.Response):
    status_code = response.status_code

    if status_code < 400:
        return

    err = ""
    try:
        err = response.json().get("error")
    except json.JSONDecodeError:
        err = response.text

    # 404 Not Found
    if status_code == httpx.codes.NOT_FOUND:
        raise exceptions.HttpNotFoundError(err)
    # 405 Method Not Allowed
    if status_code == httpx.codes.METHOD_NOT_ALLOWED:
        raise exceptions.MethodNotAllowedError(err)
    # 409 Conflict
    if status_code == httpx.codes.CONFLICT:
        raise exceptions.HttpAlreadyExistsError(err)
    # 500 Internal Server Error
    if status_code == httpx.codes.INTERNAL_SERVER_ERROR:
        raise exceptions.InternalServerError(err)
    # 501 Not Implemented
    if status_code == httpx.codes.NOT_IMPLEMENTED:
        raise exceptions.NotImplementedError(err)
    # 502 Bad Gateway
    if status_code == httpx.codes.BAD_GATEWAY:
        raise exceptions.BadGatewayError(err)
    # 503 Service Unavailable
    if status_code == httpx.codes.SERVICE_UNAVAILABLE:
        raise exceptions.ServiceUnavailableError(err)
    # 504 Gateway Timeout
    if status_code == httpx.codes.GATEWAY_TIMEOUT:
        raise exceptions.GatewayTimeoutError(err)
    # 401 UnAuthorize Access
    if status_code == httpx.codes.UNAUTHORIZED:
        raise exceptions.UnauthorizedAccessError(err)

    # Anything else that is not known
    if status_code > 504:
        raise exceptions.UnknownError(err)


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


# Decorator to handle server errors and munchify response
def handle_and_munchify_response(func) -> typing.Callable:
    """Decorator to handle server errors and munchify response.

    Args:
        func (callable): The function to decorate.
    """

    @wraps(func)
    async def async_wrapper(*args, **kwargs) -> Munch:
        response = await func(*args, **kwargs)
        handle_server_errors(response)
        return munchify(response.json())

    @wraps(func)
    def sync_wrapper(*args, **kwargs) -> Munch:
        response = func(*args, **kwargs)
        handle_server_errors(response)
        return munchify(response.json())

    if asyncio.iscoroutinefunction(func):
        return async_wrapper

    return sync_wrapper


def walk_pages(
    func: typing.Callable,
    *args,
    limit: int = 50,
    cont: int = 0,
    **kwargs,
) -> typing.Generator:
    """A generator function to paginate through list API results.

    Args:
        func (callable): The API function to call, must accept `cont` and `limit` as arguments.
        *args: Positional arguments to pass to the API function.
        limit (int, optional): Maximum number of items to return. Defaults to 50.
        cont (int, optional): Initial continuation token. Defaults to 0.
        **kwargs: Additional keyword arguments to pass to the API function.

    Yields:
        Munch: Each item from the API response.
    """
    while True:
        data = func(cont, limit, *args, **kwargs)

        items = data.get("items", [])
        if not items:
            break

        for item in items:
            yield munchify(item)

        # Update `cont` for the next page
        cont = data.get("metadata", {}).get("continue")
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
        Munch: Each item from the API response.
    """
    while True:
        data = await func(cont, limit, *args, **kwargs)

        items = data.get("items", [])
        if not items:
            break

        for item in items:
            yield munchify(item)

        # Update `cont` for the next page
        cont = data.get("metadata", {}).get("continue")
        if cont is None:
            break
