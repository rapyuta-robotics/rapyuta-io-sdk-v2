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


from typing import Any

import httpx


class SDKError(Exception):
    """An SDK error retaining the HTTP response and parsed error details."""

    def __init__(
        self,
        message: str = "SDK error",
        *,
        status_code: int | None = None,
        response: httpx.Response | None = None,
        details: Any = None,
    ):
        self.message = message
        self.status_code = status_code
        self.response = response
        self.details = details
        super().__init__(message)


class AuthenticationError(SDKError):
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, **kwargs)


class LoggedOutError(SDKError):
    def __init__(self, message: str = "Not Authenticated", **kwargs):
        super().__init__(message, **kwargs)


class HttpNotFoundError(SDKError):
    def __init__(self, message: str = "resource not found", **kwargs):
        super().__init__(message, **kwargs)


class HttpAlreadyExistsError(SDKError):
    def __init__(self, message: str = "resource already exists", **kwargs):
        super().__init__(message, **kwargs)


class ValidationError(SDKError):
    def __init__(self, message: str = "validation failed", **kwargs):
        super().__init__(message, **kwargs)


class MethodNotAllowedError(SDKError):
    def __init__(self, message: str = "method not allowed", **kwargs):
        super().__init__(message, **kwargs)


class InternalServerError(SDKError):
    def __init__(self, message: str = "internal server error", **kwargs):
        super().__init__(message, **kwargs)


class NotImplementedError(SDKError):
    def __init__(self, message: str = "not implemented", **kwargs):
        super().__init__(message, **kwargs)


class BadGatewayError(SDKError):
    def __init__(self, message: str = "bad gateway", **kwargs):
        super().__init__(message, **kwargs)


class UnauthorizedAccessError(SDKError):
    def __init__(self, message: str = "unauthorized access", **kwargs):
        super().__init__(message, **kwargs)


class GatewayTimeoutError(SDKError):
    def __init__(self, message: str = "gateway timeout", **kwargs):
        super().__init__(message, **kwargs)


class ServiceUnavailableError(SDKError):
    def __init__(self, message: str = "service unavailable", **kwargs):
        super().__init__(message, **kwargs)


class UnknownError(SDKError):
    def __init__(self, message: str = "unknown error", **kwargs):
        super().__init__(message, **kwargs)


class BadRequestError(SDKError):
    def __init__(self, message: str = "bad request", **kwargs):
        super().__init__(message, **kwargs)


class PermissionDeniedError(SDKError):
    def __init__(self, message: str = "permission denied", **kwargs):
        super().__init__(message, **kwargs)
