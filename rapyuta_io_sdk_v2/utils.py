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

import httpx

import rapyuta_io_sdk_v2.exceptions as exceptions
from munch import munchify


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
def handle_and_munchify_response(func):
    async def async_wrapper(*args, **kwargs):
        response = await func(*args, **kwargs)
        handle_server_errors(response)
        return munchify(response.json())

    def sync_wrapper(*args, **kwargs):
        response = func(*args, **kwargs)
        handle_server_errors(response)
        return munchify(response.json())

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def handle_auth_token(func):
    async def async_wrapper(self, *args, **kwargs):
        response = await func(self, *args, **kwargs)
        handle_server_errors(response)
        self.config.auth_token = response.json()["data"].get("token")
        return self.config.auth_token

    def sync_wrapper(self, *args, **kwargs):
        response = func(self, *args, **kwargs)
        handle_server_errors(response)
        self.config.auth_token = response.json()["data"].get("token")
        return self.config.auth_token

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def walk_pages(func):
    def wrapper(self, *args, **kwargs):
        result = {"items": []}

        limit = kwargs.pop("limit", 50)
        limit = int(limit) if limit else 50

        cont = kwargs.pop("cont", 0)
        cont = int(cont) if cont else 0

        while True:
            response = func(self, cont, limit, **kwargs)
            handle_server_errors(response)

            data = response.json()
            items = data.get("items", [])
            if not items:
                break

            cont = data.get("metadata", {}).get("continue", None)
            if cont is None:
                break

            result["items"].extend(items)

            # Stop if we reach the limit
            if limit is not None and len(result["items"]) >= limit:
                result["items"] = result["items"][:limit]
                return munchify(result)

        return munchify(result)

    return wrapper
