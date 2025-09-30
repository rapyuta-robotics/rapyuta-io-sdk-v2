"""Pydantic models for ManagedService resource."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, ListMeta

# --- ManagedServiceProvider Models ---


class ManagedServiceProvider(BaseModel):
    """Managed service provider model."""

    name: str = Field(description="Name of the provider")


class ManagedServiceProviderList(BaseModel):
    """List of managed service providers."""

    metadata: ListMeta | None = Field(default=None, description="List metadata")
    items: list[ManagedServiceProvider] | None = Field(
        default=[], description="List of providers"
    )


# --- ManagedServiceInstance Models ---


class ManagedServiceInstanceSpec(BaseModel):
    """Specification for ManagedServiceInstance resource."""

    provider: str = Field(description="The provider for the managed service")
    config: Any = Field(
        default=None, description="Configuration object for the managed service as JSON"
    )


class ManagedServiceInstanceStatus(BaseModel):
    """Status for ManagedServiceInstance resource."""

    status: Literal["Pending", "Error", "Success", "Deleting", "Unknown"] | None = Field(
        default=None, description="Current status of the managed service"
    )
    error: str | None = Field(
        default=None, description="Error message if any", alias="errorMessage"
    )
    provider: dict[str, Any] | None = Field(
        default=None, description="Provider-specific status information as JSON"
    )


class ManagedServiceInstance(BaseModel):
    """Managed service instance model."""

    apiVersion: str | None = Field(default=None, description="API version")
    kind: str | None = Field(default=None, description="Resource kind")
    metadata: BaseMetadata = Field(description="Resource metadata")
    spec: ManagedServiceInstanceSpec | None = Field(
        default=None, description="Instance specification"
    )
    status: ManagedServiceInstanceStatus | None = Field(
        default=None, description="Instance status"
    )


class ManagedServiceInstanceListOption(BaseList[ManagedServiceInstance]):
    """List options for ManagedServiceInstance."""

    providers: list[str] | None = Field(default=None, description="Filter by providers")


class ManagedServiceInstanceList(BaseList[ManagedServiceInstance]):
    """List of managed service instances."""

    pass


# --- ManagedServiceBinding Models ---


class ManagedServiceBindingSpec(BaseModel):
    """Specification for ManagedServiceBinding resource."""

    provider: str | None = Field(
        default=None, description="The provider for the managed service"
    )
    instance: str | None = Field(
        default=None, description="The instance name/ID to bind to"
    )
    environment: dict[str, str] | None = Field(
        default=None, description="Environment variables"
    )
    config: Any = Field(default=None, description="Configuration object as JSON")
    throwaway: bool | None = Field(
        default=None, description="Whether this is a throwaway binding"
    )


class ManagedServiceBindingStatus(BaseModel):
    """Status for ManagedServiceBinding resource."""

    # TODO: Update fields as needed
    pass


class ManagedServiceBinding(BaseModel):
    """Managed service binding model."""

    apiVersion: str | None = Field(default=None, description="API version")
    kind: str | None = Field(default=None, description="Resource kind")
    metadata: BaseMetadata = Field(description="Resource metadata")
    spec: ManagedServiceBindingSpec = Field(description="Binding specification")
    status: ManagedServiceBindingStatus | None = Field(
        default=None, description="Binding status"
    )


class ManagedServiceBindingListOption(BaseModel):
    """List options for ManagedServiceBinding."""

    # Add specific options as needed
    pass


class ManagedServiceBindingList(BaseList[ManagedServiceBinding]):
    """List of managed service bindings."""

    pass
