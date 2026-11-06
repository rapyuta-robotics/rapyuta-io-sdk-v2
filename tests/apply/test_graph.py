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

"""Contract tests for offline identity and dependency graph preparation."""

from __future__ import annotations

import pytest

from rapyuta_io_sdk_v2.apply._graph import (
    build_dependency_graph,
    prepare_dependency_graph,
)
from rapyuta_io_sdk_v2.apply.errors import ApplierValidationError
from rapyuta_io_sdk_v2.models.applier import (
    DependencyReference,
    ResourceIdentity,
    ResourceReference,
    ResourceScope,
)

EXPECTED_RESOLVED_DEPENDENCIES = 4


def _identity(  # noqa: PLR0913
    kind: str,
    name: str,
    *,
    guid: str | None = None,
    version: str | None = None,
    organization: str | None = None,
    project: str | None = None,
    organization_short: str | None = None,
) -> ResourceIdentity:
    return ResourceIdentity(
        kind=kind,
        name=name,
        guid=guid,
        version=version,
        scope=ResourceScope(
            organization_guid=organization,
            project_guid=project,
            organization_short_guid=organization_short,
        ),
    )


def _dependency(
    kind: str,
    *,
    name: str | None = None,
    guid: str | None = None,
    version: str | None = None,
    wait: bool = False,
) -> DependencyReference:
    return DependencyReference(
        reference=ResourceReference(kind=kind, name=name, guid=guid, version=version),
        wait=wait,
    )


def test_package_versions_and_delimiter_names_remain_structural() -> None:
    first = _identity("package", "robot@stable", version="1:2")
    second = _identity("package", "robot", version="stable@1:2")
    deployment = _identity("deployment", "worker")

    graph = build_dependency_graph(
        [
            (first, ()),
            (second, ()),
            (
                deployment,
                (
                    _dependency("package", name="robot@stable", version="1:2"),
                    _dependency("package", name="robot", version="stable@1:2"),
                ),
            ),
        ]
    )

    assert graph.managed == (first, second, deployment)
    assert graph.edges == ((first, deployment), (second, deployment))
    assert graph.external_references == ()


def test_kind_and_scope_aliases_are_normalized_without_cross_scope_matches() -> None:
    same_name_elsewhere = _identity(
        "serviceaccount", "runner", guid="wrong-org", organization="org-b"
    )
    local = _identity(
        "serviceaccount", "runner", guid="local-guid", organization="org-a"
    )
    deployment = _identity(
        "DEPLOYMENT",
        "worker",
        organization="org-a",
        project="project-a",
        organization_short="route-only",
    )

    graph = build_dependency_graph(
        [
            (same_name_elsewhere, ()),
            (local, ()),
            (
                deployment,
                (_dependency("SERVICEACCOUNT", name="runner"),),
            ),
        ]
    )

    assert deployment.kind == "deployment"
    assert graph.edges == ((graph.managed[1], graph.managed[2]),)
    assert graph.managed[0].scope.project_guid is None
    assert graph.managed[1].scope.project_guid is None
    assert graph.managed[2].scope.organization_short_guid is None


def test_known_guid_alias_resolves_to_managed_node() -> None:
    package = _identity("package", "base", guid="pkg-guid", version="7")
    deployment = _identity("deployment", "worker")

    graph = build_dependency_graph(
        [
            (package, ()),
            (deployment, (_dependency("package", guid="pkg-guid", version="7"),)),
        ]
    )

    assert graph.edges == ((package, deployment),)
    assert graph.external_references == ()


@pytest.mark.parametrize("selector", ["base", "base-guid"])
def test_name_or_guid_dependencies_match_either_managed_selector(
    selector: str,
) -> None:
    prerequisite = _identity("deployment", "base", guid="base-guid")
    dependent = _identity("deployment", "worker")

    graph = build_dependency_graph(
        [
            (prerequisite, ()),
            (
                dependent,
                (_dependency("deployment", name=selector, guid=selector),),
            ),
        ]
    )

    assert graph.edges == ((prerequisite, dependent),)
    assert graph.external_references == ()


def test_duplicate_dependencies_are_deduplicated_but_wait_metadata_is_retained() -> (
    None
):
    package = _identity("package", "base", version="2")
    deployment = _identity("deployment", "worker")
    managed = _dependency("package", name="base", version="2", wait=True)
    external = _dependency("device", name="arm-1", wait=True)

    plan = prepare_dependency_graph(
        [
            (package, ()),
            (
                deployment,
                (
                    managed,
                    managed,
                    _dependency("package", name="base", version="2", wait=False),
                    external,
                    external,
                    _dependency("device", name="arm-1", wait=False),
                ),
            ),
        ]
    )
    graph = plan.dependency_graph

    assert graph.edges == ((package, deployment),)
    assert graph.external_references == (
        external,
        _dependency("device", name="arm-1", wait=False),
    )
    assert len(plan.dependencies) == EXPECTED_RESOLVED_DEPENDENCIES
    assert tuple(item.dependency.wait for item in plan.dependencies) == (
        True,
        False,
        True,
        False,
    )


