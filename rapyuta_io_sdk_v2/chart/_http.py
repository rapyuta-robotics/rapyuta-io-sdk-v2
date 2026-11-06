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

"""Scoped HTTPX acquisition without borrowing authenticated platform clients."""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING

import httpx

from rapyuta_io_sdk_v2.apply.errors import ApplierUsageError
from rapyuta_io_sdk_v2.chart._async import tracked_await
from rapyuta_io_sdk_v2.chart.errors import ChartLoadError, ChartStage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

DEFAULT_TIMEOUT = 30.0


def validate_client(client: object, expected: type) -> None:
    """Reject mixed HTTPX execution modes without making a request."""
    if client is not None and not isinstance(client, expected):
        msg = f"Chart acquisition requires {expected.__name__} from httpx"
        raise ApplierUsageError(msg)


@contextmanager
def sync_transport(client: httpx.Client | None) -> Iterator[httpx.Client]:
    """Close only an owned client, preserving supplied configuration/lifetime."""
    validate_client(client, httpx.Client)
    if client is not None:
        yield client
    else:
        with httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as owned:
            yield owned


@asynccontextmanager
async def async_transport(
    client: httpx.AsyncClient | None,
) -> AsyncIterator[httpx.AsyncClient]:
    """Settle owned asynchronous cleanup even under repeated cancellation."""
    validate_client(client, httpx.AsyncClient)
    if client is not None:
        yield client
    else:
        owned = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True)
        try:
            yield owned
        finally:
            await tracked_await(owned.aclose())


def _valid_url(url: str) -> bool:
    try:
        parsed = httpx.URL(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.host)
    except httpx.InvalidURL:
        return False


def validate_url(url: str, stage: ChartStage) -> None:
    """Require an absolute first URL instead of resolving or trying alternatives."""
    if not _valid_url(url):
        error = ChartLoadError(stage, "invalid_url", url)
        raise error


def _sync_response(
    client: httpx.Client, url: str
) -> tuple[httpx.Response | None, str | None]:
    try:
        return client.get(url, follow_redirects=True), None
    except httpx.TimeoutException:
        return None, "timeout"
    except httpx.HTTPError:
        return None, "network"


async def _async_response(
    client: httpx.AsyncClient, url: str
) -> tuple[httpx.Response | None, str | None]:
    try:
        return await client.get(url, follow_redirects=True), None
    except httpx.TimeoutException:
        return None, "timeout"
    except httpx.HTTPError:
        return None, "network"


def _content(
    response: httpx.Response | None,
    category: str | None,
    url: str,
    *,
    stage: ChartStage,
) -> bytes:
    if response is None or not response.is_success:
        error = ChartLoadError(stage, category or "http_status", url)
        raise error
    return response.content


def fetch_bytes(client: httpx.Client, url: str, stage: ChartStage) -> bytes:
    """Fetch content with source-only errors, excluding response-body chains."""
    validate_url(url, stage)
    response, category = _sync_response(client, url)
    return _content(response, category, url, stage=stage)


async def async_fetch_bytes(
    client: httpx.AsyncClient, url: str, stage: ChartStage
) -> bytes:
    """Await native HTTP, preserving cancellation and body-free diagnostics."""
    validate_url(url, stage)
    response, category = await _async_response(client, url)
    return _content(response, category, url, stage=stage)
