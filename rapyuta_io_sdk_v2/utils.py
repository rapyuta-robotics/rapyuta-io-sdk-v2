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
import http
import json
from typing import Any, Dict

import httpx

from rapyuta_io_sdk_v2.exceptions import HttpAlreadyExistsError, HttpNotFoundError


def validate_auth_token(config: Any) -> Dict:
    try:
        client = config.sync_client()
        user = client.get_authenticated_user()
        return user
    except Exception:
        raise


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
    if status_code == http.HTTPStatus.NOT_FOUND:
        raise HttpNotFoundError(err)
    # 405 Method Not Allowed
    if status_code == http.HTTPStatus.METHOD_NOT_ALLOWED:
        raise Exception("method not allowed")
    # 409 Conflict
    if status_code == http.HTTPStatus.CONFLICT:
        raise HttpAlreadyExistsError()
    # 500 Internal Server Error
    if status_code == http.HTTPStatus.INTERNAL_SERVER_ERROR:
        raise Exception("internal server error")
    # 501 Not Implemented
    if status_code == http.HTTPStatus.NOT_IMPLEMENTED:
        raise Exception("not implemented")
    # 502 Bad Gateway
    if status_code == http.HTTPStatus.BAD_GATEWAY:
        raise Exception("bad gateway")
    # 503 Service Unavailable
    if status_code == http.HTTPStatus.SERVICE_UNAVAILABLE:
        raise Exception("service unavailable")
    # 504 Gateway Timeout
    if status_code == http.HTTPStatus.GATEWAY_TIMEOUT:
        raise Exception("gateway timeout")
    # 401 UnAuthorize Access
    if status_code == http.HTTPStatus.UNAUTHORIZED:
        raise Exception("unauthorized permission access")

    # Anything else that is not known
    if status_code > 504:
        raise Exception("unknown server error")
