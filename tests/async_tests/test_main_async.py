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


from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from rapyuta_io_sdk_v2 import AsyncClient

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2._client_options import ClientOptions


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options",
    [
        {},
        {"timeout": 15.0},
        {"timeout": None},
        {"timeout": (1.0, 2.0, 3.0, None)},
        {"timeout": httpx.Timeout(5.0, connect=1.0)},
    ],
)
async def test_client_timeout_applies_to_async_and_sync_connections(
    *, options: ClientOptions
) -> None:
    client = AsyncClient(**options)
    try:
        expected = httpx.Timeout(options.get("timeout", 10))
        assert client.c.timeout == expected
        assert client.sync_client.timeout == expected
    finally:
        await client.c.aclose()
        client.sync_client.close()
