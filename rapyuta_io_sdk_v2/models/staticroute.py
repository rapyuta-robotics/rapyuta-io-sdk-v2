"""
Pydantic models for StaticRoute resource validation.

This module contains Pydantic models that correspond to the StaticRoute JSON schema,
providing validation for StaticRoute resources to help users identify missing or
incorrect fields.
"""

from typing import Literal
from pydantic import BaseModel, Field, field_validator

from .utils import BaseList, BaseMetadata
import re


class StaticRouteSpec(BaseModel):
    """Specification for StaticRoute resource."""

    url: str | None = Field(default=None, description="URL for the static route")
    sourceIPRange: list[str] | None = Field(
        default=None, description="List of source IP ranges in CIDR notation"
    )

    @field_validator("sourceIPRange")
    @classmethod
    def validate_ip_ranges(cls, v):
        """Validate IP range format (CIDR notation)."""
        if v is not None:
            ip_pattern = (
                r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}(?:/([1-9]|1\d|2\d|3[0-2]))?$"
            )
            for ip_range in v:
                if not re.match(ip_pattern, ip_range):
                    raise ValueError(
                        f"Invalid IP range format: {ip_range}. "
                        "Must be a valid CIDR notation (e.g., 192.168.1.0/24)"
                    )
        return v


class StaticRouteStatus(BaseModel):
    """Status for StaticRoute resource."""

    status: Literal["Available", "Unavailable"] | None = Field(
        default=None, description="Status of the static route"
    )
    packageID: str | None = Field(
        default=None, description="Package ID associated with the static route"
    )
    deploymentID: str | None = Field(
        default=None, description="Deployment ID associated with the static route"
    )


class StaticRoute(BaseModel):
    """
    StaticRoute resource model for validation.

    This model validates StaticRoute resources according to the JSON schema,
    helping users identify missing or incorrect configuration.
    A named route for the Deployment endpoint.
    """

    apiVersion: Literal["apiextensions.rapyuta.io/v1", "api.rapyuta.io/v2"] = Field(
        default="api.rapyuta.io/v2",
        description="API version for the StaticRoute resource",
    )
    kind: Literal["StaticRoute"] = Field(
        description="Resource kind, must be 'StaticRoute'"
    )
    metadata: BaseMetadata = Field(description="Metadata for the StaticRoute resource")
    spec: StaticRouteSpec | None = Field(
        default=None, description="Specification for the StaticRoute resource"
    )
    status: StaticRouteStatus | None = Field(
        default=None, description="Status of the StaticRoute resource"
    )


class StaticRouteList(BaseList[StaticRoute]):
    pass
