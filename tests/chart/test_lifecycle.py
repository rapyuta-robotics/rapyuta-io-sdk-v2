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

"""Delegated lifecycle outcomes, two-phase guarding, and previous-call isolation."""

import asyncio
from pathlib import Path
from threading import Event, Lock

import pytest
import yaml

from rapyuta_io_sdk_v2 import (
    ApplierExecutionError,
    ApplierOptions,
    ApplierUsageError,
    AsyncClient,
    Client,
    Configuration,
    MissingResourceContextError,
    ReadinessOptions,
)
from rapyuta_io_sdk_v2.apply.applier import Applier, AsyncApplier
from rapyuta_io_sdk_v2.apply.source import ManifestSource
from rapyuta_io_sdk_v2.chart import AsyncChart, Chart, ChartSource
from rapyuta_io_sdk_v2.models.role import Role
from tests.chart.helpers import (
    PlatformRecorder,
    chart_call,
    platform_client,
    result_data,
    role_binding_documents,
)


def test_recreation_preview_keeps_both_original_phase_results(chart_dir: Path) -> None:
    chart = Chart.load(ChartSource.from_directory(chart_dir))
    result = chart.apply(dry_run=True, delete_existing=True)
    assert [phase.operation for phase in chart.phase_results] == ["delete", "apply"]
    assert chart.phase_results[-1] is result is chart.last_result
    assert all(phase.dry_run for phase in chart.phase_results)


def test_preflight_does_not_reuse_an_old_phase_result(chart_dir: Path) -> None:
    chart = Chart.load(ChartSource.from_directory(chart_dir))
    prior = chart.apply(dry_run=True)
    with pytest.raises(MissingResourceContextError):
        chart.apply(delete_existing=True)
    assert chart.phase_results == ()
    assert chart.last_result is prior
    assert chart.delete(dry_run=True).successful


def test_exact_client_remains_open_and_failed_delete_never_applies(
    chart_dir: Path,
) -> None:
    chart = Chart.load(ChartSource.from_directory(chart_dir))
    client = Client(Configuration(auth_token="chart-test", organization_guid="org"))
    calls = []
    client.create_role = lambda resource, **_kwargs: calls.append("apply") or resource

    def failed_delete(*_args: object, **_kwargs: object) -> None:
        calls.append("delete")
        msg = "controlled deletion failure"
        raise RuntimeError(msg)

    client.delete_role = failed_delete
    try:
        assert chart.apply(client).successful
        calls.clear()
        with pytest.raises(ApplierExecutionError) as error:
            chart.apply(client, delete_existing=True)
        assert calls == ["delete"]
        assert chart.phase_results == (error.value.result,)
        assert not client.c.is_closed
    finally:
        client.c.close()


def test_wrong_client_mode_preserves_original_usage_error(chart_dir: Path) -> None:
    chart = Chart.load(ChartSource.from_directory(chart_dir))
    with pytest.raises(ApplierUsageError):
        chart.apply(object())
    assert chart.phase_results == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_phase", ["delete", "apply"])
async def test_async_recreation_cancellation_and_operation_guard(
    chart_dir: Path, cancel_phase: str
) -> None:
    chart = await AsyncChart.load(ChartSource.from_directory(chart_dir))
    client = AsyncClient(
        Configuration(auth_token="chart-test", organization_guid="org")
    )
    calls, started = _cancel_lifecycle(client, cancel_phase)
    task = asyncio.create_task(chart.apply(client, delete_existing=True))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        phases_before = chart.phase_results
        with pytest.raises(ApplierUsageError, match="active operation"):
            await chart.apply(dry_run=True)
        assert chart.phase_results == phases_before
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert [p.operation for p in chart.phase_results] == calls
        assert not client.c.is_closed
        assert (await chart.apply(dry_run=True)).successful
    finally:
        task.cancel()
        await client.c.aclose()


def _cancel_lifecycle(
    client: AsyncClient, cancel_phase: str
) -> tuple[list[str], asyncio.Event]:
    started = asyncio.Event()
    calls = []

    async def create(resource: object, **_kwargs: object) -> object:
        calls.append("apply")
        started.set()
        await asyncio.Event().wait()
        return resource

    async def delete(*_args: object, **_kwargs: object) -> None:
        calls.append("delete")
        if cancel_phase == "delete":
            started.set()
            await asyncio.Event().wait()

    client.create_role = create
    client.delete_role = delete
    return calls, started


