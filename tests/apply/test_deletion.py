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

"""Reverse dependency order, retention, and absence deletion tests."""

import pytest

from rapyuta_io_sdk_v2.apply.applier import Applier
from rapyuta_io_sdk_v2.apply.errors import UnsupportedResourceOperationError
from rapyuta_io_sdk_v2.apply.source import ManifestSource
from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError
from rapyuta_io_sdk_v2.models.role import Role
from rapyuta_io_sdk_v2.models.rolebinding import (
    BulkRoleBindingUpdate,
    RoleBinding,
    RoleBindingList,
    RoleBindingSpec,
    RoleRef,
)
from rapyuta_io_sdk_v2.models.utils import BaseMetadata, Domain, ListMeta, Subject


def _role() -> Role:
    return Role(metadata=BaseMetadata(name="viewer"), spec={"rules": []})


def _binding() -> RoleBinding:
    return RoleBinding(
        metadata={},
        spec=RoleBindingSpec(
            roleRef=RoleRef(name="viewer"),
            domain=Domain(kind="Project", name="alpha"),
            subject=Subject(kind="User", name="ava"),
        ),
    )


def test_delete_revokes_exact_grant_before_deleting_role(
    configured_client: object,
) -> None:
    client = configured_client
    events: list[str] = []
    binding = _binding()

    def list_bindings(**_kwargs: object) -> RoleBindingList:
        events.append("lookup")
        return RoleBindingList(items=[binding], metadata=ListMeta())

    def update_binding(
        payload: BulkRoleBindingUpdate, **_kwargs: object
    ) -> BulkRoleBindingUpdate:
        events.append("revoke")
        assert payload.old_bindings == [binding]
        assert payload.new_bindings == []
        return payload

    def delete_role(*_args: object, **_kwargs: object) -> None:
        events.append("role")

    client.list_role_bindings = list_bindings
    client.update_role_binding = update_binding
    client.delete_role = delete_role
    result = Applier(ManifestSource(resources=[_role(), binding])).delete(client)
    assert result.successful
    assert events == ["lookup", "revoke", "role"]
    assert result.outcomes[1].status == "deleted"
    assert result.outcomes[1].completed_actions == ("revoked",)


def test_retained_organization_skips_unsupported_delete(
    resource_fixtures: dict[str, object], configured_client: object
) -> None:
    organization = resource_fixtures["organization"].model_copy(deep=True)
    organization.metadata.guid = "org-guid"
    organization.metadata.labels = {"rapyuta.io/deletionPolicy": "retain"}
    retained = Applier(ManifestSource(resources=[organization])).delete(
        configured_client
    )
    assert retained.outcomes[0].status == "retained"
    assert retained.outcomes[0].completed_actions == ()

    organization.metadata.labels = None
    with pytest.raises(UnsupportedResourceOperationError):
        Applier(ManifestSource(resources=[organization])).delete(configured_client)


def test_absent_delete_does_not_report_completed_mutation(
    configured_client: object,
) -> None:
    client = configured_client

    def delete_role(*_args: object, **_kwargs: object) -> None:
        raise HttpNotFoundError

    client.delete_role = delete_role
    result = Applier(ManifestSource(resources=[_role()])).delete(client)
    assert result.outcomes[0].status == "absent"
    assert result.outcomes[0].completed_actions == ()
