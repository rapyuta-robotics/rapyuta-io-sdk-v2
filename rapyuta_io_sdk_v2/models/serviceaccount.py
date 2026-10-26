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

"""Pydantic models for ServiceAccount resource validation.

This module mirrors the Go `ServiceAccount` and related types from the
`package extensions` snippet provided by the user.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    Domain,
    named_resource_dependency,
)


class ServiceAccountBinding(BaseModel):
    """Roles granted to a service account within a domain."""

    domain: Domain
    role_names: list[str] = Field(default_factory=list, alias="roleNames")


class ServiceAccountSpec(BaseModel):
    """Service account description and authorization bindings."""

    description: str | None = None
    roles: list[ServiceAccountBinding] | None = None


class ServiceAccount(BaseObject):
    """ServiceAccount model."""

    kind: Literal["ServiceAccount", "serviceaccount"] | None = "ServiceAccount"
    metadata: BaseMetadata
    spec: ServiceAccountSpec | None = None

    def list_dependencies(self) -> list[str] | None:
        """Return bound domains and roles in manifest order."""
        dependencies: list[str] = []
        if self.spec is None:
            return dependencies
        for binding in self.spec.roles or []:
            dependencies.extend(named_resource_dependency(binding.domain))
            dependencies.extend(f"role:{role}" for role in binding.role_names or [])
        return dependencies


class ServiceAccountList(BaseList[ServiceAccount]):
    """List of service accounts using BaseList."""


class ServiceAccountToken(BaseModel):
    """Token ownership and timezone-aware expiration settings."""

    owner: str | None = None
    expiry_at: datetime | None = Field(default=None, alias="expiry_at")

    @field_validator("expiry_at")
    @classmethod
    def check_expiry_at_iso8601(cls, v: datetime | None) -> datetime | None:
        """Require timezone information in token expiration timestamps.

        Args:
            v: Field value supplied to the validator.
        """
        if v is not None and v.tzinfo is None:
            message = "expiry_at must be an ISO8601 datetime with timezone info"
            raise ValueError(message)
        return v


class ServiceAccountTokenInfo(BaseModel):
    """Issued token identifier, credential, and expiration time."""

    id: int | None = None
    token: str | None = None
    expiry_at: datetime | None = Field(default=None, alias="expiry_at")

    @field_validator("expiry_at")
    @classmethod
    def check_expiry_at_iso8601(cls, v: datetime | None) -> datetime | None:
        """Require timezone information in token expiration timestamps.

        Args:
            v: Field value supplied to the validator.
        """
        if v is not None and v.tzinfo is None:
            message = "expiry_at must be an ISO8601 datetime with timezone info"
            raise ValueError(message)
        return v


class ServiceAccountTokenList(BaseList[ServiceAccountTokenInfo]):
    """List of service account tokens."""
