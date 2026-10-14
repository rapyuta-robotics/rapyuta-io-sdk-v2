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

"""Typed chart sources and repository metadata, separate from platform payloads."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    ConfigDict,
    Field,
    JsonValue,
    StrictStr,
    field_validator,
    model_validator,
)

from rapyuta_io_sdk_v2.models.base import SDKModel

_SELECTOR_PARTS = 2


def split_selector(selector: str) -> tuple[str, str | None]:
    """Parse an exact chart name/version without trimming or ordering versions."""
    parts = selector.split(":")
    if len(parts) > _SELECTOR_PARTS or not all(parts):
        msg = "chart selector requires name or name:version"
        raise ValueError(msg)
    return parts[0], parts[1] if len(parts) == _SELECTOR_PARTS else None


class ChartSource(SDKModel):
    """Explicit local directory/archive or remote repository selection."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["directory", "archive", "repository"]
    path: Path | None = None
    selector: StrictStr | None = None
    repository: StrictStr | None = None
    branch: StrictStr | None = None

    @field_validator("path")
    @classmethod
    def valid_local_path(cls, value: Path | None) -> Path | None:
        """Reject NUL-containing paths as invalid configuration without I/O."""
        if value is not None and "\x00" in str(value):
            msg = "chart path must not contain NUL characters"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        """Reject contradictory source tags and validate repository selectors."""
        if self.kind == "repository":
            self._validate_repository()
        else:
            self._validate_local()
        return self

    def _validate_repository(self) -> None:
        if self.selector is None or self.path is not None:
            msg = "repository source requires a selector and forbids path"
            raise ValueError(msg)
        split_selector(self.selector)

    def _validate_local(self) -> None:
        if self.path is None or any(
            value is not None for value in (self.selector, self.repository, self.branch)
        ):
            msg = "local source requires path and forbids repository fields"
            raise ValueError(msg)

    @classmethod
    def from_directory(cls, path: str | Path) -> Self:
        """Select a directory without reading or checking its existence."""
        return cls(kind="directory", path=Path(path))

    @classmethod
    def from_archive(cls, path: str | Path) -> Self:
        """Select a compressed tar archive without accessing the filesystem."""
        return cls(kind="archive", path=Path(path))

    @classmethod
    def from_repository(
        cls, selector: str, *, repository: str | None = None, branch: str | None = None
    ) -> Self:
        """Select an exact repository chart with optional index/branch override."""
        return cls(
            kind="repository", selector=selector, repository=repository, branch=branch
        )


class ChartMetadata(SDKModel):
    """Package identity and descriptive metadata with preserved extra fields."""

    model_config = ConfigDict(frozen=True, extra="allow", populate_by_name=True)
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)
    name: StrictStr
    version: StrictStr
    description: str | None = None
    api_version: str | None = Field(default=None, alias="apiVersion")

    @field_validator("name", "version")
    @classmethod
    def nonempty_identity(cls, value: str) -> str:
        """Preserve identity spelling while rejecting blank identifiers."""
        if not value.strip():
            msg = "chart name and version must be non-empty strings"
            raise ValueError(msg)
        return value


class ChartEntry(ChartMetadata):
    """One ordered repository version and its advertised package locations."""

    urls: tuple[StrictStr, ...] = ()
    created: str | datetime | None = None
    digest: str | None = None


class ChartIndex(SDKModel):
    """Repository entries preserving version order and optional index metadata."""

    model_config = ConfigDict(frozen=True, extra="allow", populate_by_name=True)
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)
    entries: dict[str, tuple[ChartEntry, ...]]
    api_version: str | None = Field(default=None, alias="apiVersion")
    generated: str | datetime | None = None

    @field_validator("entries")
    @classmethod
    def validate_entries(
        cls, entries: dict[str, tuple[ChartEntry, ...]]
    ) -> dict[str, tuple[ChartEntry, ...]]:
        """Require named keys and matching entry identities without deduplication."""
        for name, versions in entries.items():
            if not name or any(entry.name != name for entry in versions):
                msg = "index keys must be non-empty and match entry names"
                raise ValueError(msg)
        return entries


__all__ = ["ChartEntry", "ChartIndex", "ChartMetadata", "ChartSource"]
