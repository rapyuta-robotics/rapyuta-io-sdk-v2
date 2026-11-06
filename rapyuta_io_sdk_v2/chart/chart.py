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

"""Prepared Chart facades composing existing Applier lifecycle contracts."""

from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from typing import TYPE_CHECKING

import httpx

from rapyuta_io_sdk_v2.apply.applier import Applier, AsyncApplier
from rapyuta_io_sdk_v2.apply.errors import ApplierError, ApplierUsageError
from rapyuta_io_sdk_v2.chart._acquisition import async_load_chart, load_chart
from rapyuta_io_sdk_v2.chart._async import require_sync
from rapyuta_io_sdk_v2.chart._package import Preparation, PreparedChart, add_source_note
from rapyuta_io_sdk_v2.chart.source import ChartInputs
from rapyuta_io_sdk_v2.models.applier import (
    ApplierOptions,
    ApplierResult,
    InspectionResult,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.models.chart import ChartEntry, ChartMetadata, ChartSource


class _ChartBase:
    """Prepared snapshots and a guard covering complete multi-phase calls."""

    def __init__(self, prepared: PreparedChart) -> None:
        self._prepared = prepared
        self._lock = Lock()
        self._phase_results: tuple[ApplierResult, ...] = ()

    @property
    def metadata(self) -> ChartMetadata:
        """Return an independent metadata snapshot, including mutable extras."""
        return self._prepared.metadata.model_copy(deep=True)

    @property
    def entry(self) -> ChartEntry | None:
        """Return the selected repository entry, or None for local sources."""
        entry = self._prepared.request.entry
        return entry.model_copy(deep=True) if entry is not None else None

    @property
    def source(self) -> ChartSource:
        """Identify the original caller-selected chart source."""
        return self._prepared.request.source

    @property
    def template_paths(self) -> tuple[str, ...]:
        """List ordered template names relative to the chart root."""
        return self._prepared.template_paths

    @property
    def options(self) -> ApplierOptions:
        """Expose the existing frozen execution policy."""
        return self._prepared.request.options

    @property
    def last_result(self) -> ApplierResult | None:
        """Preserve the delegate's most recent settled operation result."""
        return self._prepared.delegate.last_result

    @property
    def phase_results(self) -> tuple[ApplierResult, ...]:
        """Expose new settled phases from the most recent accepted call."""
        return self._phase_results

    def inspect(self) -> InspectionResult:
        """Return independent existing inspection data without any I/O."""
        return self._prepared.delegate.inspect()

    @contextmanager
    def _operation(self) -> Iterator[None]:
        if not self._lock.acquire(blocking=False):
            msg = "this chart already has an active operation"
            raise ApplierUsageError(msg)
        self._phase_results = ()
        try:
            yield
        finally:
            self._lock.release()

    @contextmanager
    def _phase(self) -> Iterator[None]:
        previous = self.last_result
        try:
            yield
        except ApplierError as error:
            add_source_note(error, self._prepared.root, self._prepared.request.origin)
            raise
        finally:
            current = self.last_result
            if current is not None and current is not previous:
                self._phase_results += (current,)


class Chart(_ChartBase):
    """Synchronous packaged application wrapper using caller-owned SDK clients."""

    @classmethod
    def load(
        cls,
        source: ChartSource,
        *,
        inputs: ChartInputs | None = None,
        options: ApplierOptions | None = None,
        http_client: httpx.Client | None = None,
    ) -> Chart:
        """Prepare a selected local chart; values replace defaults when supplied."""
        require_sync()
        if http_client is not None and not isinstance(http_client, httpx.Client):
            msg = "Chart acquisition requires an httpx.Client"
            raise ApplierUsageError(msg)
        request = Preparation(
            source, inputs or ChartInputs(), options or ApplierOptions(), Applier
        )
        return cls(load_chart(request, http_client))

    def apply(
        self,
        client: Client | None = None,
        *,
        dry_run: bool = False,
        delete_existing: bool = False,
    ) -> ApplierResult:
        """Delegate apply or guarded delete-then-apply, preserving phase progress."""
        require_sync()
        with self._operation():
            if delete_existing:
                with self._phase():
                    self._prepared.delegate.delete(client, dry_run=dry_run)
            with self._phase():
                return self._prepared.delegate.apply(client, dry_run=dry_run)

    def delete(
        self, client: Client | None = None, *, dry_run: bool = False
    ) -> ApplierResult:
        """Delegate reverse-order deletion or a platform-free preview."""
        require_sync()
        with self._operation(), self._phase():
            return self._prepared.delegate.delete(client, dry_run=dry_run)


class AsyncChart(_ChartBase):
    """Awaitable acquisition and lifecycle wrapper over native AsyncApplier."""

    @classmethod
    async def load(
        cls,
        source: ChartSource,
        *,
        inputs: ChartInputs | None = None,
        options: ApplierOptions | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> AsyncChart:
        """Prepare in a settled worker; supplied resolvers must be thread-safe."""
        if http_client is not None and not isinstance(http_client, httpx.AsyncClient):
            msg = "AsyncChart acquisition requires an httpx.AsyncClient"
            raise ApplierUsageError(msg)
        request = Preparation(
            source, inputs or ChartInputs(), options or ApplierOptions(), AsyncApplier
        )
        prepared = await async_load_chart(request, http_client)
        return cls(prepared)

    async def apply(
        self,
        client: AsyncClient | None = None,
        *,
        dry_run: bool = False,
        delete_existing: bool = False,
    ) -> ApplierResult:
        """Await apply or complete guarded recreation without wrapping cancellation."""
        with self._operation():
            if delete_existing:
                with self._phase():
                    await self._prepared.delegate.delete(client, dry_run=dry_run)
            with self._phase():
                return await self._prepared.delegate.apply(client, dry_run=dry_run)

    async def delete(
        self,
        client: AsyncClient | None = None,
        *,
        dry_run: bool = False,
    ) -> ApplierResult:
        """Await deletion or a client-free preview using the original delegate."""
        with self._operation(), self._phase():
            return await self._prepared.delegate.delete(client, dry_run=dry_run)