def test_sequential_clients_rebind_scope_without_mutating_client_or_source(
    chart_dir: Path,
) -> None:
    chart = Chart.load(ChartSource.from_directory(chart_dir))
    calls = []
    for guid in ["org-first", "org-second"]:
        configuration = Configuration(auth_token="chart-test", organization_guid=guid)
        client = Client(configuration)
        client.create_role = lambda resource, **kwargs: (
            calls.append(kwargs["organization_guid"]) or resource
        )
        try:
            chart.apply(client)
            assert configuration.organization_guid == guid
            assert not client.c.is_closed
        finally:
            client.c.close()
    assert calls == ["org-first", "org-second"]
    assert chart.inspect().resolved_manifests[0].metadata.organization_guid is None


async def _paired_lifecycle(root: Path, loader: object) -> tuple:
    documents = role_binding_documents()
    (root / "templates/role.yaml").write_text(yaml.safe_dump_all(documents))
    chart = await loader(
        ChartSource.from_directory(root), options=ApplierOptions(workers=1)
    )
    facade = Applier if loader.chart_type is Chart else AsyncApplier
    direct = facade(
        ManifestSource(
            files=[root / "templates/role.yaml"], values=[root / "values.yaml"]
        ),
        chart.options,
    )
    return chart, direct


@pytest.mark.asyncio
async def test_dependency_actions_equal_direct_apply(
    chart_dir: Path,
    chart_loader: object,
) -> None:
    chart, direct = await _paired_lifecycle(chart_dir, chart_loader)
    outputs, events = [], []
    for facade in [chart, direct]:
        recorder = PlatformRecorder(chart.inspect().resolved_manifests[1])
        async with platform_client(chart_loader, recorder) as client:
            applied = await chart_call(facade, "apply", client=client)
            deleted = await chart_call(facade, "delete", client=client)
            outputs.append([result_data(applied), result_data(deleted)])
            events.append(recorder.events)
    assert outputs[0] == outputs[1]
    assert (
        events[0]
        == events[1]
        == [
            ("create", "viewer", "org"),
            ("grant",),
            ("revoke",),
            ("delete", "viewer", "org"),
        ]
    )
    assert chart.phase_results[-1] is chart.last_result
    assert chart.inspect().dependency_graph.edges


@pytest.mark.asyncio
async def test_partial_failure_matches_direct_and_preserves_result_identity(
    chart_dir: Path,
    chart_loader: object,
) -> None:
    chart, direct = await _paired_lifecycle(chart_dir, chart_loader)
    outputs = []
    for facade in [chart, direct]:
        recorder = PlatformRecorder(chart.inspect().resolved_manifests[1])
        recorder.fail = "grant"
        async with platform_client(chart_loader, recorder) as client:
            with pytest.raises(ApplierExecutionError) as error:
                await chart_call(facade, "apply", client=client)
            assert error.value.result is facade.last_result
            outcomes = error.value.result.outcomes
            assert outcomes[0].completed_actions == ("created",)
            assert not outcomes[0].write_uncertain
            assert outcomes[1].write_uncertain
            outputs.append(result_data(error.value.result))
    assert outputs[0] == outputs[1]
    assert chart.phase_results == (chart.last_result,)
    assert (await chart_call(chart, "apply", dry_run=True)).successful


@pytest.mark.asyncio
async def test_recreation_apply_failure_keeps_successful_delete(
    chart_dir: Path,
    chart_loader: object,
) -> None:
    chart, _direct = await _paired_lifecycle(chart_dir, chart_loader)
    recorder = PlatformRecorder(chart.inspect().resolved_manifests[1])
    recorder.present, recorder.fail = True, "create"
    async with platform_client(chart_loader, recorder) as client:
        with pytest.raises(ApplierExecutionError) as error:
            await chart_call(chart, "apply", client=client, delete_existing=True)
    assert [phase.operation for phase in chart.phase_results] == ["delete", "apply"]
    assert chart.phase_results[0].successful
    assert chart.phase_results[-1] is error.value.result is chart.last_result
    assert recorder.events == [
        ("revoke",),
        ("delete", "viewer", "org"),
        ("create", "viewer", "org"),
    ]


