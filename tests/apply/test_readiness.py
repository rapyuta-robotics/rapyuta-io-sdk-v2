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

"""Finite, exact readiness observation and per-round budget tests."""

from types import SimpleNamespace

import pytest

from rapyuta_io_sdk_v2.apply._readiness import (
    wait_for_deployment_dependencies,
    wait_for_resource,
    wait_for_resource_async,
)
from rapyuta_io_sdk_v2.apply.errors import ReadinessError
from rapyuta_io_sdk_v2.models.applier import ReadinessOptions, ResourceContext
from rapyuta_io_sdk_v2.models.deployment import (
    Deployment,
    DeploymentMetadata,
    DeploymentSpec,
    DeploymentStatus,
)
from rapyuta_io_sdk_v2.models.disk import Disk, DiskStatus
from rapyuta_io_sdk_v2.models.network import Network, NetworkStatus
from rapyuta_io_sdk_v2.models.project import Project, ProjectStatus
from rapyuta_io_sdk_v2.models.utils import DeploymentDepends, ListMeta


def _list_page(items: list[object], continuation: int | None = None) -> object:
    return type(
        "Page", (), {"items": items, "metadata": ListMeta(continue_=continuation)}
    )()


def _context(checks: int = 3) -> ResourceContext:
    return ResourceContext(readiness=ReadinessOptions(checks=checks, interval=0))


@pytest.mark.parametrize(
    ("kind", "status", "expected"),
    [
        ("disk", None, (None, False, False)),
        ("disk", {"status": "Available"}, ("Available", True, False)),
        ("disk", {"status": "Released"}, ("Released", True, False)),
        ("disk", {"status": "Pending"}, ("Pending", False, False)),
        ("disk", {"status": "Failed"}, ("Failed", False, True)),
        ("network", None, (None, False, False)),
        (
            "network",
            {"phase": "Succeeded", "status": "Running"},
            ("Succeeded", True, False),
        ),
        (
            "network",
            {"phase": "Provisioning", "status": "Pending"},
            ("Provisioning", False, False),
        ),
        (
            "network",
            {"phase": "Stopped", "status": "Pending"},
            ("Stopped", False, True),
        ),
        (
            "network",
            {"phase": "FailedToStart", "status": "Pending"},
            ("FailedToStart", False, True),
        ),
        (
            "network",
            {"phase": "FailedToUpdate", "status": "Pending"},
            ("FailedToUpdate", False, True),
        ),
        ("network", {"phase": "", "status": "Error"}, ("Error", False, True)),
        (
            "network",
            {"phase": "Provisioning", "status": "Pending", "errorCodes": ["DEP_E153"]},
            ("Provisioning", False, True),
        ),
        ("project", None, (None, False, False)),
        ("project", {"status": "Success"}, ("Success", True, False)),
        ("project", {"status": "Error"}, ("Error", False, True)),
        ("project", {"status": "Pending"}, ("Pending", False, False)),
        ("deployment", None, (None, False, False)),
        ("deployment", {}, (None, False, False)),
        ("deployment", {"status": "Running"}, ("Running", True, False)),
        ("deployment", {"status": "Error"}, ("Error", False, True)),
        ("deployment", {"status": "Stopped"}, ("Stopped", False, True)),
        ("deployment", {"phase": "FailedToStart"}, ("FailedToStart", False, True)),
        ("deployment", {"phase": "FailedToUpdate"}, ("FailedToUpdate", False, True)),
        ("deployment", {"phase": "Stopped"}, ("Stopped", False, True)),
    ],
)
def test_resource_models_own_readiness_state_without_changing_payloads(
    resource_fixtures: dict[str, object],
    kind: str,
    status: dict[str, object] | None,
    *,
    expected: tuple[str | None, bool, bool],
) -> None:
    status_type = {
        "disk": DiskStatus,
        "network": NetworkStatus,
        "project": ProjectStatus,
        "deployment": DeploymentStatus,
    }[kind]
    resource = resource_fixtures[kind].model_copy(
        update={
            "status": status_type.model_validate(status) if status is not None else None
        }
    )
    before = resource.model_dump()

    assert resource.readiness_state() == expected
    assert resource.model_dump() == before
    assert "readiness_state" not in before


