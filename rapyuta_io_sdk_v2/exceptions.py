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


"""Exceptions raised for rapyuta.io HTTP errors and upload failures."""

from __future__ import annotations

from asyncio import CancelledError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.models.device_command import (
        DeviceCommandFailure,
        DeviceCommandOutcome,
    )
    from rapyuta_io_sdk_v2.models.parameter import (
        ParameterUploadFailure,
        ParameterUploadResult,
    )


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


class DeviceContractError(UnknownError):
    """A Device service payload violates its documented response contract."""

    def __init__(self, message: str, *, jid: str | None = None) -> None:
        """Retain a validated job identity when malformed acknowledgment permits.

        Args:
            message: Redacted contract failure description.
            jid: Validated job identifier, if received despite malformed data.
        """
        self.jid = jid
        super().__init__(message)


class ParameterUploadError(Exception):
    """An upload failed after the operations recorded in partial_result."""

    def __init__(
        self, failure: ParameterUploadFailure, partial_result: ParameterUploadResult
    ) -> None:
        """Retain typed failure/progress; the helper chains the original cause.

        Args:
            failure: Attributable path/stage and redacted message.
            partial_result: Immutable snapshot of acknowledged operations.
        """
        self.failure = failure
        self.partial_result = partial_result
        super().__init__(f"{failure.stage}: {failure.path}: {failure.message}")


# Public cancellation name follows asyncio conventions and the SDK contract.
class ParameterUploadCancelled(CancelledError):  # noqa: N818
    """Cancellation preserving known upload progress and task semantics."""

    def __init__(
        self, failure: ParameterUploadFailure, partial_result: ParameterUploadResult
    ) -> None:
        """Retain cancellation context and the immutable acknowledged progress.

        Args:
            failure: Last path/stage observed when cancellation arrived.
            partial_result: Snapshot including completed identities and skips.
        """
        self.failure = failure
        self.partial_result = partial_result
        super().__init__(f"{failure.stage}: {failure.path}: {failure.message}")


class DeviceCommandError(Exception):
    """Command failure with immutable known progress and a chained cause."""

    def __init__(
        self, failure: DeviceCommandFailure, partial_result: DeviceCommandOutcome
    ) -> None:
        """Retain matching failure and outcome identities.

        Args:
            failure: Redacted failure stage and identities.
            partial_result: Immutable outputs known at failure.
        """
        _check_command_snapshot(failure, partial_result)
        self.failure = failure
        self.partial_result = partial_result
        super().__init__(f"{failure.stage}: {failure.message}")


# Public timeout name follows TimeoutError and the documented SDK contract.
class DeviceCommandTimeout(DeviceCommandError, TimeoutError):  # noqa: N818
    """Local command waiting expired; remote execution may continue."""


# Public cancellation name preserves the SDK's asyncio naming convention.
class DeviceCommandCancelled(CancelledError):  # noqa: N818
    """External cancellation carrying acknowledged progress."""

    def __init__(
        self, failure: DeviceCommandFailure, partial_result: DeviceCommandOutcome
    ) -> None:
        """Retain cancellation identity and task cancellation semantics.

        Args:
            failure: Redacted cancellation context.
            partial_result: Immutable outputs known at cancellation.
        """
        _check_command_snapshot(failure, partial_result)
        self.failure = failure
        self.partial_result = partial_result
        super().__init__(f"{failure.stage}: {failure.message}")


def _check_command_snapshot(
    failure: DeviceCommandFailure, result: DeviceCommandOutcome
) -> None:
    """Require exact identity equality between paired snapshots."""
    fields = ("jid", "requested_devices", "missing_devices")
    if any(getattr(failure, field) != getattr(result, field) for field in fields):
        message = "Command failure and outcome identities must match"
        raise ValueError(message)