def test_scope_irrelevant_to_reference_kind_is_dropped() -> None:
    role = _identity("role", "viewer", guid="role-guid", organization="org-a")
    deployment = _identity(
        "deployment", "worker", organization="org-a", project="project-a"
    )

    graph = build_dependency_graph(
        [
            (role, ()),
            (
                deployment,
                (_dependency("role", guid="role-guid"),),
            ),
        ]
    )

    assert graph.edges == ((role, deployment),)


def test_rolebinding_identity_is_composite_and_does_not_require_a_name() -> None:
    role = ResourceReference(kind="ROLE", name="reader")
    subject = ResourceReference(kind="UserGroup", guid="group-guid")
    domain = ResourceReference(kind="organization", guid="org-a")
    binding = ResourceIdentity(
        kind="ROLEBINDING", role=role, subject=subject, domain=domain
    )
    duplicate_binding = ResourceIdentity(
        kind="rolebinding", role=role, subject=subject, domain=domain
    )

    assert binding.kind == "rolebinding"
    with pytest.raises(ApplierValidationError, match="duplicate"):
        build_dependency_graph([(binding, ()), (duplicate_binding, ())])

    named_binding = binding.model_copy(
        update={"name": "platform-display-name", "guid": "binding-guid"}
    )
    graph = build_dependency_graph([(named_binding, ())])
    assert graph.managed[0].name is None
    assert graph.managed[0].guid is None


def test_rolebinding_components_use_known_local_name_and_guid_aliases() -> None:
    role = _identity("role", "reader", guid="role-guid", organization="org-a")
    group = _identity("usergroup", "operators", guid="group-guid", organization="org-a")
    first = ResourceIdentity(
        kind="rolebinding",
        scope=ResourceScope(organization_guid="org-a"),
        role=ResourceReference(kind="role", name="reader"),
        subject=ResourceReference(kind="usergroup", name="operators"),
        domain=ResourceReference(kind="organization", guid="org-a"),
    )
    alias_binding = ResourceIdentity(
        kind="rolebinding",
        scope=ResourceScope(organization_guid="org-a"),
        role=ResourceReference(kind="role", guid="role-guid"),
        subject=ResourceReference(kind="usergroup", guid="group-guid"),
        domain=ResourceReference(kind="organization", guid="org-a"),
    )

    with pytest.raises(ApplierValidationError, match="duplicate"):
        build_dependency_graph(
            [(role, ()), (group, ()), (first, ()), (alias_binding, ())]
        )


def test_duplicate_managed_identity_is_rejected() -> None:
    resource = _identity("deployment", "worker", organization="org-a", project="p-a")

    with pytest.raises(ApplierValidationError, match="duplicate"):
        build_dependency_graph([(resource, ()), (resource, ())])


def test_conflicting_and_ambiguous_local_aliases_are_rejected() -> None:
    first = _identity("deployment", "first", guid="shared-guid")
    second = _identity("deployment", "second", guid="shared-guid")
    dependent = _identity("deployment", "dependent")

    with pytest.raises(ApplierValidationError, match="ambiguous"):
        build_dependency_graph(
            [
                (first, ()),
                (second, ()),
                (dependent, (_dependency("deployment", guid="shared-guid"),)),
            ]
        )

    target = _identity("deployment", "known", guid="known-guid")
    with pytest.raises(ApplierValidationError, match="conflict"):
        build_dependency_graph(
            [
                (
                    target,
                    (),
                ),
                (
                    dependent,
                    (_dependency("deployment", name="known", guid="other-guid"),),
                ),
            ]
        )


def test_self_edge_and_multi_node_cycle_are_rejected() -> None:
    first = _identity("deployment", "first")
    second = _identity("deployment", "second")

    with pytest.raises(ApplierValidationError, match="itself"):
        build_dependency_graph([(first, (_dependency("deployment", name="first"),))])

    with pytest.raises(ApplierValidationError, match="cycle"):
        build_dependency_graph(
            [
                (first, (_dependency("deployment", name="second"),)),
                (second, (_dependency("deployment", name="first"),)),
            ]
        )


def test_unresolved_references_are_metadata_only_and_never_managed_nodes() -> None:
    deployment = _identity("deployment", "worker")
    package = _dependency("package", name="external-package", version="3")
    user = _dependency("user", guid="external-user")

    graph = build_dependency_graph([(deployment, (package, user))])

    assert graph.managed == (deployment,)
    assert graph.edges == ()
    assert graph.external_references == (package, user)
