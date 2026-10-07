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
import os
import sys

import httpx

import rapyuta_io_sdk_v2.exceptions as exceptions


def handle_server_errors(response: httpx.Response) -> None:
    """Raise the precise SDK exception for HTTP failures."""
    status_code = response.status_code
    if status_code < 400:
        return
    try:
        details = response.json()
    except (ValueError, UnicodeDecodeError):
        details = response.text
    if isinstance(details, dict):
        error = details.get("error") or details.get("message")
    else:
        error = details
    error_types = {
        400: exceptions.BadRequestError,
        401: exceptions.UnauthorizedAccessError,
        403: exceptions.PermissionDeniedError,
        404: exceptions.HttpNotFoundError,
        405: exceptions.MethodNotAllowedError,
        409: exceptions.HttpAlreadyExistsError,
        422: exceptions.ValidationError,
        500: exceptions.InternalServerError,
        501: exceptions.NotImplementedError,
        502: exceptions.BadGatewayError,
        503: exceptions.ServiceUnavailableError,
        504: exceptions.GatewayTimeoutError,
    }
    error_type = error_types.get(status_code, exceptions.UnknownError)
    message = (
        str(error) if error else f"{error_type.__name__} (status_code={status_code})"
    )
    raise error_type(message, status_code=status_code, response=response, details=details)


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