@pytest.mark.asyncio
async def test_retention_absence_and_sequential_scope_rebinding(
    chart_dir: Path,
    chart_loader: object,
) -> None:
    documents = role_binding_documents()[:1]
    documents.append(
        {
            "kind": "Role",
            "metadata": {
                "name": "kept",
                "labels": {"rapyuta.io/deletionPolicy": "retain"},
            },
            "spec": {"rules": []},
        }
    )
    (chart_dir / "templates/role.yaml").write_text(yaml.safe_dump_all(documents))
    chart = await chart_loader(ChartSource.from_directory(chart_dir))
    recorder = PlatformRecorder(None)
    recorder.absent = True
    for org in ["first", "second"]:
        async with platform_client(chart_loader, recorder, org=org) as client:
            await chart_call(chart, "apply", client=client)
            result = await chart_call(chart, "delete", client=client)
            assert [outcome.status for outcome in result.outcomes] == [
                "absent",
                "retained",
            ]
            assert all(outcome.completed_actions == () for outcome in result.outcomes)
    assert [event[-1] for event in recorder.events if event[0] == "delete"] == [
        "first",
        "second",
    ]
    assert chart.inspect().resolved_manifests[0].metadata.organization_guid is None


@pytest.mark.asyncio
async def test_both_modes_reject_clients_without_stale_progress(
    chart_dir: Path,
    chart_loader: object,
) -> None:
    chart = await chart_loader(ChartSource.from_directory(chart_dir))
    prior = await chart_call(chart, "apply", dry_run=True)
    with pytest.raises(ApplierUsageError):
        await chart_call(chart, "apply", client=object())
    with pytest.raises(MissingResourceContextError):
        await chart_call(chart, "apply", delete_existing=True)
    assert chart.phase_results == ()
    assert chart.last_result is prior
    assert (await chart_call(chart, "delete", dry_run=True)).successful


@pytest.mark.asyncio
async def test_sync_overlap_is_rejected_without_resetting_accepted_call(
    chart_dir: Path,
) -> None:
    started, released = Event(), Event()
    chart = await asyncio.to_thread(Chart.load, ChartSource.from_directory(chart_dir))
    client = Client(Configuration(auth_token="chart-test", organization_guid="org"))

    def blocked(resource: object, **_kwargs: object) -> object:
        started.set()
        released.wait(timeout=2)
        return resource

    client.create_role = blocked
    task = asyncio.create_task(asyncio.to_thread(chart.apply, client))
    try:
        assert await asyncio.to_thread(started.wait, 2)
        with pytest.raises(ApplierUsageError, match="active operation"):
            await asyncio.to_thread(chart.delete, dry_run=True)
        assert chart.phase_results == ()
    finally:
        released.set()
        await task
        client.c.close()
    assert chart.phase_results == (chart.last_result,)
    assert (await asyncio.to_thread(chart.delete, dry_run=True)).successful


class _CreateProbe:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.started, self.release = Event(), Event()
        self.active, self.maximum = 0, 0
        self.checks = []
        self.lock = Lock()

    def _enter(self, context: object) -> None:
        with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            self.checks.append(context.readiness.checks)
            if self.active == self.limit:
                self.started.set()

    def sync(self, resource: object, _client: object, *, context: object) -> object:
        self._enter(context)
        try:
            assert self.release.wait(2)
            return resource
        finally:
            with self.lock:
                self.active -= 1

    async def native(
        self, resource: object, _client: object, *, context: object
    ) -> object:
        self._enter(context)
        try:
            assert await asyncio.to_thread(self.release.wait, 2)
            return resource
        finally:
            with self.lock:
                self.active -= 1


@pytest.mark.asyncio
async def test_worker_limit_and_readiness_are_executed(
    chart_dir: Path,
    chart_loader: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = [
        dict(role_binding_documents()[0], metadata={"name": name})
        for name in ["one", "two", "three"]
    ]
    (chart_dir / "templates/role.yaml").write_text(yaml.safe_dump_all(documents))
    options = ApplierOptions(
        workers=2, readiness=ReadinessOptions(checks=7, interval=0)
    )
    chart = await chart_loader(ChartSource.from_directory(chart_dir), options=options)
    probe = _CreateProbe(1 if chart_loader.chart_type is Chart else options.workers)

    def create(resource: object, client: object, **kwargs: object) -> object:
        return probe.sync(resource, client, **kwargs)

    async def create_async(
        resource: object, client: object, **kwargs: object
    ) -> object:
        return await probe.native(resource, client, **kwargs)

    monkeypatch.setattr(Role, "create_object", create)
    monkeypatch.setattr(Role, "create_object_async", create_async)
    async with platform_client(chart_loader, PlatformRecorder(None)) as client:
        task = asyncio.create_task(chart_call(chart, "apply", client=client))
        try:
            assert await asyncio.to_thread(probe.started.wait, 2)
            await asyncio.sleep(0)
            assert len(probe.checks) == probe.limit
        finally:
            probe.release.set()
            result = await task
    assert result.successful
    assert probe.maximum == probe.limit
    assert probe.checks == [options.readiness.checks] * len(documents)
