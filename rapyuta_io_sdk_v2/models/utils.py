from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .base import SDKModel as SDKModel
from .resource import ResourceModel


def resource_key(kind: str, name: str, version: str | None = None) -> str:
    """Canonical resource and dependency identity, including Package version."""
    normalized_kind = kind.lower()
    if normalized_kind == "package":
        if not version:
            raise ValueError("Package identity requires a version")
        return f"{normalized_kind}:{name}:{version}"
    return f"{normalized_kind}:{name}"


class BaseObject(ResourceModel):
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
        default=None, description="Project GUID", alias="projectGUID"
    )
    organization_guid: str | None = Field(
        default=None, description="Organization GUID", alias="organizationGUID"
    )
    organization_creator_guid: str | None = Field(
        default=None,
        description="Organization creator GUID",
        alias="organizationCreatorGUID",
    )

    # Creator information
    creator_guid: str | None = Field(
        default=None, description="Creator GUID", alias="creatorGUID"
    )

    # Labels are key-value pairs associated with the resource
    labels: dict[str, str] | None = Field(
        default=None, description="Labels as key-value pairs"
    )

    # Region information
    region: str | None = Field(default=None, description="Region")

    # Timestamps
    created_at: str | None = Field(
        default=None, description="Time of resource creation", alias="createdAt"
    )
    updated_at: str | None = Field(
        default=None, description="Time of resource update", alias="updatedAt"
    )
    deleted_at: str | None = Field(
        default=None, description="Time of resource deletion", alias="deletedAt"
    )

    @field_validator("created_at", "updated_at", "deleted_at", mode="before")
    @classmethod
    def coerce_datetime_to_str(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    # Human-readable names
    organization_name: str | None = Field(
        default=None, description="Organization name", alias="organizationName"
    )
    short_guid: str | None = Field(
        default=None, description="Short GUID", alias="shortGUID"
    )
    project_name: str | None = Field(
        default=None, description="Project name", alias="projectName"
    )


class ListMeta(SDKModel):
    """Metadata for list responses based on Kubernetes ListMeta."""

    continue_: int | str | None = Field(
        default=None,
        alias="continue",
        description="Continuation token for pagination",
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
        description="Kind is a string value representing the REST resource this object represents",
    )
    api_version: str | None = Field(
        default="api.rapyuta.io/v2",
        description="APIVersion defines the versioned schema of this representation of an object",
        alias="apiVersion",
    )

    # ListMeta
    metadata: ListMeta | None = Field(default=None, description="List metadata")

    # Items
    items: list[T] = Field(default_factory=list, description="List of resource items")

    @field_validator("items", mode="before")
    @classmethod
    def normalize_null_items(cls, value):
        return [] if value is None else value


class Depends(SDKModel):
    name_or_guid: str = Field(
        validation_alias=AliasChoices("nameOrGUID", "nameOrGuid"),
        serialization_alias="nameOrGUID",
    )


class PackageDepends(SDKModel):
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
    kind: Literal["Secret", "secret"] = "Secret"
    name_or_guid: str | None = Field(
        validation_alias=AliasChoices("nameOrGUID", "nameOrGuid"),
        serialization_alias="nameOrGUID",
    )


class DiskDepends(Depends):
    kind: Literal["Disk", "disk"] = "Disk"


class StaticRouteDepends(Depends):
    kind: Literal["StaticRoute", "staticroute"] = "StaticRoute"


class NetworkDepends(Depends):
    kind: Literal["Network", "network"] = "Network"


class DeviceDepends(Depends):
    name_or_guid: str = Field(
        validation_alias=AliasChoices("nameOrGUID", "nameOrGuid"),
        serialization_alias="nameOrGUID",
    )
    kind: Literal["Device", "device"] = "Device"


class DeploymentDepends(Depends):
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
    kind: Literal["User", "UserGroup", "ServiceAccount"] | None = None
    name: str | None = None
    guid: str | None = None

    @model_validator(mode="after")
    def ensure_name_or_guid(self):
        if self.name is None and self.guid is None:
            raise ValueError("either 'name' or 'guid' should be specified")

        return self


class Domain(SDKModel):
    kind: Literal["UserGroup", "Project", "Organization"] | None = None
    name: str | None = None
    guid: str | None = None

    @model_validator(mode="after")
    def ensure_name_or_guid(self):
        if self.name is None and self.guid is None:
            raise ValueError("either 'name' or 'guid' should be specified")

        return self


class SecretKeyRef(SDKModel):
    name: str | None = Field(default=None, description="Name of the Secret resource")
    key: str | None = Field(default=None, description="Key within the Secret")
    value: str | None = Field(
        default=None, description="Resolved value (read-only, returned by server)"
    )


class ValueFrom(SDKModel):
    secret_key_ref: SecretKeyRef | None = Field(
        default=None,
        alias="secretKeyRef",
        description="Selects a key of a Secret in the same namespace",
    )


class AuthSubject(SDKModel):
    """Authentication service response; unversioned attributes remain opaque."""

    model_config = ConfigDict(extra="allow")
    data: dict[str, Any] | None = None
