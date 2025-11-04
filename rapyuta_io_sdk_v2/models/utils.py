from typing import Generic, Literal, Self, TypeVar

from pydantic import AliasChoices, BaseModel, Field, model_validator

# Type variable for generic list items
T = TypeVar("T")


class BaseObject(BaseModel):
    api_version: Literal["api.rapyuta.io/v2", "apiextensions.rapyuta.io/v1"] = Field(
        default="api.rapyuta.io/v2", alias="apiVersion"
    )


class BaseMetadata(BaseModel):
    """Base metadata class containing common fields across all resource types.

    Based on server ObjectMeta struct that holds all the meta information
    related to a resource such as name, timestamps, etc.
    """

    # Name of the resource
    name: str = Field(description="Name of the resource")

    # GUID is a globally unique identifier on Rapyuta.io platform
    guid: str | None = Field(default=None, description="GUID of the resource")

    # Project and Organization information
    projectGUID: str | None = Field(default=None, description="Project GUID")
    organizationGUID: str | None = Field(default=None, description="Organization GUID")
    organizationCreatorGUID: str | None = Field(
        default=None, description="Organization creator GUID"
    )

    # Creator information
    creatorGUID: str | None = Field(default=None, description="Creator GUID")

    # Labels are key-value pairs associated with the resource
    labels: dict[str, str] | None = Field(
        default=None, description="Labels as key-value pairs"
    )

    # Region information
    region: str | None = Field(default=None, description="Region")

    # Timestamps
    createdAt: str | None = Field(default=None, description="Time of resource creation")
    updatedAt: str | None = Field(default=None, description="Time of resource update")
    deletedAt: str | None = Field(default=None, description="Time of resource deletion")

    # Human-readable names
    organizationName: str | None = Field(default=None, description="Organization name")
    shortGUID: str | None = Field(default=None, description="Short GUID")
    projectName: str | None = Field(default=None, description="Project name")


class ListMeta(BaseModel):
    """Metadata for list responses based on Kubernetes ListMeta."""

    continue_: int | None = Field(
        default=None,
        alias="continue",
        description="Continue token for pagination (int64)",
    )


class BaseList(BaseModel, Generic[T]):
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
    apiVersion: str | None = Field(
        default="api.rapyuta.io/v2",
        description="APIVersion defines the versioned schema of this representation of an object",
    )

    # ListMeta
    metadata: ListMeta | None = Field(default=None, description="List metadata")

    # Items
    items: list[T] | None = Field(default=[], description="List of resource items")


class Depends(BaseModel):
    name_or_guid: str = Field(validation_alias=AliasChoices("nameOrGuid", "nameOrGUID"))


class PackageDepends(BaseModel):
    kind: Literal["Package", "package"] = "Package"
    name_or_guid: str = Field(alias="nameOrGUID")
    version: str


class DiskDepends(Depends):
    kind: Literal["Disk", "disk"] = "Disk"


class StaticRouteDepends(Depends):
    kind: Literal["StaticRoute", "staticroute"] = "StaticRoute"


class NetworkDepends(Depends):
    kind: Literal["Network", "network"] = "Network"


class DeviceDepends(Depends):
    kind: Literal["Device", "device"] = "Device"


class DeploymentDepends(Depends):
    kind: Literal["Deployment", "deployment"] = "Deployment"
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


class Subject(BaseModel):
    kind: Literal["User", "UserGroup", "ServiceAccount"] | None = None
    name: str | None = None
    guid: str | None = None

    @model_validator(mode="after")
    def ensure_name_or_guid(self) -> Self:
        if self.name is None and self.guid is None:
            raise ValueError("either 'name' or 'guid' should be specified")

        return self


class Domain(BaseModel):
    kind: Literal["UserGroup", "Project", "Organization"] | None = None
    name: str | None = None
    guid: str | None = None

    @model_validator(mode="after")
    def ensure_name_or_guid(self) -> Self:
        if self.name is None and self.guid is None:
            raise ValueError("either 'name' or 'guid' should be specified")

        return self
