# Copyright 2026 Rapyuta Robotics
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

"""Structured failures raised by applier preparation and execution."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from rapyuta_io_sdk_v2.models.applier import (
        ApplierResult,
        OperationFailure,
        ResourceIdentity,
        SourceLocation,
    )


class ApplierError(Exception):
    """Base exception for the high-level applier API."""


class ApplierValidationError(ApplierError):
    """Invalid source, rendered manifest, identity, or dependency graph."""

    def __init__(
        self,
        message: str,
        *,
        source: SourceLocation | None = None,
        category: str = "validation",
        identities: Iterable[ResourceIdentity] = (),
    ) -> None:
        """Initialize a validation diagnostic with optional source context."""
        super().__init__(message)
        self.source = source
        self.category = category
        self.identities = tuple(identities)


class ApplierUsageError(ApplierError):
    """Invalid facade/client use, such as a sync call inside an event loop."""


class UnsupportedResourceOperationError(ApplierError):
    """A declared resource kind does not support the requested operation."""

    def __init__(
        self,
        message: str,
        *,
        identity: ResourceIdentity | None = None,
        operation: str | None = None,
    ) -> None:
        """Initialize an unsupported-operation diagnostic."""
        super().__init__(message)
        self.identity = identity
        self.operation = operation


class MissingResourceContextError(ApplierError):
    """A live operation lacks its supplied client or required routing context."""

    def __init__(
        self,
        message: str,
        *,
        resource: ResourceIdentity | None = None,
        operation: str | None = None,
        required_context: Iterable[str] = (),
    ) -> None:
        """Initialize a missing-client or missing-scope diagnostic."""
        super().__init__(message)
        self.resource = resource
        self.operation = operation
        self.required_context = tuple(required_context)


class ApplierExecutionError(ApplierError):
    """Lifecycle failure carrying the settled immutable operation result."""

    def __init__(
        self,
        message: str,
        *,
        result: ApplierResult,
        causes: Iterable[OperationFailure] = (),
    ) -> None:
        """Initialize an execution error with its settled result snapshot."""
        super().__init__(message)
        self.result = result
        self.causes = tuple(causes)


class ReadinessError(ApplierError):
    """A resource entered a terminal state or exhausted its readiness budget."""

    def __init__(
        self,
        message: str,
        *,
        identity: ResourceIdentity,
        category: str,
        last_state: str | None = None,
    ) -> None:
        """Initialize a readiness diagnostic for one resource identity."""
        super().__init__(message)
        self.identity = identity
        self.category = category
        self.last_state = last_state


class SopsDecryptionError(ApplierError):
    """Safe SOPS-helper diagnostic that never retains command output."""

    def __init__(
        self,
        source: str | Path,
        *,
        category: str,
        return_code: int | None = None,
        guidance: str,
    ) -> None:
        """Initialize a safe SOPS diagnostic without retaining command output."""
        self.source = str(source)
        self.category = category
        self.return_code = return_code
        self.guidance = guidance
        super().__init__(f"SOPS {category} error for {self.source}: {guidance}")


__all__ = [
    "ApplierError",
    "ApplierExecutionError",
    "ApplierUsageError",
    "ApplierValidationError",
    "MissingResourceContextError",
    "ReadinessError",
    "SopsDecryptionError",
    "UnsupportedResourceOperationError",
]
