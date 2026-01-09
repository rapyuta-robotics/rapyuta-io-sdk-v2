"""
Pydantic models for ServiceAccount resource validation.

This module mirrors the Go `ServiceAccount` and related types from the
`package extensions` snippet provided by the user.
"""

from typing import Literal
from datetime import datetime

from pydantic import BaseModel, Field
from pydantic import field_validator

from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    Domain,
)


class ServiceAccountBinding(BaseModel):
    domain: Domain
    role_names: list[str] = Field(default_factory=list, alias="roleNames")


class ServiceAccountSpec(BaseModel):
    description: str | None = None
    roles: list[ServiceAccountBinding] | None = None


class ServiceAccount(BaseObject):
    """ServiceAccount model."""

    kind: Literal["ServiceAccount", "serviceaccount"] | None = "ServiceAccount"
    metadata: BaseMetadata
    spec: ServiceAccountSpec | None = None

    def list_dependencies(self) -> list[str] | None:
        dependencies: list[str] = []

        # Process service account roles and their domains
        if self.spec and self.spec.roles is not None:
            for role_binding in self.spec.roles:
                # Add domain dependency
                if (
                    role_binding.domain.kind is not None
                    and role_binding.domain.name is not None
                ):
                    domain = (
                        f"{role_binding.domain.kind.lower()}:{role_binding.domain.name}"
                    )
                    dependencies.append(domain)

                # Add role dependencies
                if role_binding.role_names is not None:
                    for role in role_binding.role_names:
                        dependencies.append(f"role:{role}")

        return dependencies


class ServiceAccountList(BaseList[ServiceAccount]):
    """List of service accounts using BaseList."""

    pass


class ServiceAccountToken(BaseModel):
    owner: str | None = None
    expiry_at: datetime | None = Field(default=None, alias="expiry_at")

    @field_validator("expiry_at")
    @classmethod
    def check_expiry_at_iso8601(cls, v):
        if v is not None and v.tzinfo is None:
            raise ValueError("expiry_at must be an ISO8601 datetime with timezone info")
        return v


class ServiceAccountTokenInfo(BaseModel):
    id: int | None = None
    token: str | None = None
    expiry_at: datetime | None = Field(default=None, alias="expiry_at")

    @field_validator("expiry_at")
    @classmethod
    def check_expiry_at_iso8601(cls, v):
        if v is not None and v.tzinfo is None:
            raise ValueError("expiry_at must be an ISO8601 datetime with timezone info")
        return v


class ServiceAccountTokenList(BaseList[ServiceAccountTokenInfo]):
    """List of service account tokens."""

    pass
