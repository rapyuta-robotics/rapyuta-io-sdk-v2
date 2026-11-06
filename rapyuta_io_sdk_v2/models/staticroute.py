"""
Pydantic models for StaticRoute resource validation.

This module contains Pydantic models that correspond to the StaticRoute JSON schema,
providing validation for StaticRoute resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer

from .utils import BaseList, BaseMetadata, BaseObject


class StaticRouteRateLimit(BaseModel):
    """HTTP/HTTPS requests per client IP, per Traefik instance.

    The server validates Go duration strings and supplies defaults for omitted
    period (1s) and burst. No defaults are materialized by the SDK.
    """

    average: int = Field(gt=0, le=1_000_000, strict=True)
    period: str | None = Field(default=None, strict=True)
    burst: int | None = Field(default=None, ge=0, le=2**63 - 1, strict=True)

    @model_serializer(mode="wrap")
    def serialize_rate_limit(self, handler):
        data = handler(self)
        for field in ("period", "burst"):
            if field not in self.model_fields_set:
                data.pop(field, None)
        return data


class StaticRouteSpec(BaseModel):
    """Specification for StaticRoute resource."""

    model_config = ConfigDict(populate_by_name=True)

    rate_limit: StaticRouteRateLimit | None = Field(
        default=None,
        alias="rateLimit",
        description="Optional HTTP/HTTPS rate limit; omitted or null disables limiting",
    )

    @model_serializer(mode="wrap")
    def serialize_spec(self, handler, info):
        data = handler(self)
        if "rate_limit" not in self.model_fields_set:
            data.pop("rateLimit" if info.by_alias else "rate_limit", None)
        return data

    url: str | None = Field(default=None, description="URL for the static route")
    source_ip_range: list[str] | None = Field(
        default=None,
        description="List of source IP ranges in CIDR notation",
        alias="sourceIPRange",
    )

    @field_validator("source_ip_range")
    @staticmethod
    def validate_ip_ranges(v: list[str] | None) -> list[str] | None:
        """Validate IP range format (CIDR notation)."""
        ip_pattern = (
            r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}(?:/([1-9]|1\d|2\d|3[0-2]))?$"
        )
        if v is not None:
            for ip_range in v:
                if not re.match(ip_pattern, ip_range):
                    raise ValueError(
                        f"Invalid IP range format: {ip_range}. Must be a valid CIDR notation (e.g., 192.168.1.0/24)"
                    )
        return v


class StaticRouteStatus(BaseModel):
    """Status for StaticRoute resource."""

    status: Literal["Available", "Unavailable"] | None = Field(
        default=None, description="Status of the static route"
    )
    package_guid: str | None = Field(
        default=None,
        description="Package ID associated with the static route",
        alias="packageID",
    )
    deployment_guid: str | None = Field(
        default=None,
        description="Deployment ID associated with the static route",
        alias="deploymentID",
    )


class StaticRoute(BaseObject):
    """
    StaticRoute resource model for validation.

    This model validates StaticRoute resources according to the JSON schema,
    helping users identify missing or incorrect configuration.
    A named route for the Deployment endpoint.
    """

    kind: Literal["StaticRoute"] = Field(
        default="StaticRoute", description="Resource kind, must be 'StaticRoute'"
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
