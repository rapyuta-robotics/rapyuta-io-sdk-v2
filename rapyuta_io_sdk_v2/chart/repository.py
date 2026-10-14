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

"""Typed catalog lookup with the rio CLI's source and ordering semantics."""

from __future__ import annotations

from functools import partial
from urllib.parse import quote

import httpx
import yaml
from pydantic import ValidationError

from rapyuta_io_sdk_v2.chart._async import blocking_call, require_sync
from rapyuta_io_sdk_v2.chart._http import (
    async_fetch_bytes,
    async_transport,
    fetch_bytes,
    sync_transport,
    validate_client,
)
from rapyuta_io_sdk_v2.chart._yaml import load_documents
from rapyuta_io_sdk_v2.chart.errors import ChartLoadError
from rapyuta_io_sdk_v2.models.chart import ChartEntry, ChartIndex, split_selector

DEFAULT_REPOSITORY = (
    "https://rapyuta-robotics.github.io/rapyuta-charts/incubator/index.yaml"
)
BRANCH_REPO_BASE = "https://chartsbranch.blob.core.windows.net/charts-per-branch"


def branch_repository_url(branch: str) -> str:
    """Construct the exact CLI branch URL, preserving slash and quoting symbols."""
    return f"{BRANCH_REPO_BASE}/{quote(branch, safe='/')}/incubator/index.yaml"


def _parse_index(data: bytes) -> ChartIndex | None:
    try:
        documents = load_documents(data)
        if len(documents) != 1:
            return None
        return ChartIndex.model_validate(documents[0])
    except (yaml.YAMLError, ValidationError, UnicodeError):
        return None


def _index(data: bytes, source: str) -> ChartIndex:
    parsed = _parse_index(data)
    if parsed is None:
        error = ChartLoadError("index", "invalid_index", source)
        raise error
    return parsed


def _validate_selector(selector: str, source: str) -> None:
    try:
        split_selector(selector)
    except ValueError:
        error = ChartLoadError("index", "invalid_selector", source, selector=selector)
        raise error from None


def _find(index: ChartIndex, selector: str, source: str) -> tuple[ChartEntry, ...]:
    name, version = split_selector(selector)
    entries = index.entries.get(name, ())
    if version is not None:
        entries = tuple(entry for entry in entries if entry.version == version)[:1]
    if not entries:
        error = ChartLoadError("index", "chart_not_found", source, selector=selector)
        raise error
    return entries


def _listing(index: ChartIndex) -> tuple[ChartEntry, ...]:
    return tuple(
        sorted(
            (entry for versions in index.entries.values() for entry in versions),
            key=lambda entry: entry.name.lower(),
        )
    )


class _RepositoryBase:
    def __init__(self, repository: str | None, branch: str | None) -> None:
        self._index_url = (
            branch_repository_url(branch)
            if branch
            else repository or DEFAULT_REPOSITORY
        )

    @property
    def index_url(self) -> str:
        """Expose the selected index without any network request."""
        return self._index_url


class ChartRepository(_RepositoryBase):
    """Synchronous repository helper; no persistent cache or owned transport."""

    def __init__(
        self,
        repository: str | None = None,
        *,
        branch: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        """Select an index and optional caller-owned HTTPX client without I/O."""
        super().__init__(repository, branch)
        validate_client(http_client, httpx.Client)
        self._client = http_client

    def fetch_index(self) -> ChartIndex:
        """Read a fresh typed index; close only a transport created for this call."""
        require_sync()
        with sync_transport(self._client) as client:
            return _index(fetch_bytes(client, self.index_url, "index"), self.index_url)

    def find_chart(self, selector: str) -> tuple[ChartEntry, ...]:
        """Return index-order versions or only the first exact-version match."""
        _validate_selector(selector, self.index_url)
        return _find(self.fetch_index(), selector, self.index_url)

    def list_charts(self) -> tuple[ChartEntry, ...]:
        """List fresh entries sorted stably by case-insensitive chart name."""
        return _listing(self.fetch_index())


class AsyncChartRepository(_RepositoryBase):
    """Native asynchronous metadata lookup with settled parsing and cleanup."""

    def __init__(
        self,
        repository: str | None = None,
        *,
        branch: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Select an index and optional async acquisition client without I/O."""
        super().__init__(repository, branch)
        validate_client(http_client, httpx.AsyncClient)
        self._client = http_client

    async def fetch_index(self) -> ChartIndex:
        """Await HTTP and parse in a tracked worker, returning independent data."""
        async with async_transport(self._client) as client:
            data = await async_fetch_bytes(client, self.index_url, "index")
            return await blocking_call(partial(_index, data, self.index_url))

    async def find_chart(self, selector: str) -> tuple[ChartEntry, ...]:
        """Await index-order versions or only the first exact-version match."""
        _validate_selector(selector, self.index_url)
        return _find(await self.fetch_index(), selector, self.index_url)

    async def list_charts(self) -> tuple[ChartEntry, ...]:
        """Await fresh entries in the CLI's stable case-insensitive name order."""
        return _listing(await self.fetch_index())
