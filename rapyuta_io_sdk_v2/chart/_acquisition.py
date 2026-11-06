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

"""Acquire packaged templates before exposing a complete client-free facade."""

from __future__ import annotations

import warnings
from dataclasses import replace
from functools import partial
from typing import TYPE_CHECKING

from rapyuta_io_sdk_v2.chart import _package
from rapyuta_io_sdk_v2.chart._async import blocking_call, require_sync
from rapyuta_io_sdk_v2.chart._http import (
    async_fetch_bytes,
    async_transport,
    fetch_bytes,
    sync_transport,
)
from rapyuta_io_sdk_v2.chart.errors import ChartLoadError, ChartVersionWarning
from rapyuta_io_sdk_v2.chart.repository import AsyncChartRepository, ChartRepository

if TYPE_CHECKING:
    import httpx

    from rapyuta_io_sdk_v2.chart._package import Preparation, PreparedChart
    from rapyuta_io_sdk_v2.models.chart import ChartEntry


def _selected(entries: tuple[ChartEntry, ...], selector: str) -> ChartEntry:
    if len(entries) > 1:
        warnings.warn(
            (
                f"multiple versions for {selector}; selected {entries[0].version}; "
                "specify a version"
            ),
            ChartVersionWarning,
            stacklevel=3,
        )
    return entries[0]


def _package_url(entry: ChartEntry) -> str:
    if not entry.urls or not entry.urls[0]:
        error = ChartLoadError("download", "missing_url", entry.name)
        raise error
    return entry.urls[0]


def load_chart(request: Preparation, http_client: httpx.Client | None) -> PreparedChart:
    """Prepare local sources or scoped index/package retrieval synchronously."""
    require_sync()
    if request.source.kind != "repository":
        return _package.prepare_local(request)
    source = request.source
    with sync_transport(http_client) as client:
        entries = ChartRepository(
            source.repository, branch=source.branch, http_client=client
        ).find_chart(source.selector)
        entry = _selected(entries, source.selector)
        data = fetch_bytes(client, _package_url(entry), "download")
        return _package.prepare_archive(replace(request, entry=entry), data)


async def async_load_chart(
    request: Preparation, http_client: httpx.AsyncClient | None
) -> PreparedChart:
    """Await acquisition and join every started preparation worker on cancellation."""
    if request.source.kind != "repository":
        return await blocking_call(partial(_package.prepare_local, request))
    source = request.source
    async with async_transport(http_client) as client:
        entries = await AsyncChartRepository(
            source.repository, branch=source.branch, http_client=client
        ).find_chart(source.selector)
        entry = _selected(entries, source.selector)
        data = await async_fetch_bytes(client, _package_url(entry), "download")
        return await blocking_call(
            partial(_package.prepare_archive, replace(request, entry=entry), data)
        )
