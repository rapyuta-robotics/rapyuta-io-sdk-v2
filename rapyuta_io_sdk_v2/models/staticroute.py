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

"""Pydantic models for StaticRoute resource validation.

This module contains Pydantic models that correspond to the StaticRoute JSON schema,
providing validation for StaticRoute resources to help users identify missing or
incorrect fields.
"""

import re
from typing import Literal

from pydantic import Field, field_validator

from rapyuta_io_sdk_v2.models.base import SDKModel

from .utils import BaseList, BaseMetadata, BaseObject


class StaticRouteSpec(SDKModel):
    """Specification for StaticRoute resource."""

    url: str | None = Field(default=None, description="URL for the static route")
    source_ip_range: list[str] | None = Field(
        default=None,
        description="List of source IP ranges in CIDR notation",
        alias="sourceIPRange",
    )

    @field_validator("source_ip_range")
    @staticmethod
    def validate_ip_ranges(v: list[str] | None) -> list[str] | None:
        """Validate IP range format (CIDR notation).

        Args:
            v: Field value supplied to the validator.
        """
        ip_pattern = (
            r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}(?:/([1-9]|1\d|2\d|3[0-2]))?$"
        )
        if v is not None:
            for ip_range in v:
                if not re.match(ip_pattern, ip_range):
                    message = (
                        f"Invalid IP range format: {ip_range}. "
                        "Must be a valid CIDR notation (e.g., 192.168.1.0/24)"
                    )
                    raise ValueError(message)
        return v


class StaticRouteStatus(SDKModel):
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
    """StaticRoute resource model for validation.

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
    """Paginated static route resources."""
