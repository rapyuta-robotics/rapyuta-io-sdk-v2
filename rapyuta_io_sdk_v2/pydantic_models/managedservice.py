"""Pydantic models for ManagedService resource."""

from typing import Any, Literal
from pydantic import BaseModel, Field

from rapyuta_io_sdk_v2.pydantic_models.utils import BaseMetadata, BaseList


class ManagedServiceMetadata(BaseMetadata):
    """Metadata for ManagedService resource."""

    # Inherits all common fields from BaseMetadata
    pass


class ManagedServiceSpec(BaseModel):
    """Specification for ManagedService resource."""

    provider: Literal["elasticsearch", "headscalevpn"] = Field(
        description="The provider for the managed service"
    )
    config: dict[str, Any] = Field(
        description="Configuration object for the managed service"
    )


class ManagedService(BaseModel):
    """Managed service model."""

    apiVersion: str | None = None
    kind: str | None = None
    metadata: BaseMetadata
    spec: ManagedServiceSpec


class ManagedServiceList(BaseList[ManagedService]):
    """List of managed services using BaseList."""

    pass
