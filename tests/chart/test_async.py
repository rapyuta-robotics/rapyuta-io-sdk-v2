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

"""Async loading progress and cancellation join the actual preparation worker."""

from __future__ import annotations

import asyncio
import tarfile
from threading import Event, get_ident
from typing import TYPE_CHECKING

import httpx
import pytest
import yaml

from rapyuta_io_sdk_v2 import ApplierOptions, ApplierUsageError, ResourceScope
from rapyuta_io_sdk_v2.apply import _loader
from rapyuta_io_sdk_v2.chart import (
    AsyncChart,
    Chart,
    ChartInputs,
    ChartSource,
    _package,
    repository,
)
from tests.chart.helpers import repository_response

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.asyncio
async def test_async_local_recreation_and_previous_result(chart_dir: Path) -> None:
    chart = await AsyncChart.load(ChartSource.from_directory(chart_dir))
    result = await chart.apply(dry_run=True, delete_existing=True)
    assert [phase.operation for phase in chart.phase_results] == ["delete", "apply"]
    assert result is chart.last_result
    assert chart.inspect().resource_identities[0].name == "viewer"


@pytest.mark.asyncio
async def test_cancelled_load_joins_running_worker_even_after_second_cancel(
    chart_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = asyncio.Event()
    released, finished = Event(), Event()
    loop = asyncio.get_running_loop()
    original = _package.prepare_local

    def delayed(request: _package.Preparation) -> _package.PreparedChart:
        loop.call_soon_threadsafe(started.set)
        released.wait()
        try:
            return original(request)
        finally:
            finished.set()

    monkeypatch.setattr(_package, "prepare_local", delayed)
    task = asyncio.create_task(AsyncChart.load(ChartSource.from_directory(chart_dir)))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert not finished.is_set()
    finally:
        released.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()


@pytest.mark.asyncio
async def test_sync_load_is_rejected_before_preparation(chart_dir: Path) -> None:
    with pytest.raises(ApplierUsageError, match="AsyncChart"):
        Chart.load(ChartSource.from_directory(chart_dir))


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["index", "package"])
async def test_native_repository_cancellation_stops_requests(stage: str) -> None:

    entered = asyncio.Event()
    urls = []

    async def response(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        is_index = request.url.path.endswith("yaml")
        if (stage == "index") == is_index:
            entered.set()
            await asyncio.Event().wait()
        entry = {
            "name": "sample",
            "version": "1.0.0",
            "urls": ["https://charts.test/package.tgz"],
        }
        return httpx.Response(
            200, text=yaml.safe_dump({"entries": {"sample": [entry]}}), request=request
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        task = asyncio.create_task(
            AsyncChart.load(ChartSource.from_repository("sample"), http_client=client)
        )
        await asyncio.wait_for(entered.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        prior = list(urls)
        await asyncio.sleep(0)
        assert urls == prior
        assert not client.is_closed


@pytest.mark.asyncio
async def test_cancellation_during_owned_transport_close_is_settled(
    chart_dir: Path, archive_bytes: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = archive_bytes(chart_dir)
    closing, released = asyncio.Event(), asyncio.Event()
    clients = []
    real_client = httpx.AsyncClient

    def response(request: httpx.Request) -> httpx.Response:
        entry = {
            "name": "sample",
            "version": "1.0.0",
            "urls": ["https://charts.test/package.tgz"],
        }
        content = (
            yaml.safe_dump({"entries": {"sample": [entry]}}).encode()
            if request.url.path.endswith("yaml")
            else data
        )
        return httpx.Response(200, content=content, request=request)

    class DelayedCloseClient(real_client):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(transport=httpx.MockTransport(response), **kwargs)
            clients.append(self)

        async def aclose(self) -> None:
            closing.set()
            await released.wait()
            await super().aclose()

    monkeypatch.setattr(httpx, "AsyncClient", DelayedCloseClient)
    task = asyncio.create_task(AsyncChart.load(ChartSource.from_repository("sample")))
    try:
        await asyncio.wait_for(closing.wait(), timeout=2)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        released.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert clients[0].is_closed


@pytest.mark.asyncio
async def test_interface_resolver_runs_on_worker_thread(chart_dir: Path) -> None:
    caller = get_ident()
    threads = []
    (chart_dir / "templates/role.yaml").write_text(
        "kind: Role\n"
        "metadata: {name: '{{ device | get_intf_ip(interface=\"eth0\") }}'}\n"
        "spec: {rules: []}\n"
    )

    def resolver(_project: str, _device: str) -> dict:
        threads.append(get_ident())
        return {"eth0": ["10.0.0.1"]}

    chart = await AsyncChart.load(
        ChartSource.from_directory(chart_dir),
        inputs=ChartInputs(values={"device": "fixture"}, interface_resolver=resolver),
        options=ApplierOptions(scope=ResourceScope(project_guid="project")),
    )
    assert threads
    assert threads[0] != caller
    assert chart.inspect().resource_identities[0].name == "10.0.0.1"


class _WorkerGate:
    def __init__(self, *, fail: bool) -> None:
        self.loop = asyncio.get_running_loop()
        self.started = asyncio.Event()
        self.release, self.finished = Event(), Event()
        self.fail = fail

    def wrap(self, callback: object) -> object:
        def work(*args: object, **kwargs: object) -> object:
            self.loop.call_soon_threadsafe(self.started.set)
            try:
                assert self.release.wait(2)
                if self.fail:
                    msg = "controlled preparation worker failure"
                    raise RuntimeError(msg)
                return callback(*args, **kwargs)
            finally:
                self.finished.set()

        return work


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["stream", "extract", "render", "index"])
@pytest.mark.parametrize("fail", [False, True])
async def test_cancellation_settles_active_preparation_and_consumes_worker_failure(
    chart_dir: Path,
    archive_bytes: object,
    *,
    boundary: str,
    fail: bool,
    preparation_gate: object,
) -> None:
    gate, staging = preparation_gate(boundary, fail=fail)
    archive = chart_dir.parent / "worker.tgz"
    archive.write_bytes(archive_bytes(chart_dir))
    before = archive.read_bytes()
    errors, loop = [], asyncio.get_running_loop()
    prior = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: errors.append(context))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(repository_response(before))
    ) as client:
        source = (
            ChartSource.from_repository("sample:1.0.0")
            if boundary == "index"
            else ChartSource.from_archive(archive)
        )
        task = asyncio.create_task(AsyncChart.load(source, http_client=client))
        try:
            await asyncio.wait_for(gate.started.wait(), 2)
            assert bool(staging) == (boundary != "index")
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
        finally:
            gate.release.set()
            await _expect_cancelled(task, loop, prior)
    assert gate.finished.is_set()
    assert errors == []
    assert archive.read_bytes() == before


@pytest.fixture
def preparation_gate(monkeypatch: pytest.MonkeyPatch, chart_staging: list) -> object:
    def install(boundary: str, *, fail: bool) -> tuple:
        gate = _WorkerGate(fail=fail)
        owner, name = {
            "stream": (_package, "_validate_archive_stream"),
            "extract": (tarfile.TarFile, "makefile"),
            "render": (_loader, "_render_manifest"),
            "index": (repository, "_index"),
        }[boundary]
        monkeypatch.setattr(owner, name, gate.wrap(getattr(owner, name)))
        return gate, chart_staging

    return install


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["index", "package"])
async def test_native_cancellation_closes_owned_transport(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    started, finished = asyncio.Event(), asyncio.Event()
    clients, requests = [], []
    original = httpx.AsyncClient

    async def response(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if (stage == "index") == request.url.path.endswith("yaml"):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                finished.set()
        return repository_response(b"unused")(request)

    class OwnedClient(original):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(transport=httpx.MockTransport(response), **kwargs)
            clients.append(self)

    monkeypatch.setattr(httpx, "AsyncClient", OwnedClient)
    task = asyncio.create_task(
        AsyncChart.load(ChartSource.from_repository("sample:1.0.0"))
    )
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()
    assert all(client.is_closed for client in clients)
    before = list(requests)
    await asyncio.sleep(0)
    assert requests == before


async def _expect_cancelled(
    task: asyncio.Task, loop: asyncio.AbstractEventLoop, prior: object
) -> None:
    try:
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        loop.set_exception_handler(prior)
