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

"""Inspect and preview a typed resource without clients or platform access."""

from __future__ import annotations

import asyncio

from rapyuta_io_sdk_v2 import Applier, AsyncApplier, ManifestSource, Role
from rapyuta_io_sdk_v2.models.utils import BaseMetadata


def _source() -> ManifestSource:
    role = Role(metadata=BaseMetadata(name="preview-role"), spec={"rules": []})
    return ManifestSource(resources=(role,))


async def _async_preview(source: ManifestSource) -> None:
    applier = AsyncApplier(source)
    result = await applier.apply(dry_run=True)
    print(f"async apply plan: {len(result.outcomes)} resource(s)")


def main() -> None:
    """Print sync and async offline plans for one typed example resource."""
    source = _source()
    applier = Applier(source)
    inspection = applier.inspect()
    result = applier.apply(dry_run=True)
    print(f"inspected {len(inspection.resource_identities)} resource(s)")
    print(f"sync apply plan: {len(result.outcomes)} resource(s)")
    asyncio.run(_async_preview(source))


if __name__ == "__main__":
    main()
