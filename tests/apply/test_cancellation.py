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

"""Original cancellation propagation and settled write progress tests."""

from __future__ import annotations

import asyncio

import pytest

from rapyuta_io_sdk_v2.apply.applier import AsyncApplier
from rapyuta_io_sdk_v2.apply.source import ManifestSource
from rapyuta_io_sdk_v2.models.applier import ApplierOptions, ReadinessOptions
from rapyuta_io_sdk_v2.models.disk import Disk, DiskSpec
from rapyuta_io_sdk_v2.models.utils import BaseMetadata


@pytest.mark.asyncio
async def test_cancellation_during_readiness_keeps_confirmed_create_certain(
    configured_async_client: object,
) -> None:
    client = configured_async_client
    disk = Disk(
        metadata=BaseMetadata(name="data"),
        spec=DiskSpec(capacity=4),
    )
    readiness_started = asyncio.Event()
    writes: list[str] = []
    reads: list[str] = []

    async def create_disk(resource: Disk, **_kwargs: object) -> Disk:
        writes.append("created")
        return resource

    async def list_disks(**_kwargs: object) -> object:
        reads.append("read")
        readiness_started.set()
        await asyncio.Future()

    client.create_disk = create_disk
    client.list_disks = list_disks
    applier = AsyncApplier(
        ManifestSource(resources=(disk,)),
        ApplierOptions(readiness=ReadinessOptions(checks=2, interval=0)),
    )
    operation = asyncio.create_task(applier.apply(client))
    await asyncio.wait_for(readiness_started.wait(), timeout=1)
    operation.cancel()

    with pytest.raises(asyncio.CancelledError):
        await operation

    assert writes == ["created"]
    assert reads == ["read"]
    assert applier.last_result is not None
    outcome = applier.last_result.outcomes[0]
    assert outcome.completed_actions == ("created",)
    assert outcome.write_uncertain is False
    assert outcome.incomplete_reason == "cancelled"
