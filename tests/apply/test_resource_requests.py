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

"""Typed credential and membership request preservation tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from rapyuta_io_sdk_v2.apply._resources.standard import (
    record_write,
    record_write_async,
)
from rapyuta_io_sdk_v2.apply.errors import ApplierValidationError
from rapyuta_io_sdk_v2.exceptions import MethodNotAllowedError
from rapyuta_io_sdk_v2.models.applier import ResourceContext, ResourceScope
from rapyuta_io_sdk_v2.models.progress import MutationJournal
from rapyuta_io_sdk_v2.models.role import Role
from rapyuta_io_sdk_v2.models.secret import (
    DockerSpecCreate,
    Secret,
    SecretCreate,
    SecretSpec,
    SecretSpecCreate,
)
from rapyuta_io_sdk_v2.models.usergroup import (
    UserGroup,
    UserGroupMember,
    UserGroupSpec,
)
from rapyuta_io_sdk_v2.models.utils import BaseMetadata, Subject


def _context() -> ResourceContext:
    return ResourceContext(
        scope=ResourceScope(organization_guid="org-guid", project_guid="project-guid")
    )


def _docker_secret() -> SecretCreate:
    return SecretCreate(
        metadata=BaseMetadata(name="registry"),
        spec=SecretSpecCreate(
            type="Docker",
            docker=DockerSpecCreate(
                username="builder",
                email="builder@example.test",
                password="credential-value",
            ),
        ),
    )


def test_secret_create_and_update_requests_keep_docker_credentials() -> None:
    secret = _docker_secret()
    captured: list[SecretCreate] = []
    response = Secret(
        metadata=secret.metadata,
        spec=SecretSpec(
            type="Docker",
            docker={"username": "builder", "email": "builder@example.test"},
        ),
    )

    def create_secret(payload: SecretCreate, **_kwargs: object) -> Secret:
        captured.append(payload)
        return response

    def update_secret(name: str, payload: SecretCreate, **_kwargs: object) -> Secret:
        assert name == "registry"
        captured.append(payload)
        return response

    client = SimpleNamespace(
        create_secret=create_secret,
        update_secret=update_secret,
    )

    secret.create_object(client, context=_context())
    secret.update_object(client, context=_context())

    assert [item.spec.docker.password for item in captured] == [
        "credential-value",
        "credential-value",
    ]
    assert secret.metadata.organization_guid is None
    assert secret.metadata.project_guid is None


def test_usergroup_update_preserves_explicit_membership_and_roles() -> None:
    group = UserGroup(
        metadata=BaseMetadata(name="operators", guid="group-guid"),
        spec=UserGroupSpec(
            members=[
                UserGroupMember(
                    subject=Subject(kind="User", name="ava"),
                    role_names=["operator"],
                    implicit_role_names=["reader"],
                )
            ]
        ),
    )
    captured: list[UserGroup] = []

    def update(payload: UserGroup, **_kwargs: object) -> UserGroup:
        captured.append(payload)
        return payload

    group.update_object(SimpleNamespace(update_user_group=update), context=_context())

    assert captured[0].metadata.guid == "group-guid"
    assert captured[0].spec.members == group.spec.members
    assert group.metadata.organization_guid is None


def test_direct_apply_rejects_conflicting_scope_before_writing() -> None:
    role = Role(
        metadata=BaseMetadata(name="viewer", organization_guid="org-a"),
        spec={"rules": []},
    )
    writes: list[str] = []

    def create(payload: Role, **_kwargs: object) -> Role:
        writes.append("create")
        return payload

    with pytest.raises(ApplierValidationError) as caught:
        role.apply(
            SimpleNamespace(create_role=create),
            context=ResourceContext(scope=ResourceScope(organization_guid="org-b")),
        )

    assert caught.value.category == "scope_conflict"
    assert writes == []


def test_direct_apply_uses_one_scope_for_request_and_outcome() -> None:
    role = Role(metadata=BaseMetadata(name="viewer"), spec={"rules": []})
    calls: list[tuple[str | None, str | None]] = []

    def create(payload: Role, **kwargs: object) -> Role:
        calls.append(
            (payload.metadata.organization_guid, kwargs.get("organization_guid"))
        )
        return payload

    outcome = role.apply(
        SimpleNamespace(create_role=create),
        context=ResourceContext(scope=ResourceScope(organization_guid="org-b")),
    )

    assert calls == [("org-b", "org-b")]
    assert outcome.identity.scope.organization_guid == "org-b"


def test_direct_lifecycle_uses_metadata_scope_when_context_scope_is_omitted() -> None:
    role = Role(
        metadata=BaseMetadata(name="viewer", organization_guid="org-a"),
        spec={"rules": []},
    )
    calls: list[tuple[str | None, str | None]] = []

    def create(payload: Role, **kwargs: object) -> Role:
        calls.append(
            (payload.metadata.organization_guid, kwargs.get("organization_guid"))
        )
        return payload

    outcome = role.apply(SimpleNamespace(create_role=create), context=ResourceContext())

    assert calls == [("org-a", "org-a")]
    assert outcome.identity.scope.organization_guid == "org-a"


def test_direct_delete_rejects_conflicting_scope_before_writing() -> None:
    role = Role(
        metadata=BaseMetadata(name="viewer", organization_guid="org-a"),
        spec={"rules": []},
    )
    writes: list[str] = []

    def delete(*_args: object, **_kwargs: object) -> None:
        writes.append("delete")

    with pytest.raises(ApplierValidationError) as caught:
        role.delete_object(
            SimpleNamespace(delete_role=delete),
            context=ResourceContext(scope=ResourceScope(organization_guid="org-b")),
        )

    assert caught.value.category == "scope_conflict"
    assert writes == []


def test_sync_write_rejection_is_not_reported_as_uncertain() -> None:
    journal = MutationJournal()
    context = ResourceContext(progress=journal)

    def reject() -> None:
        message = "rejected"
        raise MethodNotAllowedError(message)

    with pytest.raises(MethodNotAllowedError):
        record_write(context, "created", reject)

    assert journal.snapshot()[0].state == "rejected"


@pytest.mark.asyncio
async def test_async_write_rejection_is_not_reported_as_uncertain() -> None:
    journal = MutationJournal()
    context = ResourceContext(progress=journal)

    async def reject() -> None:
        message = "rejected"
        raise MethodNotAllowedError(message)

    with pytest.raises(MethodNotAllowedError):
        await record_write_async(context, "created", reject)

    assert journal.snapshot()[0].state == "rejected"


_DIRECT_WRITES = [
    ("package", "create"),
    ("deployment", "create"),
    ("disk", "create"),
    ("network", "create"),
    ("secret", "create"),
    ("secret", "update"),
    ("usergroup", "create"),
    ("usergroup", "update"),
    ("role", "create"),
    ("role", "update"),
    ("serviceaccount", "create"),
    ("serviceaccount", "update"),
]


def _direct_write_resource(resource_fixtures: dict[str, object], kind: str) -> object:
    resource = (
        _docker_secret()
        if kind == "secret"
        else resource_fixtures[kind].model_copy(deep=True)
    )
    resource.metadata.organization_guid = "org-a"
    if kind in {"package", "deployment", "disk", "network", "secret"}:
        resource.metadata.project_guid = "project-a"
    if kind == "usergroup":
        resource.metadata.guid = "group-guid"
        resource.spec.members = []
    return resource


async def _invoke_direct_write(
    resource: object,
    client: object,
    *,
    context: ResourceContext,
    case: tuple[str, str],
    asynchronous: bool,
) -> None:
    hook = getattr(resource, f"{case[1]}_object{'_async' if asynchronous else ''}")
    if asynchronous:
        await hook(client, context=context)
    else:
        hook(client, context=context)


@pytest.mark.parametrize("case", _DIRECT_WRITES)
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("conflict", [False, True])
@pytest.mark.asyncio
async def test_direct_write_reconciles_metadata_scope(
    resource_fixtures: dict[str, object],
    case: tuple[str, str],
    *,
    asynchronous: bool,
    conflict: bool,
) -> None:
    resource = _direct_write_resource(resource_fixtures, case[0])
    before = resource.model_dump(exclude_unset=True)
    journal = MutationJournal()
    context = ResourceContext(
        scope=ResourceScope(organization_guid="org-b") if conflict else ResourceScope(),
        progress=journal,
    )
    endpoint = {"usergroup": "user_group", "serviceaccount": "service_account"}.get(
        case[0], case[0]
    )
    write = (
        AsyncMock(return_value=resource)
        if asynchronous
        else Mock(return_value=resource)
    )
    client = SimpleNamespace(**{f"{case[1]}_{endpoint}": write})
    if conflict:
        with pytest.raises(ApplierValidationError, match="scope conflicts"):
            await _invoke_direct_write(
                resource, client, context=context, case=case, asynchronous=asynchronous
            )
        write.assert_not_called()
        assert journal.snapshot() == ()
    else:
        await _invoke_direct_write(
            resource, client, context=context, case=case, asynchronous=asynchronous
        )
        assert write.call_args.kwargs["organization_guid"] == "org-a"
        assert (
            write.call_args.kwargs.get("project_guid") == resource.metadata.project_guid
        )
        assert journal.snapshot()[0].state == "completed"
    assert resource.model_dump(exclude_unset=True) == before
    assert context.scope.project_guid is None
    assert context.progress is journal
