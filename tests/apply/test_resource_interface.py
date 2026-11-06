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

"""Paired lifecycle interface and policy declarations for resource models."""

import asyncio
from types import SimpleNamespace

import pytest

from rapyuta_io_sdk_v2.apply.errors import UnsupportedResourceOperationError
from rapyuta_io_sdk_v2.models.applier import ResourceContext
from rapyuta_io_sdk_v2.models.deployment import Deployment
from rapyuta_io_sdk_v2.models.disk import Disk
from rapyuta_io_sdk_v2.models.network import Network
from rapyuta_io_sdk_v2.models.organization import Organization
from rapyuta_io_sdk_v2.models.package import Package
from rapyuta_io_sdk_v2.models.progress import MutationJournal
from rapyuta_io_sdk_v2.models.project import Project
from rapyuta_io_sdk_v2.models.resource import ResourceMethods
from rapyuta_io_sdk_v2.models.role import Role
from rapyuta_io_sdk_v2.models.rolebinding import RoleBinding
from rapyuta_io_sdk_v2.models.secret import Secret
from rapyuta_io_sdk_v2.models.serviceaccount import ServiceAccount
from rapyuta_io_sdk_v2.models.staticroute import StaticRoute
from rapyuta_io_sdk_v2.models.usergroup import UserGroup

RESOURCE_POLICIES = {
    Organization: ("update_only", False, True),
    Project: ("create_or_update", True, True),
    Package: ("create_or_exists", True, False),
    Deployment: ("create_or_exists", True, False),
    Disk: ("create_or_exists", True, False),
    Network: ("create_or_exists", True, False),
    StaticRoute: ("create_or_update", True, True),
    Secret: ("create_or_update", True, True),
    UserGroup: ("create_or_update", True, True),
    Role: ("create_or_update", True, True),
    RoleBinding: ("grant", False, False),
    ServiceAccount: ("create_or_update", True, True),
}


def test_all_managed_models_declare_the_paired_resource_interface(
    resource_fixtures: dict[str, object],
) -> None:
    for model, (policy, can_create, can_update) in RESOURCE_POLICIES.items():
        assert issubclass(model, ResourceMethods)
        resource = resource_fixtures[model.__name__.lower()]
        capabilities = resource.resource_capabilities()
        assert capabilities.apply_policy == policy
        assert capabilities.create is can_create
        assert capabilities.update is can_update
        assert resource.resource_identity().kind == model.__name__.lower()
        assert isinstance(resource.resource_dependencies(), tuple)
        assert resource.retention_policy() == "delete"
        assert callable(resource.apply)
        assert callable(resource.apply_async)
        assert callable(resource.delete_object)
        assert callable(resource.delete_object_async)


def test_unsupported_default_operations_fail_without_touching_a_client(
    resource_fixtures: dict[str, object],
) -> None:
    resource = resource_fixtures["network"]
    context = ResourceContext()
    with pytest.raises(UnsupportedResourceOperationError):
        resource.update_object(None, context=context)
    with pytest.raises(UnsupportedResourceOperationError):
        asyncio.run(resource.update_object_async(None, context=context))


def test_capabilities_and_mixin_state_do_not_become_payload_fields() -> None:
    resource_models = (
        Organization,
        Project,
        Package,
        Deployment,
        Disk,
        Network,
        StaticRoute,
        Secret,
        UserGroup,
        Role,
        RoleBinding,
        ServiceAccount,
    )
    for model in resource_models:
        assert "CAPABILITIES" not in model.model_fields
        assert "KIND" not in model.model_fields
        assert "resource_identity" not in model.model_fields


@pytest.mark.asyncio
async def test_direct_sync_async_apply_methods_share_the_supplied_journal() -> None:
    role = Role(metadata={"name": "reader"}, spec={"rules": []})
    sync_journal = MutationJournal()
    sync_client = SimpleNamespace(create_role=lambda resource, **_kwargs: resource)
    sync_outcome = role.apply(
        sync_client, context=ResourceContext(progress=sync_journal)
    )
    assert sync_outcome.completed_actions == ("created",)
    assert sync_journal.snapshot()[0].state == "completed"

    async_journal = MutationJournal()

    async def create_role(resource: Role, **_kwargs: object) -> Role:
        return resource

    async_client = SimpleNamespace(create_role=create_role)
    async_outcome = await role.apply_async(
        async_client, context=ResourceContext(progress=async_journal)
    )
    assert async_outcome.completed_actions == ("created",)
    assert async_journal.snapshot()[0].state == "completed"


@pytest.mark.asyncio
async def test_direct_async_cancellation_preserves_original_and_uncertainty() -> None:
    role = Role(metadata={"name": "reader"}, spec={"rules": []})
    journal = MutationJournal()
    cancellation = asyncio.CancelledError()

    async def create_role(_resource: Role, **_kwargs: object) -> Role:
        raise cancellation

    with pytest.raises(asyncio.CancelledError) as caught:
        await role.apply_async(
            SimpleNamespace(create_role=create_role),
            context=ResourceContext(progress=journal),
        )

    assert caught.value is cancellation
    assert journal.snapshot()[0].state == "uncertain"
