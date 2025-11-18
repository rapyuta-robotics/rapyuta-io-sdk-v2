from pydantic import BaseModel, Field


from typing import Generic, Literal, TypeVar


# Type variable for generic list items
T = TypeVar("T")


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
    kind: str
    nameOrGUID: str  # Keep for backward compatibility, but add GUID field
    wait: bool | None = None
    version: str | None = None


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
