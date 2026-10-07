"""Wire models for the legacy Parameter service."""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from .base import SDKModel


class ParameterNode(SDKModel):
    """A recursive Parameter tree node returned by the v1 service."""

    model_config = ConfigDict(extra="allow")

    type: str
    name: str | None = None
    data: Any = None
    blob_ref_id: str | None = Field(default=None, alias="blobRefId")
    children: list[ParameterNode] = Field(default_factory=list)


class ParameterBlob(SDKModel):
    """A signed download URL for a binary Parameter file."""

    model_config = ConfigDict(extra="allow")

    id: int | str = Field(alias="ID")
    signed_url: str | None = Field(default=None, alias="signedUrl")


class ParameterBlobList(SDKModel):
    """Binary references returned by the treeblobs endpoint."""

    model_config = ConfigDict(extra="allow")

    blob_refs: list[ParameterBlob] = Field(default_factory=list, alias="blobRefs")
