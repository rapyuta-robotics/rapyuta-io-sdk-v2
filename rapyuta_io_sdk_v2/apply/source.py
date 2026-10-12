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

"""Typed, immutable source configuration for an applier facade."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from rapyuta_io_sdk_v2.models.base import SDKModel

type JsonValue = (
    str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
)
type PathInput = str | Path
type ValueInput = Mapping[str, JsonValue] | PathInput
type ResourceInput = SDKModel


def _snapshot(
    value: object, *, singleton_types: tuple[type, ...]
) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, singleton_types):
        return (value,)
    return tuple(value)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True, init=False)
class ManifestSource:
    """Ordered caller inputs for local manifest preparation.

    Iterable inputs are snapshotted at construction. Paths and typed resource
    instances may be combined; values are merged in the order supplied.
    """

    files: tuple[PathInput, ...]
    resources: tuple[ResourceInput, ...]
    values: tuple[ValueInput, ...]
    secrets: tuple[ValueInput, ...]
    rio: Mapping[str, JsonValue] | None

    def __init__(
        self,
        *,
        files: object = (),
        resources: object = (),
        values: object = (),
        secrets: object = (),
        rio: Mapping[str, JsonValue] | None = None,
    ) -> None:
        """Snapshot ordered input iterables without retaining mutable mappings."""
        paths = _snapshot(files, singleton_types=(str, Path))
        models = _snapshot(resources, singleton_types=(SDKModel,))
        value_sources = _snapshot(values, singleton_types=(Mapping, str, Path))
        secret_sources = _snapshot(secrets, singleton_types=(Mapping, str, Path))
        object.__setattr__(self, "files", tuple(paths))
        object.__setattr__(self, "resources", tuple(models))
        object.__setattr__(self, "values", tuple(deepcopy(value_sources)))
        object.__setattr__(self, "secrets", tuple(deepcopy(secret_sources)))
        object.__setattr__(self, "rio", deepcopy(rio) if rio is not None else None)


__all__ = [
    "JsonValue",
    "ManifestSource",
    "PathInput",
    "ResourceInput",
    "ValueInput",
]