def test_disk_readiness_polls_immediately_until_ready_and_stops_on_failure(
    resource_fixtures: dict[str, object],
) -> None:
    disk = resource_fixtures["disk"]
    calls = 0

    def list_disks(**_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        status = "Pending" if calls == 1 else "Released"
        item = Disk.model_construct(
            metadata=disk.metadata,
            status=DiskStatus.model_construct(status=status),
        )
        return _list_page([item])

    fake_client = SimpleNamespace(list_disks=list_disks)
    wait_for_resource(disk, fake_client, context=_context(), kind="disk")
    expected_calls = 2
    assert calls == expected_calls

    calls = 0

    def failed_disks(**_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        item = Disk.model_construct(
            metadata=disk.metadata,
            status=DiskStatus.model_construct(status="Failed"),
        )
        return _list_page([item])

    fake_client.list_disks = failed_disks
    with pytest.raises(ReadinessError, match="terminal"):
        wait_for_resource(disk, fake_client, context=_context(), kind="disk")
    assert calls == 1


def test_paginated_pages_are_one_round_and_repeated_tokens_fail(
    resource_fixtures: dict[str, object],
) -> None:
    network = resource_fixtures["network"]
    calls = 0

    def list_networks(*, cont: int = 0, **_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if cont == 0:
            return _list_page([], continuation=5)
        item = Network.model_construct(
            metadata=network.metadata,
            status=NetworkStatus.model_construct(phase="Succeeded", status="Running"),
        )
        return _list_page([item])

    fake_client = SimpleNamespace(list_networks=list_networks)
    wait_for_resource(
        network,
        fake_client,
        context=_context(checks=1),
        kind="network",
    )
    expected_page_requests = 2
    assert calls == expected_page_requests

    calls = 0

    def repeated_token(**_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return _list_page([], continuation=5)

    fake_client.list_networks = repeated_token
    with pytest.raises(ReadinessError, match="repeated"):
        wait_for_resource(network, fake_client, context=_context(), kind="network")
    assert calls == expected_page_requests


def test_project_terminal_status_and_network_provisioning_error_are_terminal(
    resource_fixtures: dict[str, object],
) -> None:
    project = resource_fixtures["project"]

    def get_project(*_args: object, **_kwargs: object) -> Project:
        return Project.model_construct(
            metadata=project.metadata,
            spec=project.spec,
            status=ProjectStatus(status="Error"),
        )

    project.metadata.guid = "project-guid"
    fake_client = SimpleNamespace(get_project=get_project)
    with pytest.raises(ReadinessError) as project_error:
        wait_for_resource(project, fake_client, context=_context(), kind="project")
    assert project_error.value.last_state == "Error"

    network = resource_fixtures["network"]

    def list_networks(**_kwargs: object) -> object:
        item = Network.model_construct(
            metadata=network.metadata,
            status=NetworkStatus.model_construct(
                phase="Provisioning", status="Pending", error_codes=["DEP_E153"]
            ),
        )
        return _list_page([item])

    network_client = SimpleNamespace(list_networks=list_networks)
    with pytest.raises(ReadinessError, match="terminal"):
        wait_for_resource(network, network_client, context=_context(), kind="network")


def test_waited_deployment_dependencies_are_read_as_exact_targets(
    resource_fixtures: dict[str, object],
) -> None:
    resource = resource_fixtures["deployment"]
    prerequisite = Deployment.model_construct(
        metadata=DeploymentMetadata.model_construct(name="prerequisite", guid="d-1"),
        spec=DeploymentSpec.model_construct(),
        status=DeploymentStatus(status="Running"),
    )
    calls: list[dict[str, object]] = []

    def list_deployments(**kwargs: object) -> object:
        calls.append(dict(kwargs))
        return _list_page([prerequisite])

    resource.spec = DeploymentSpec.model_construct(
        depends=[DeploymentDepends(nameOrGUID="prerequisite", wait=True)]
    )
    fake_client = SimpleNamespace(list_deployments=list_deployments)
    wait_for_deployment_dependencies(resource, fake_client, context=_context())
    assert calls[0]["names"] == ["prerequisite"]
    expected_page_limit = 50
    assert calls[0]["limit"] == expected_page_limit


@pytest.mark.asyncio
async def test_async_readiness_uses_native_awaitable_reads(
    resource_fixtures: dict[str, object],
) -> None:
    disk = resource_fixtures["disk"]
    calls = 0

    async def list_disks(**_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        item = Disk.model_construct(
            metadata=disk.metadata,
            status=DiskStatus.model_construct(status="Available"),
        )
        return _list_page([item])

    fake_client = SimpleNamespace(list_disks=list_disks)
    await wait_for_resource_async(disk, fake_client, context=_context(), kind="disk")
    assert calls == 1
