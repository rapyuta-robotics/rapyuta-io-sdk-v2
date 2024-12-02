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


class AuthenticationError(Exception):
    """Exception raised for errors in the authentication process."""

    def __init__(self, message="Authentication failed"):
        self.message = message
        super().__init__(self.message)


class LoggedOutError(Exception):
    def __init__(self, message="Not Authenticated"):
        self.message = message
        super().__init__(self.message)


class HttpNotFoundError(Exception):
    def __init__(self, message="resource not found"):
        self.message = message
        super().__init__(self.message)


class HttpAlreadyExistsError(Exception):
    def __init__(self, message="resource already exists"):
        self.message = message
        super().__init__(self.message)


class ValidationError(Exception):
    def __init__(self, message=None):
        self.message = message
        super().__init__(self.message)


class MethodNotAllowedError(Exception):
    def __init__(self, message="method not allowed"):
        self.message = message
        super().__init__(self.message)


class InternalServerError(Exception):
    def __init__(self, message="internal server error"):
        self.message = message
        super().__init__(self.message)


class NotImplementedError(Exception):
    def __init__(self, message="not implemented"):
        self.message = message
        super().__init__(self.message)


class BadGatewayError(Exception):
    def __init__(self, message="bad gateway"):
        self.message = message
        super().__init__(self.message)


class UnauthorizedAccessError(Exception):
    def __init__(self, message="unauthorized permission access"):
        self.message = message
        super().__init__(self.message)


class GatewayTimeoutError(Exception):
    def __init__(self, message="gateway timeout"):
        self.message = message
        super().__init__(self.message)


class ServiceUnavailableError(Exception):
    def __init__(self, message="service unavailable"):
        self.message = message
        super().__init__(self.message)


class UnknownError(Exception):
    def __init__(self, message="unknown error"):
        self.message = message
        super().__init__(self.message)
