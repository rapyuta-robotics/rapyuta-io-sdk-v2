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


"""Exceptions raised for rapyuta.io HTTP errors."""


class AuthenticationError(Exception):
    """Exception raised for errors in the authentication process."""

    def __init__(self, message: str = "Authentication failed") -> None:
        """Initialize the exception with the supplied error message.

        Args:
            message: Error message reported to the caller.
        """
        self.message = message
        super().__init__(self.message)


class LoggedOutError(Exception):
    """Authentication credentials are absent or have expired."""

    def __init__(self, message: str = "Not Authenticated") -> None:
        """Initialize the exception with the supplied error message.

        Args:
            message: Error message reported to the caller.
        """
        self.message = message
        super().__init__(self.message)


class HttpNotFoundError(Exception):
    """The requested resource could not be found."""

    def __init__(self, message: str = "resource not found") -> None:
        """Initialize the exception with the supplied error message.

        Args:
            message: Error message reported to the caller.
        """
        self.message = message
        super().__init__(self.message)


class HttpAlreadyExistsError(Exception):
    """The requested resource conflicts with an existing resource."""

    def __init__(self, message: str = "resource already exists") -> None:
        """Initialize the exception with the supplied error message.

        Args:
            message: Error message reported to the caller.
        """
        self.message = message
        super().__init__(self.message)


class ValidationError(Exception):
    """SDK configuration or resource input is invalid."""

    def __init__(self, message: str | None = None) -> None:
        """Initialize the exception with the supplied error message.

        Args:
            message: Error message reported to the caller.
        """
        self.message = message
        super().__init__(self.message)


class MethodNotAllowedError(Exception):
    """The server rejected the request method or operation."""

    def __init__(self, message: str = "method not allowed") -> None:
        """Initialize the exception with the supplied error message.

        Args:
            message: Error message reported to the caller.
        """
        self.message = message
        super().__init__(self.message)


class InternalServerError(Exception):
    """The server encountered an internal error."""

    def __init__(self, message: str = "internal server error") -> None:
        """Initialize the exception with the supplied error message.

        Args:
            message: Error message reported to the caller.
        """
        self.message = message
        super().__init__(self.message)


# Retain the exported SDK exception name for backwards compatibility.
class NotImplementedError(Exception):  # noqa: A001
    """The server does not implement the requested operation."""

    def __init__(self, message: str = "not implemented") -> None:
        """Initialize the exception with the supplied error message.

        Args:
            message: Error message reported to the caller.
        """
        self.message = message
        super().__init__(self.message)


class BadGatewayError(Exception):
    """An upstream gateway returned an invalid response."""

    def __init__(self, message: str = "bad gateway") -> None:
        """Initialize the exception with the supplied error message.

        Args:
            message: Error message reported to the caller.
        """
        self.message = message
        super().__init__(self.message)


class UnauthorizedAccessError(Exception):
    """The caller lacks permission to access the resource."""

    def __init__(self, message: str = "unauthorized permission access") -> None:
        """Initialize the exception with the supplied error message.

        Args:
            message: Error message reported to the caller.
        """
        self.message = message
        super().__init__(self.message)


class GatewayTimeoutError(Exception):
    """The gateway timed out while contacting an upstream service."""

    def __init__(self, message: str = "gateway timeout") -> None:
        """Initialize the exception with the supplied error message.

        Args:
            message: Error message reported to the caller.
        """
        self.message = message
        super().__init__(self.message)


class ServiceUnavailableError(Exception):
    """The service is temporarily unavailable."""

    def __init__(self, message: str = "service unavailable") -> None:
        """Initialize the exception with the supplied error message.

        Args:
            message: Error message reported to the caller.
        """
        self.message = message
        super().__init__(self.message)


class UnknownError(Exception):
    """The server returned an unmapped HTTP error status."""

    def __init__(self, message: str = "unknown error") -> None:
        """Initialize the exception with the supplied error message.

        Args:
            message: Error message reported to the caller.
        """
        self.message = message
        super().__init__(self.message)
