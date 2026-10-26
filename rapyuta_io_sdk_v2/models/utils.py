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

"""HTTP error handling and resource pagination utilities."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator

from rapyuta_io_sdk_v2.models.base import SDKModel


class BaseObject(SDKModel):
    """API version shared by rapyuta.io resource manifests."""

    api_version: Literal["api.rapyuta.io/v2", "apiextensions.rapyuta.io/v1"] = Field(
        default="api.rapyuta.io/v2", alias="apiVersion"
    )


class BaseMetadata(SDKModel):
    """Base metadata class containing common fields across all resource types.

    Based on server ObjectMeta struct that holds all the meta information
    related to a resource such as name, timestamps, etc.
    """

    # Name of the resource
    name: str = Field(description="Name of the resource")

    # GUID is a globally unique identifier on Rapyuta.io platform
    guid: str | None = Field(default=None, description="GUID of the resource")

    # Project and Organization information
    project_guid: str | None = Field(
        alias="projectGUID",
        default=None,
        description="Project GUID",
    )
    organization_guid: str | None = Field(
        alias="organizationGUID",
        default=None,
        description="Organization GUID",
    )
    organization_creator_guid: str | None = Field(
        alias="organizationCreatorGUID",
        default=None,
        description="Organization creator GUID",
    )

    # Creator information
    creator_guid: str | None = Field(
        alias="creatorGUID",
        default=None,
        description="Creator GUID",
    )

    # Labels are key-value pairs associated with the resource
    labels: dict[str, str] | None = Field(
        default=None, description="Labels as key-value pairs"
    )

    # Region information
    region: str | None = Field(default=None, description="Region")

    # Timestamps
    created_at: str | None = Field(
        alias="createdAt",
        default=None,
        description="Time of resource creation",
    )
    updated_at: str | None = Field(
        alias="updatedAt",
        default=None,
        description="Time of resource update",
    )
    deleted_at: str | None = Field(
        alias="deletedAt",
        default=None,
        description="Time of resource deletion",
    )

    @field_validator("created_at", "updated_at", "deleted_at", mode="before")
    @classmethod
    def coerce_datetime_to_str(cls, v: object) -> object:
        """Serialize datetime timestamps as ISO 8601 strings.

        Args:
            v: Field value supplied to the validator.
        """
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    # Human-readable names
    organization_name: str | None = Field(
        alias="organizationName",
        default=None,
        description="Organization name",
    )
    short_guid: str | None = Field(
        alias="shortGUID", default=None, description="Short GUID"
    )
    project_name: str | None = Field(
        alias="projectName",
        default=None,
        description="Project name",
    )


class ListMeta(SDKModel):
    """Metadata for list responses based on Kubernetes ListMeta."""

    continue_: int | None = Field(
        default=None,
        alias="continue",
        description="Continue token for pagination (int64)",
    )


class BaseList[T](SDKModel):
    """Base list class for validating list method results.

    Corresponds to Go struct:
    type ProjectList struct {
        metav1.TypeMeta `json:",inline,omitempty"`
        ListMeta        `json:"metadata,omitempty"`
        Items           []Project `json:"items,omitempty"`
    }
    """

    # TypeMeta fields (inline)
    kind: str | None = Field(
        default=None,
        description=(
            "Kind is a string value representing the REST resource this "
            "object represents"
        ),
    )
    api_version: str | None = Field(
        alias="apiVersion",
        default="api.rapyuta.io/v2",
        description=(
            "APIVersion defines the versioned schema of this "
            "representation of an object"
        ),
    )

    # ListMeta
    metadata: ListMeta | None = Field(default=None, description="List metadata")

    # Items
    items: list[T] | None = Field(default=[], description="List of resource items")


class Depends(SDKModel):
    """Resource reference identified by name or GUID."""

    name_or_guid: str = Field(
        validation_alias=AliasChoices("nameOrGUID", "nameOrGuid"),
        serialization_alias="nameOrGUID",
    )


class PackageDepends(SDKModel):
    """Versioned package reference required by a resource."""

    kind: Literal["Package", "package"] = "Package"
    name_or_guid: str = Field(
        validation_alias=AliasChoices("nameOrGUID", "nameOrGuid"),
        serialization_alias="nameOrGUID",
    )
    # Must name a concrete version: an empty version cannot identify the
    # Package this dependency refers to. Templated manifests render an empty
    # string when the value is not supplied, which would otherwise validate.
    version: str = Field(min_length=1)


class SecretDepends(SDKModel):
    """Secret reference required by a resource."""

    kind: Literal["Secret", "secret"] = "Secret"
    name_or_guid: str | None = Field(
        validation_alias=AliasChoices("nameOrGUID", "nameOrGuid"),
        serialization_alias="nameOrGUID",
    )


class DiskDepends(Depends):
    """Disk reference required by a resource."""

    kind: Literal["Disk", "disk"] = "Disk"


class StaticRouteDepends(Depends):
    """Static route reference required by a resource."""

    kind: Literal["StaticRoute", "staticroute"] = "StaticRoute"


class NetworkDepends(Depends):
    """Network reference required by a resource."""

    kind: Literal["Network", "network"] = "Network"


class DeviceDepends(Depends):
    """Device reference required by a resource."""

    name_or_guid: str = Field(
        validation_alias=AliasChoices("nameOrGUID", "nameOrGuid"),
        serialization_alias="nameOrGUID",
    )
    kind: Literal["Device", "device"] = "Device"


class DeploymentDepends(Depends):
    """Deployment prerequisite with an optional readiness wait."""

    kind: Literal["Deployment", "deployment"] = "Deployment"
    name_or_guid: str = Field(
        validation_alias=AliasChoices("nameOrGUID", "nameOrGuid"),
        serialization_alias="nameOrGUID",
    )
    wait: bool = False


RestartPolicy = Literal["always", "never", "onfailure"]
Runtime = Literal["device", "cloud"]
ExecutableStatusType = Literal[
    "error", "running", "pending", "terminating", "terminated", "unknown"
]
DeploymentStatusType = Literal["Running", "Pending", "Error", "Unknown", "Stopped"]
# --- Constants matching Go server-side ---
DeploymentPhase = Literal[
    "InProgress",
    "Provisioning",
    "Succeeded",
    "FailedToUpdate",
    "FailedToStart",
    "Stopped",
]
Architecture = Literal["amd64", "arm32v7", "arm64v8"]


class Subject(SDKModel):
    """User, group, or service account receiving an authorization grant."""

    kind: Literal["User", "UserGroup", "ServiceAccount"] | None = None
    name: str | None = None
    guid: str | None = None

    @model_validator(mode="after")
    def ensure_name_or_guid(self) -> Subject:
        """Require a resource name or GUID."""
        if self.name is None and self.guid is None:
            message = "either 'name' or 'guid' should be specified"
            raise ValueError(message)

        return self


class Domain(SDKModel):
    """Organization, project, or group in which a grant applies."""

    kind: Literal["UserGroup", "Project", "Organization"] | None = None
    name: str | None = None
    guid: str | None = None

    @model_validator(mode="after")
    def ensure_name_or_guid(self) -> Domain:
        """Require a resource name or GUID."""
        if self.name is None and self.guid is None:
            message = "either 'name' or 'guid' should be specified"
            raise ValueError(message)

        return self


class SecretKeyRef(SDKModel):
    """Secret key reference and its optional server-resolved value."""

    name: str | None = Field(default=None, description="Name of the Secret resource")
    key: str | None = Field(default=None, description="Key within the Secret")
    value: str | None = Field(
        default=None, description="Resolved value (read-only, returned by server)"
    )


class ValueFrom(SDKModel):
    """Environment variable value supplied by a secret key."""

    secret_key_ref: SecretKeyRef | None = Field(
        default=None,
        alias="secretKeyRef",
        description="Selects a key of a Secret in the same namespace",
    )


def named_resource_dependency(resource: Subject | Domain) -> list[str]:
    """Return a dependency for a resource identified by kind and name.

    Args:
        resource: Subject or domain whose named resource must exist first.
    """
    if resource.kind is not None and resource.name is not None:
        return [f"{resource.kind.lower()}:{resource.name}"]
    return []
