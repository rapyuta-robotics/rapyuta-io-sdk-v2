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

"""StaticRoute logical names resolve to exact canonical routing names."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from rapyuta_io_sdk_v2.apply._resources.staticroute import (
    delete_staticroute as apply_staticroute_delete,
)
from rapyuta_io_sdk_v2.apply._resources.staticroute import (
    update_staticroute as apply_staticroute_update,
)
from rapyuta_io_sdk_v2.apply._resources.staticroute import (
    update_staticroute_async as apply_staticroute_update_async,
)
from rapyuta_io_sdk_v2.apply.errors import ApplierValidationError
from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError
from rapyuta_io_sdk_v2.models.applier import ResourceContext, ResourceScope
from rapyuta_io_sdk_v2.models.progress import MutationJournal
from rapyuta_io_sdk_v2.models.staticroute import StaticRoute, StaticRouteSpec
from rapyuta_io_sdk_v2.models.utils import BaseMetadata


def _route(name: str) -> StaticRoute:
    return StaticRoute(
        metadata=BaseMetadata(name=name),
        spec=StaticRouteSpec(url="https://example.test"),
    )


def _context() -> ResourceContext:
    return ResourceContext(
        scope=ResourceScope(
            organization_guid="org-guid",
            organization_short_guid="short",
            project_guid="project-guid",
        )
    )


def _fake_client(**methods: object) -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(
            organization_guid="org-guid", project_guid="project-guid"
        ),
        **methods,
    )


def _direct_client(*, asynchronous: bool) -> SimpleNamespace:
    mock = AsyncMock if asynchronous else Mock
    return _fake_client(
        create_staticroute=mock(return_value=_route("edge")),
        update_staticroute=mock(return_value=_route("edge")),
        get_staticroute=mock(return_value=_route("edge")),
        list_staticroutes=mock(),
        get_organization=mock(),
    )


@pytest.mark.parametrize("default_project", [None, "another-project"])
@pytest.mark.parametrize(
    "method",
    ["create_object", "update_object", "create_object_async", "update_object_async"],
)
def test_direct_staticroute_uses_metadata_before_client_defaults(
    default_project: str | None, method: str
) -> None:
    route = _route("edge")
    route.metadata.organization_guid = "metadata-org"
    route.metadata.project_guid = "metadata-project"
    before = route.model_dump(exclude_unset=True)
    context = ResourceContext()
    client = _direct_client(asynchronous=method.endswith("_async"))
    client.config.project_guid = default_project
    result = getattr(route, method)(client, context=context)
    if method.endswith("_async"):
        result = asyncio.run(result)

    assert isinstance(result, StaticRoute)
    write = (
        client.create_staticroute
        if method.startswith("create")
        else client.update_staticroute
    )
    payload = write.call_args.args[-1]
    assert payload.metadata.project_guid == "metadata-project"
    assert payload.metadata.organization_guid == "metadata-org"
    assert write.call_args.kwargs == {
        "organization_guid": "metadata-org",
        "project_guid": "metadata-project",
    }
    for call in client.get_staticroute.call_args_list:
        assert call.kwargs == write.call_args.kwargs
    assert route.model_dump(exclude_unset=True) == before
    assert context.scope == ResourceScope()
    assert client.config.project_guid == default_project


@pytest.mark.parametrize("scope_field", ["organization_guid", "project_guid"])
@pytest.mark.parametrize(
    "method",
    ["create_object", "update_object", "create_object_async", "update_object_async"],
)
def test_direct_staticroute_conflicts_fail_before_reads_or_writes(
    scope_field: str, method: str
) -> None:
    route = _route("edge")
    setattr(route.metadata, scope_field, "metadata-scope")
    journal = MutationJournal()
    context = ResourceContext(
        scope=ResourceScope(**{scope_field: "selected-scope"}), progress=journal
    )
    client = _direct_client(asynchronous=method.endswith("_async"))

    with pytest.raises(ApplierValidationError) as caught:
        (
            asyncio.run(getattr(route, method)(client, context=context))
            if method.endswith("_async")
            else getattr(route, method)(client, context=context)
        )

    assert caught.value.category == "scope_conflict"
    for mock in (
        client.create_staticroute,
        client.update_staticroute,
        client.get_staticroute,
        client.list_staticroutes,
        client.get_organization,
    ):
        mock.assert_not_called()
    assert journal.snapshot() == ()


def test_sync_staticroute_update_uses_exact_canonical_name_and_private_payload() -> (
    None
):
    requested = _route("edge")
    canonical = _route("edge-short")
    looked_up: list[str] = []
    updates: list[tuple[str, str]] = []

    def get_staticroute(name: str, **_kwargs: object) -> StaticRoute:
        looked_up.append(name)
        if name == "edge":
            raise HttpNotFoundError
        return canonical

    def update_staticroute(
        name: str, payload: StaticRoute, **_kwargs: object
    ) -> StaticRoute:
        updates.append((name, payload.metadata.name))
        return payload

    client = _fake_client(
        get_staticroute=get_staticroute,
        update_staticroute=update_staticroute,
    )

    result = apply_staticroute_update(client, requested, context=_context())

    assert looked_up == ["edge", "edge-short"]
    assert updates == [("edge-short", "edge-short")]
    assert requested.metadata.name == "edge"
    assert result.metadata.name == "edge-short"


def test_sync_staticroute_create_keeps_logical_name_and_delete_uses_canonical() -> None:
    requested = _route("edge")
    calls: list[tuple[str, str]] = []

    def create_staticroute(payload: StaticRoute, **_kwargs: object) -> StaticRoute:
        calls.append(("create", payload.metadata.name))
        return payload

    def get_staticroute(name: str, **_kwargs: object) -> StaticRoute:
        if name == "edge":
            raise HttpNotFoundError
        return _route("edge-short")

    def delete_staticroute(name: str, **_kwargs: object) -> None:
        calls.append(("delete", name))

    client = _fake_client(
        create_staticroute=create_staticroute,
        get_staticroute=get_staticroute,
        delete_staticroute=delete_staticroute,
    )

    requested.create_object(client, context=_context())
    apply_staticroute_delete(client, requested, context=_context())

    assert calls == [("create", "edge"), ("delete", "edge-short")]


@pytest.mark.asyncio
async def test_async_staticroute_update_uses_canonical_name_once_resolved() -> None:
    requested = _route("edge")
    looked_up: list[str] = []
    updates: list[tuple[str, str]] = []

    async def get_staticroute(name: str, **_kwargs: object) -> StaticRoute:
        looked_up.append(name)
        if name == "edge":
            raise HttpNotFoundError
        return _route("edge-short")

    async def update_staticroute(
        name: str, payload: StaticRoute, **_kwargs: object
    ) -> StaticRoute:
        updates.append((name, payload.metadata.name))
        return payload

    client = _fake_client(
        get_staticroute=get_staticroute,
        update_staticroute=update_staticroute,
    )

    await apply_staticroute_update_async(client, requested, context=_context())

    assert looked_up == ["edge", "edge-short"]
    assert updates == [("edge-short", "edge-short")]
