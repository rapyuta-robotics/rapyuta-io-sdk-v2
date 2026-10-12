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

"""Project cache bootstrap and retained multi-step progress tests."""

from __future__ import annotations

import pytest

from rapyuta_io_sdk_v2.apply.applier import Applier, AsyncApplier
from rapyuta_io_sdk_v2.apply.errors import ApplierExecutionError
from rapyuta_io_sdk_v2.apply.source import ManifestSource
from rapyuta_io_sdk_v2.models.project import (
    Features,
    FeaturesDockerCache,
    Project,
    ProjectList,
    ProjectSpec,
    ProjectStatus,
)
from rapyuta_io_sdk_v2.models.utils import BaseMetadata, ListMeta


def _project() -> Project:
    return Project(
        metadata=BaseMetadata(name="analytics"),
        spec=ProjectSpec(
            features=Features(
                docker_cache=FeaturesDockerCache(
                    enabled=True,
                    proxy_device="cache-device",
                    proxy_interface="eth0",
                    registry_secret="cache-secret",
                    registry_url="registry.example.test",
                )
            )
        ),
    )


def _created_project(resource: Project) -> Project:
    return Project(
        metadata=BaseMetadata(
            name=resource.metadata.name,
            guid="analytics-guid",
            organization_guid="dummy-organization",
        ),
        spec=resource.spec,
    )


def test_cache_bootstrap_disables_cache_on_create_then_updates_full_features(
    configured_client: object,
) -> None:
    client = configured_client
    resource = _project()
    created = _created_project(resource)
    events: list[str] = []
    list_calls = 0

    def list_projects(**_kwargs: object) -> ProjectList:
        nonlocal list_calls
        list_calls += 1
        events.append("lookup")
        items = [] if list_calls == 1 else [created]
        return ProjectList(items=items, metadata=ListMeta())

    def create_project(payload: Project, **_kwargs: object) -> Project:
        events.append("create")
        assert payload.spec.features.docker_cache.enabled is False
        return created

    def update_project(payload: Project, guid: str, **_kwargs: object) -> Project:
        events.append("update")
        assert guid == "analytics-guid"
        assert payload.metadata.guid == guid
        assert payload.spec.features.docker_cache.enabled is True
        return payload

    def get_project(guid: str, **_kwargs: object) -> Project:
        events.append("readiness")
        return Project(
            metadata=BaseMetadata(
                name="analytics",
                guid=guid,
                organization_guid="dummy-organization",
            ),
            spec=resource.spec,
            status=ProjectStatus(status="Success"),
        )

    client.list_projects = list_projects
    client.create_project = create_project
    client.update_project = update_project
    client.get_project = get_project
    result = Applier(ManifestSource(resources=(resource,))).apply(client)

    assert result.outcomes[0].status == "created"
    assert result.outcomes[0].completed_actions == ("created", "updated")
    assert events == ["lookup", "create", "update", "readiness"]
    assert resource.metadata.guid is None
    assert resource.spec.features.docker_cache.enabled is True


def test_project_partial_result_keeps_confirmed_create_when_cache_update_fails(
    configured_client: object,
) -> None:
    client = configured_client
    resource = _project()
    created = _created_project(resource)
    list_calls = 0

    def list_projects(**_kwargs: object) -> ProjectList:
        nonlocal list_calls
        list_calls += 1
        return ProjectList(
            items=[] if list_calls == 1 else [created], metadata=ListMeta()
        )

    def create_project(_payload: Project, **_kwargs: object) -> Project:
        return created

    def update_project(_payload: Project, _guid: str, **_kwargs: object) -> Project:
        raise RuntimeError

    client.list_projects = list_projects
    client.create_project = create_project
    client.update_project = update_project
    applier = Applier(ManifestSource(resources=(resource,)))

    with pytest.raises(ApplierExecutionError) as caught:
        applier.apply(client)

    outcome = caught.value.result.outcomes[0]
    assert outcome.completed_actions == ("created",)
    assert outcome.write_uncertain is True
    assert applier.last_result == caught.value.result


@pytest.mark.asyncio
async def test_async_project_cache_bootstrap_uses_native_methods(
    configured_async_client: object,
) -> None:
    client = configured_async_client
    resource = _project()
    created = _created_project(resource)
    events: list[str] = []
    list_calls = 0

    async def list_projects(**_kwargs: object) -> ProjectList:
        nonlocal list_calls
        list_calls += 1
        events.append("lookup")
        return ProjectList(
            items=[] if list_calls == 1 else [created], metadata=ListMeta()
        )

    async def create_project(payload: Project, **_kwargs: object) -> Project:
        events.append("create")
        assert payload.spec.features.docker_cache.enabled is False
        return created

    async def update_project(
        payload: Project, _guid: str, **_kwargs: object
    ) -> Project:
        events.append("update")
        assert payload.spec.features.docker_cache.enabled is True
        return payload

    async def get_project(guid: str, **_kwargs: object) -> Project:
        events.append("readiness")
        return Project(
            metadata=BaseMetadata(
                name="analytics",
                guid=guid,
                organization_guid="dummy-organization",
            ),
            spec=resource.spec,
            status=ProjectStatus(status="Success"),
        )

    client.list_projects = list_projects
    client.create_project = create_project
    client.update_project = update_project
    client.get_project = get_project
    result = await AsyncApplier(ManifestSource(resources=(resource,))).apply(client)

    assert result.successful
    assert result.outcomes[0].completed_actions == ("created", "updated")
    assert events == ["lookup", "create", "update", "readiness"]
