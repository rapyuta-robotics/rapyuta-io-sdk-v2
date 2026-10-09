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

"""Configuration trees, revisions, and key payloads matching the v2 API."""

from pydantic import Field, RootModel

from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject


class ConfigValue(SDKModel):
    """Stored key metadata and optional base64-encoded data."""

    permissions: str | None = None
    metadata: dict[str, str] | None = None
    checksum: str | None = None
    content_type: str | None = Field(default=None, alias="contentType")
    content_length: int | None = Field(default=None, alias="contentLength")
    url: str | None = None
    data: str | None = None


class ConfigTreeRevisionMetadata(BaseMetadata):
    """Revision metadata supporting label-only commit requests."""

    name: str | None = None


class ConfigTreeRevision(BaseObject):
    """Revision metadata and commit information, flattened on the wire."""

    api_version: str = Field(default="apiextensions.rapyuta.io/v1", alias="apiVersion")
    kind: str | None = None
    metadata: ConfigTreeRevisionMetadata | None = None
    parent: str | None = None
    message: str | None = None
    author: str | None = None
    committed: bool | None = None


class ConfigTree(BaseObject):
    """Configuration tree with its selected revision and key map."""

    api_version: str = Field(default="apiextensions.rapyuta.io/v1", alias="apiVersion")
    kind: str = "ConfigTree"
    metadata: BaseMetadata
    head: ConfigTreeRevision | None = None
    keys: dict[str, ConfigValue] | None = None


class ConfigTreeList(BaseList[ConfigTree]):
    """Paginated configuration trees."""

    api_version: str | None = Field(
        default="apiextensions.rapyuta.io/v1", alias="apiVersion"
    )


class ConfigTreeRevisionList(BaseList[ConfigTreeRevision]):
    """Paginated configuration tree revisions."""

    api_version: str | None = Field(
        default="apiextensions.rapyuta.io/v1", alias="apiVersion"
    )


class ConfigValues(RootModel[dict[str, ConfigValue]]):
    """Key map serialized directly, without a wrapping root property."""


class ConfigKeyRename(SDKModel):
    """New key name and optional permissions and metadata."""

    name: str
    permissions: str | None = None
    metadata: dict[str, str] | None = None


class ConfigKeyContent(RootModel[object]):
    """Decoded JSON/YAML values or raw bytes without a wrapping property.

    Preserve YAML's Python types, including dates, bytes, sets, and non-string
    mapping keys, as well as arbitrary binary downloads.
    """


class ConfigKeyUpload(RootModel[str | bytes]):
    """Raw key content sent unchanged as the HTTP request body."""
