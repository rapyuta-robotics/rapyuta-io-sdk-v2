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

"""Client-free local preparation and settled asynchronous blocking work."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from rapyuta_io_sdk_v2.apply.errors import ApplierUsageError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def require_sync() -> None:
    """Reject blocking acquisition inside an active event loop before work starts."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    msg = "synchronous Chart cannot run inside an active event loop; use AsyncChart"
    raise ApplierUsageError(msg)


async def settle_task[T](task: asyncio.Future[T]) -> None:
    """Join owned work despite repeated cancellation and consume its outcome."""
    while not task.done():
        try:
            await asyncio.wait({task})
        except asyncio.CancelledError:
            continue
    if not task.cancelled():
        task.exception()


async def tracked_await[T](operation: Awaitable[T]) -> T:
    """Wait for owned work to settle before propagating caller cancellation."""
    task = asyncio.ensure_future(operation)
    try:
        # Wait without cancelling owned work or installing shield error callbacks.
        await asyncio.wait({task})
        return task.result()
    except asyncio.CancelledError:
        await settle_task(task)
        raise


async def blocking_call[T](function: Callable[[], T]) -> T:
    """Offload preparation without returning while its worker is still active."""
    return await tracked_await(asyncio.to_thread(function))
