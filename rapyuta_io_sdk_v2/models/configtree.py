"""ConfigTree envelopes and request bodies; key paths retain their exact spelling."""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field, RootModel

from .utils import BaseList, BaseMetadata, BaseObject, SDKModel


class ConfigTreeMetadata(BaseMetadata):
    model_config = ConfigDict(extra="allow")
    name: str | None = None


class ConfigTreeKey(SDKModel):
    model_config = ConfigDict(extra="allow")
    data: str | None = None
    permissions: str | None = None
    checksum: str | None = None
    content_type: str | None = Field(default=None, alias="contentType")
    content_length: int | None = Field(default=None, alias="contentLength")
    metadata: dict[str, Any] | None = None


class ConfigTreeRevision(SDKModel):
    model_config = ConfigDict(extra="allow")
    metadata: ConfigTreeMetadata | None = None
    author: str | None = None
    message: str | None = None
    committed: bool | None = None
    keys: dict[str, ConfigTreeKey] | None = None


class ConfigTree(BaseObject):
    model_config = ConfigDict(extra="allow")
    kind: str = "ConfigTree"
    metadata: ConfigTreeMetadata | None = None
    head: ConfigTreeRevision | None = None
    keys: dict[str, ConfigTreeKey] | None = None


class ConfigTreeList(BaseList[ConfigTree]):
    pass


class ConfigTreeRevisionList(BaseList[ConfigTreeRevision]):
    pass


class ConfigTreeKeyUpdate(RootModel[dict[str, ConfigTreeKey]]):
    """Batch update whose JSON body is a mapping from exact paths to keys."""


class ConfigTreeRevisionCommit(SDKModel):
    author: str | None = None
    message: str | None = None
    metadata: ConfigTreeMetadata | None = None


class ConfigTreeKeyRename(SDKModel):
    metadata: ConfigTreeMetadata


class ConfigTreeActionResponse(RootModel[dict[str, Any]]):
    """Opaque action response, preserved until the API defines a stable schema."""
