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
import json
import os
import sys

import httpx

from rapyuta_io_sdk_v2.exceptions import HttpAlreadyExistsError, HttpNotFoundError
from munch import munchify
from asyncer import asyncify


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
        raise HttpNotFoundError(err)
    # 405 Method Not Allowed
    if status_code == httpx.codes.METHOD_NOT_ALLOWED:
        raise Exception("method not allowed")
    # 409 Conflict
    if status_code == httpx.codes.CONFLICT:
        raise HttpAlreadyExistsError()
    # 500 Internal Server Error
    if status_code == httpx.codes.INTERNAL_SERVER_ERROR:
        raise Exception("internal server error")
    # 501 Not Implemented
    if status_code == httpx.codes.NOT_IMPLEMENTED:
        raise Exception("not implemented")
    # 502 Bad Gateway
    if status_code == httpx.codes.BAD_GATEWAY:
        raise Exception("bad gateway")
    # 503 Service Unavailable
    if status_code == httpx.codes.SERVICE_UNAVAILABLE:
        raise Exception("service unavailable")
    # 504 Gateway Timeout
    if status_code == httpx.codes.GATEWAY_TIMEOUT:
        raise Exception("gateway timeout")
    # 401 UnAuthorize Access
    if status_code == httpx.codes.UNAUTHORIZED:
        raise Exception("unauthorized permission access")

    # Anything else that is not known
    if status_code > 504:
        raise Exception("unknown server error")


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
# def handle_and_munchify_response(func):
#     def wrapper(*args, **kwargs):
#         response = func(*args, **kwargs)
#         handle_server_errors(response)
#         return munchify(response.json())

#     return wrapper


def handle_and_munchify_response(func):
    def wrapper(*args, **kwargs):
        # Call the synchronous function
        response = func(*args, **kwargs)
        handle_server_errors(response)
        return munchify(response.json())

    async def async_wrapper(*args, **kwargs):
        # Call the function asynchronously
        response = await asyncify(func)(*args, **kwargs)
        # handle_server_errors(response)
        # return munchify(response.json())
        return response

    def wrapper_selector(*args, **kwargs):
        # Determine if the first argument is an httpx.AsyncClient
        if (
            args
            and hasattr(args[0], "__class__")
            and "AsyncClient" in args[0].__class__.__name__
        ):
            # if asyncio.iscoroutinefunction(func):
            return async_wrapper(*args, **kwargs)  # Use async wrapper
        return wrapper(*args, **kwargs)  # Use sync wrapper

    return wrapper_selector


def handle_auth_token(func):
    def wrapper(self, *args, **kwargs):
        response = func(self, *args, **kwargs)
        handle_server_errors(response)
        self.config.auth_token = response.json()["data"].get("token")
        return self.config.auth_token

    return wrapper
