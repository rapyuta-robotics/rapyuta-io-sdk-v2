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

"""Concrete model dependency extraction preserves every declared branch."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from rapyuta_io_sdk_v2.apply._graph import build_dependency_graph
from rapyuta_io_sdk_v2.apply.applier import Applier, AsyncApplier
from rapyuta_io_sdk_v2.apply.source import ManifestSource
from rapyuta_io_sdk_v2.models.applier import (
    ApplierOptions,
    ResourceContext,
    ResourceOutcome,
    ResourceScope,
)
from rapyuta_io_sdk_v2.models.deployment import (
    Deployment,
    DeploymentDevice,
    DeploymentMetadata,
    DeploymentROSNetwork,
    DeploymentSpec,
    DeploymentStaticRoute,
    DeploymentVolume,
    EnvArgsSpec,
)
from rapyuta_io_sdk_v2.models.network import Network, NetworkSpec
from rapyuta_io_sdk_v2.models.organization import (
    Organization,
    OrganizationMember,
    OrganizationSpec,
)
from rapyuta_io_sdk_v2.models.package import (
    DockerSpec,
    Executable,
    Package,
    PackageMetadata,
    PackageSpec,
    PullSecret,
)
from rapyuta_io_sdk_v2.models.project import (
    Features,
    FeaturesDockerCache,
    Project,
    ProjectMember,
    ProjectSpec,
)
from rapyuta_io_sdk_v2.models.role import Role
from rapyuta_io_sdk_v2.models.secret import Secret, SecretSpec
from rapyuta_io_sdk_v2.models.serviceaccount import (
    ServiceAccount,
    ServiceAccountBinding,
    ServiceAccountSpec,
)
from rapyuta_io_sdk_v2.models.usergroup import (
    UserGroup,
    UserGroupBinding,
    UserGroupMember,
    UserGroupSpec,
)
from rapyuta_io_sdk_v2.models.utils import (
    BaseMetadata,
    DeploymentDepends,
    DeviceDepends,
    DiskDepends,
    Domain,
    NetworkDepends,
    PackageDepends,
    SecretDepends,
    SecretKeyRef,
    StaticRouteDepends,
    Subject,
    ValueFrom,
)

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.models.applier import DependencyReference


def _reference_keys(
    references: tuple[DependencyReference, ...],
) -> tuple[tuple[str, str | None, str | None, bool], ...]:
    return tuple(
        (
            reference.reference.kind,
            reference.reference.name,
            reference.reference.version,
            reference.wait,
        )
        for reference in references
    )


def test_deployment_dependencies_keep_all_runtime_and_wait_branches() -> None:
    metadata = DeploymentMetadata.model_construct(
        name="worker",
        depends=PackageDepends(name_or_guid="runtime-package", version="v3"),
    )
    spec = DeploymentSpec.model_construct(
        runtime="cloud",
        volumes=[
            DeploymentVolume.model_construct(
                depends=DiskDepends(name_or_guid="volume-disk")
            )
        ],
        static_routes=[
            DeploymentStaticRoute.model_construct(
                depends=StaticRouteDepends(name_or_guid="static-route")
            )
        ],
        ros_networks=[
            DeploymentROSNetwork.model_construct(
                depends=NetworkDepends(name_or_guid="ros-network")
            )
        ],
        device=DeploymentDevice.model_construct(
            depends=DeviceDepends(name_or_guid="device")
        ),
        depends=[
            DeploymentDepends(name_or_guid="prerequisite", wait=True),
            DeploymentDepends(name_or_guid="no-wait", wait=False),
        ],
        service_account="runtime-account",
        env_args=[
            EnvArgsSpec(
                name="TOKEN",
                value_from=ValueFrom(
                    secret_key_ref=SecretKeyRef(name="runtime-secret", key="token")
                ),
            )
        ],
    )
    deployment = Deployment.model_construct(metadata=metadata, spec=spec)

    assert _reference_keys(deployment.resource_dependencies()) == (
        ("package", "runtime-package", "v3", False),
        ("disk", "volume-disk", None, False),
        ("staticroute", "static-route", None, False),
        ("network", "ros-network", None, False),
        ("device", "device", None, False),
        ("deployment", "prerequisite", None, True),
        ("deployment", "no-wait", None, False),
        ("serviceaccount", "runtime-account", None, False),
        ("secret", "runtime-secret", None, False),
    )


def test_package_network_and_secret_keep_pull_secret_and_device_dependencies() -> None:
    package = Package(
        metadata=PackageMetadata(name="app", version="v1"),
        spec=PackageSpec(
            executables=[
                Executable(
                    docker=DockerSpec(
                        image="example/app:v1",
                        pull_secret=PullSecret(
                            depends=SecretDepends(name_or_guid="registry-secret")
                        ),
                    )
                )
            ]
        ),
    )
    network = Network.model_construct(
        metadata=BaseMetadata(name="device-network"),
        spec=NetworkSpec.model_construct(
            type="routed",
            ros_distro="noetic",
            runtime="device",
            depends=DeviceDepends(name_or_guid="robot-1"),
        ),
    )
    secret = Secret(
        metadata=BaseMetadata(name="device-secret"),
        spec=SecretSpec(
            type="Opaque",
            data={"token": "value"},
            runtime="device",
            depends=DeviceDepends(name_or_guid="robot-1"),
        ),
    )

    assert _reference_keys(package.resource_dependencies()) == (
        ("secret", "registry-secret", None, False),
    )
    assert package.list_dependencies() == ["secret:registry-secret"]
    assert _reference_keys(network.resource_dependencies()) == (
        ("device", "robot-1", None, False),
    )
    assert _reference_keys(secret.resource_dependencies()) == (
        ("device", "robot-1", None, False),
    )


@pytest.mark.parametrize("selector", ["base", "base-guid"])
def test_deployment_package_name_or_guid_dependency_resolves(selector: str) -> None:
    package = Package(
        metadata=PackageMetadata(name="base", guid="base-guid", version="v1"),
        spec=PackageSpec(executables=[]),
    )
    deployment = Deployment.model_construct(
        metadata=DeploymentMetadata.model_construct(
            name="worker",
            depends=PackageDepends(name_or_guid=selector, version="v1"),
        ),
        spec=DeploymentSpec.model_construct(runtime="cloud"),
    )

    graph = build_dependency_graph(
        [
            (package.resource_identity(), ()),
            (deployment.resource_identity(), deployment.resource_dependencies()),
        ]
    )

    assert graph.edges == (
        (package.resource_identity(), deployment.resource_identity()),
    )


@pytest.mark.parametrize("selector", ["registry", "registry-guid"])
def test_package_pull_secret_name_or_guid_dependency_resolves(selector: str) -> None:
    secret = Secret(
        metadata=BaseMetadata(name="registry", guid="registry-guid"),
        spec=SecretSpec(type="Opaque", data={}),
    )
    package = Package(
        metadata=PackageMetadata(name="app", version="v1"),
        spec=PackageSpec(
            executables=[
                Executable(
                    docker=DockerSpec(
                        image="example/app:v1",
                        pull_secret=PullSecret(
                            depends=SecretDepends(name_or_guid=selector)
                        ),
                    )
                )
            ]
        ),
    )

    graph = build_dependency_graph(
        [
            (secret.resource_identity(), ()),
            (package.resource_identity(), package.resource_dependencies()),
        ]
    )

    assert graph.edges == ((secret.resource_identity(), package.resource_identity()),)


def test_organization_project_usergroup_and_serviceaccount_keep_access_edges() -> None:
    user = Subject(kind="User", name="ava")
    project = Project(
        metadata=BaseMetadata(name="alpha"),
        spec=ProjectSpec(
            members=[ProjectMember(subject=user, role_names=["project-reader"])],
            features=Features(
                docker_cache=FeaturesDockerCache(
                    enabled=True,
                    proxy_device="cache-device",
                    proxy_interface="eth0",
                    registry_secret="cache-secret",
                    registry_url="registry.example.test",
                )
            ),
        ),
    )
    organization = Organization(
        metadata=BaseMetadata(name="org", guid="org-guid"),
        spec=OrganizationSpec(members=[]),
    )
    organization.spec.members.append(
        OrganizationMember(subject=user, role_names=["org-reader"])
    )
    usergroup = UserGroup(
        metadata=BaseMetadata(name="ops"),
        spec=UserGroupSpec(
            members=[UserGroupMember(subject=user, role_names=["group-reader"])],
            roles=[
                UserGroupBinding(
                    domain=Domain(kind="Project", name="alpha"),
                    role_name="group-admin",
                )
            ],
        ),
    )
    account = ServiceAccount(
        metadata=BaseMetadata(name="robot"),
        spec=ServiceAccountSpec(
            roles=[
                ServiceAccountBinding(
                    domain=Domain(kind="Project", name="alpha"),
                    role_names=["account-reader"],
                )
            ]
        ),
    )

    assert _reference_keys(project.resource_dependencies()) == (
        ("user", "ava", None, False),
        ("role", "project-reader", None, False),
        ("secret", "cache-secret", None, False),
        ("device", "cache-device", None, False),
    )
    assert _reference_keys(organization.resource_dependencies()) == (
        ("user", "ava", None, False),
        ("role", "org-reader", None, False),
    )
    assert _reference_keys(usergroup.resource_dependencies()) == (
        ("user", "ava", None, False),
        ("role", "group-reader", None, False),
        ("project", "alpha", None, False),
        ("role", "group-admin", None, False),
    )
    assert _reference_keys(account.resource_dependencies()) == (
        ("project", "alpha", None, False),
        ("role", "account-reader", None, False),
    )


def _cross_scope_resources() -> tuple[Organization, Project, Role, Secret]:
    role = Role(metadata=BaseMetadata(name="reader"), spec={"rules": []})
    organization = Organization(
        metadata=BaseMetadata(name="org", guid="org-guid"),
        spec=OrganizationSpec(
            members=[
                OrganizationMember(
                    subject=Subject(kind="User", name="ava"), role_names=["reader"]
                )
            ]
        ),
    )
    secret = Secret(
        metadata=BaseMetadata(name="registry"),
        spec=SecretSpec(type="Opaque", data={"token": "value"}),
    )
    project = Project(
        metadata=BaseMetadata(name="alpha"),
        spec=ProjectSpec(
            features=Features(
                docker_cache=FeaturesDockerCache(
                    enabled=True,
                    proxy_device="cache-device",
                    proxy_interface="eth0",
                    registry_url="registry.example.test",
                    registry_secret="registry",
                )
            )
        ),
    )
    return organization, project, role, secret


@pytest.mark.parametrize("facade", [Applier, AsyncApplier])
def test_cross_scope_dependencies_use_selected_routing_scope(facade: type) -> None:
    organization, project, role, secret = _cross_scope_resources()
    scope = ResourceScope(organization_guid="org-guid", project_guid="project-guid")
    graph = (
        facade(
            ManifestSource(resources=(organization, project, role, secret)),
            ApplierOptions(scope=scope),
        )
        .inspect()
        .dependency_graph
    )

    assert graph.edges == (
        (
            role.resource_identity(scope=scope),
            organization.resource_identity(scope=scope),
        ),
        (secret.resource_identity(scope=scope), project.resource_identity(scope=scope)),
    )
    assert {item.reference.kind for item in graph.external_references} == {
        "user",
        "device",
    }
    assert graph.managed[0].scope == ResourceScope()
    assert graph.managed[1].scope.project_guid is None


def _cross_scope_pair(kind: str) -> tuple[object, object]:
    resources = _cross_scope_resources()
    return (
        (resources[0], resources[2])
        if kind == "organization"
        else (resources[1], resources[3])
    )


def _record_cross_scope_execution(
    monkeypatch: pytest.MonkeyPatch, case: tuple[str, str]
) -> tuple[ManifestSource, list[str], list[str]]:
    dependent, prerequisite = _cross_scope_pair(case[0])
    if case[0] == "organization":
        dependent.metadata.guid = "dummy-organization"
    events: list[str] = []

    def execute(
        resource: object, _client: object, *, context: ResourceContext
    ) -> ResourceOutcome:
        events.append(resource.KIND.lower())
        return ResourceOutcome(
            identity=resource.resource_identity(scope=context.scope),
            operation=case[1],
            status="created" if case[1] == "apply" else "deleted",
        )

    async def execute_async(
        resource: object, client: object, *, context: ResourceContext
    ) -> ResourceOutcome:
        return execute(resource, client, context=context)

    method = "apply" if case[1] == "apply" else "delete_object"
    for model in (type(dependent), type(prerequisite)):
        monkeypatch.setattr(model, method, execute)
        monkeypatch.setattr(model, method + "_async", execute_async)
    resources = (
        (dependent, prerequisite) if case[1] == "apply" else (prerequisite, dependent)
    )
    return (
        ManifestSource(resources=resources),
        events,
        [item.KIND.lower() for item in resources[::-1]],
    )


@pytest.mark.parametrize(
    "case", [("organization", "apply"), ("project", "apply"), ("project", "delete")]
)
def test_sync_cross_scope_execution_order_uses_client_scope(
    configured_client: object, monkeypatch: pytest.MonkeyPatch, case: tuple[str, str]
) -> None:
    source, events, expected = _record_cross_scope_execution(monkeypatch, case)
    result = getattr(Applier(source, ApplierOptions(workers=1)), case[1])(
        configured_client
    )
    assert result.successful
    assert events == expected


@pytest.mark.parametrize(
    "case", [("organization", "apply"), ("project", "apply"), ("project", "delete")]
)
@pytest.mark.asyncio
async def test_async_cross_scope_execution_order_uses_client_scope(
    configured_async_client: object,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[str, str],
) -> None:
    source, events, expected = _record_cross_scope_execution(monkeypatch, case)
    result = await getattr(AsyncApplier(source, ApplierOptions(workers=1)), case[1])(
        configured_async_client
    )
    assert result.successful
    assert events == expected


def _organization_target_resources() -> tuple[Organization, Role]:
    organization, _project, role, _secret = _cross_scope_resources()
    role.metadata.organization_guid = organization.metadata.guid
    return organization, role


@pytest.mark.parametrize("facade", [Applier, AsyncApplier])
@pytest.mark.parametrize("default_guid", [None, "another-organization"])
def test_organization_dependency_routes_using_target_guid(
    facade: type, default_guid: str | None
) -> None:
    organization, role = _organization_target_resources()
    scope = ResourceScope(organization_guid=default_guid)
    graph = (
        facade(
            ManifestSource(resources=(organization, role)), ApplierOptions(scope=scope)
        )
        .inspect()
        .dependency_graph
    )

    assert graph.edges == (
        (role.resource_identity(), organization.resource_identity()),
    )
    assert {item.reference.kind for item in graph.external_references} == {"user"}


def test_sync_organization_membership_waits_for_target_scoped_role(
    configured_client: object,
) -> None:
    organization, role = _organization_target_resources()
    events: list[str] = []
    configured_client.config.organization_guid = None

    def create_role(payload: Role, **_kwargs: object) -> Role:
        events.append("role")
        return payload

    def update_organization(payload: Organization, target_guid: str) -> Organization:
        assert target_guid == organization.metadata.guid
        events.append("organization")
        return payload

    configured_client.create_role = create_role
    configured_client.update_organization = update_organization
    result = Applier(ManifestSource(resources=(organization, role))).apply(
        configured_client
    )

    assert result.successful
    assert events == ["role", "organization"]


@pytest.mark.asyncio
async def test_async_organization_membership_waits_for_target_scoped_role(
    configured_async_client: object,
) -> None:
    organization, role = _organization_target_resources()
    started, release = asyncio.Event(), asyncio.Event()
    events: list[str] = []
    configured_async_client.config.organization_guid = None

    async def create_role(payload: Role, **_kwargs: object) -> Role:
        started.set()
        await release.wait()
        events.append("role")
        return payload

    async def update_organization(
        payload: Organization, target_guid: str
    ) -> Organization:
        assert target_guid == organization.metadata.guid
        events.append("organization")
        return payload

    configured_async_client.create_role = create_role
    configured_async_client.update_organization = update_organization
    active = asyncio.create_task(
        AsyncApplier(ManifestSource(resources=(organization, role))).apply(
            configured_async_client
        )
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        assert events == []
    finally:
        release.set()
        result = await active
    assert result.successful
    assert events == ["role", "organization"]
