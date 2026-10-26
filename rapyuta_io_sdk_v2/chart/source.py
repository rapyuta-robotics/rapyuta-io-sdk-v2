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

"""Snapshotted rendering configuration for packaged templates."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from rapyuta_io_sdk_v2.apply.source import (
    DeviceInterfaceResolver,
    JsonValue,
    ManifestSource,
    ValueInput,
)

type ValueSources = ValueInput | Iterable[ValueInput] | None


@dataclass(frozen=True, slots=True, init=False)
class ChartInputs:
    """Ordered render inputs normalized with the existing ManifestSource contract."""

    values: tuple[ValueInput, ...]
    secrets: tuple[ValueInput, ...]
    rio: Mapping[str, JsonValue] | None
    interface_resolver: DeviceInterfaceResolver | None

    def __init__(
        self,
        *,
        values: ValueSources = (),
        secrets: ValueSources = (),
        rio: Mapping[str, JsonValue] | None = None,
        interface_resolver: DeviceInterfaceResolver | None = None,
    ) -> None:
        """Snapshot mappings/iterables without merging or implicitly decrypting."""
        snapshot = ManifestSource(
            values=values,
            secrets=secrets,
            rio=rio,
            interface_resolver=interface_resolver,
        )
        object.__setattr__(self, "values", snapshot.values)
        object.__setattr__(self, "secrets", snapshot.secrets)
        object.__setattr__(self, "rio", snapshot.rio)
        object.__setattr__(self, "interface_resolver", snapshot.interface_resolver)
