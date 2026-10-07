"""Declarative behavior contracts, independent of live platform services."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from rapyuta_io_sdk_v2.apply import (
    Applier,
    ApplyError,
    ApplyExecutionError,
    AsyncApplier,
    Outcome,
)
from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.context import RequestContext
from rapyuta_io_sdk_v2.exceptions import (
    HttpAlreadyExistsError,
    PermissionDeniedError,
    UnauthorizedAccessError,
)
from rapyuta_io_sdk_v2.features import FeatureDisabledError
from rapyuta_io_sdk_v2.models import Deployment, Package, Role, RoleBinding


def configuration():
    return Configuration(load_cli_config=False, features={"apply": True})


def role(name="reader", **metadata):
    return Role.model_validate(
        {"kind": "Role", "metadata": {"name": name, **metadata}, "spec": {}}
    )


def package(version="v1"):
    return Package.model_validate(
        {
            "kind": "Package",
            "metadata": {"name": "app", "version": version},
            "spec": {"runtime": "cloud"},
        }
    )


def deployment(name="app", dependency="app", wait=False):
    return Deployment.model_validate(
        {
            "kind": "Deployment",
            "metadata": {"name": name, "depends": {"nameOrGUID": "app", "version": "v2"}},
            "spec": {
                "runtime": "cloud",
                "depends": [{"nameOrGUID": dependency, "wait": wait}]
                if dependency
                else [],
            },
        }
    )


def client():
    result = SimpleNamespace(config=configuration())
    result.create_role = Mock(side_effect=lambda value, **kwargs: value)
    result.delete_role = Mock()
    return result


def test_disabled_feature_checked_before_dependencies(monkeypatch):
    c = SimpleNamespace(config=Configuration(load_cli_config=False))
    importer = Mock(side_effect=AssertionError("must not import dependencies"))
    monkeypatch.setattr("rapyuta_io_sdk_v2.apply.engine.require_dependency", importer)
    with pytest.raises(FeatureDisabledError):
        Applier(c)
    importer.assert_not_called()


def test_render_values_secrets_filters_strict_and_no_calls(tmp_path):
    manifest = tmp_path / "role.yaml"
    manifest.write_text(
        "kind: Role\nmetadata:\n  name: '{{ nested.name | upper }}'\n  labels:\n    secret: '{{ secrets.token }}'\nspec: {}\n"
    )
    c = client()
    applier = Applier(
        c,
        tmp_path,
        values=[{"nested": {"name": "old", "kept": 1}}, {"nested": {"name": "reader"}}],
        secrets={"token": "yes"},
    )
    resources = applier.render()
    assert resources[0].metadata.name == "READER"
    assert applier.values["nested"]["kept"] == 1
    assert resources[0].metadata.labels == {"secret": "yes"}
    c.create_role.assert_not_called()
    with pytest.raises(ApplyError, match="Cannot render"):
        Applier(c, manifest).render()


def test_versioned_identity_order_and_reverse_delete():
    c = client()
    resources = [deployment(dependency=None), package("v1"), package("v2")]
    plan = Applier(c, resources).plan()
    assert set(plan.layers[0]) == {"package:app:v1", "package:app:v2"}
    assert plan.layers[1] == ["deployment:app"]
    assert Applier(c, resources).plan(operation="delete").layers == list(
        reversed(plan.layers)
    )


def test_guid_dependency_uses_manifest_identity_and_package_version():
    app = package("v2")
    app.metadata.guid = "pkg-guid"
    other_version = package("v1")
    other_version.metadata.guid = "pkg-guid"
    child = deployment(dependency=None)
    child.metadata.depends.name_or_guid = "pkg-guid"
    resources = [child, other_version, app]
    applier = Applier(client(), resources)
    layers = applier.plan().layers
    assert set(layers[0]) == {"package:app:v1", "package:app:v2"}
    assert layers[1] == ["deployment:app"]
    assert applier.plan(operation="delete").layers == list(reversed(layers))
    # A GUID for a different package version remains an external dependency.
    child.metadata.depends.version = "v3"
    assert len(Applier(client(), resources).plan().layers) == 1


def test_guid_alias_applies_to_other_resource_kinds():
    from rapyuta_io_sdk_v2.models import Network

    network = Network.model_validate(
        {
            "metadata": {"name": "ros", "guid": "network-guid"},
            "spec": {"runtime": "cloud", "type": "routed", "rosDistro": "noetic"},
        }
    )
    child = Deployment.model_validate(
        {
            "metadata": {"name": "app"},
            "spec": {
                "runtime": "cloud",
                "rosNetworks": [{"depends": {"nameOrGUID": "network-guid"}}],
            },
        }
    )
    assert Applier(client(), [child, network]).plan().layers == [
        ["network:ros"],
        ["deployment:app"],
    ]


@pytest.mark.parametrize(
    "resources",
    [
        lambda: [role("one", guid="two"), role("two")],
        lambda: [role("one", guid="same"), role("two", guid="same")],
    ],
)
def test_ambiguous_guid_aliases_rejected_before_writes(resources):
    c = client()
    with pytest.raises(ApplyError, match="Ambiguous resource reference"):
        Applier(c, resources()).apply()
    c.create_role.assert_not_called()


def test_typed_network_infers_kind_on_copy_and_standalone_identity():
    from rapyuta_io_sdk_v2.models import Network

    network = Network.model_validate(
        {
            "metadata": {"name": "ros"},
            "spec": {"runtime": "cloud", "type": "routed", "rosDistro": "noetic"},
        }
    )
    assert network.kind is None
    assert network.identity == "network:ros"
    applier = Applier(client(), network)
    rendered = applier.render()
    assert rendered[0].kind == "Network"
    assert applier.plan().layers == [["network:ros"]]
    assert applier.plan(operation="delete").layers == [["network:ros"]]
    assert network.kind is None


@pytest.mark.parametrize(
    "resources",
    [
        lambda: [role(), role()],
        lambda: [deployment("one", "two"), deployment("two", "one")],
    ],
)
def test_invalid_graph_prevents_all_writes(resources):
    c = client()
    with pytest.raises(ApplyError):
        Applier(c, resources()).apply()
    c.create_role.assert_not_called()


def test_capability_validation_precedes_writes():
    c = client()
    org = {
        "kind": "Organization",
        "metadata": {"name": "org", "guid": "o1"},
        "spec": {"members": []},
    }
    with pytest.raises(ApplyError, match="does not support deletion"):
        Applier(c, [role(), org]).delete()
    c.delete_role.assert_not_called()


def test_conflict_update_immutable_and_auth_failure():
    c = client()
    c.create_role.side_effect = HttpAlreadyExistsError()
    c.update_role = Mock(side_effect=lambda name, value, **kwargs: value)
    report = Applier(c, role()).apply()
    assert report.results[0].outcome == Outcome.UPDATED
    assert c.update_role.call_args.args[0] == "reader"
    c.create_package = Mock(side_effect=HttpAlreadyExistsError())
    assert Applier(c, package()).apply().results[0].outcome == Outcome.EXISTS
    c.create_role.side_effect = UnauthorizedAccessError()
    c.update_role.reset_mock()
    failed = Applier(c, role()).apply()
    assert failed.results[0].outcome == Outcome.FAILED
    c.update_role.assert_not_called()
    with pytest.raises(ApplyExecutionError) as caught:
        failed.raise_for_errors()
    assert caught.value.report is failed


def test_permission_denied_can_update():
    c = client()
    error = PermissionDeniedError("denied", status_code=403)
    c.create_role.side_effect = error
    c.update_role = Mock(return_value=role())
    assert Applier(c, role()).apply().results[0].outcome == Outcome.UPDATED


def test_retain_and_dryrun():
    c = client()
    retained = role(labels={"rapyuta.io/deletionPolicy": "retain"})
    assert Applier(c, retained).delete().results[0].outcome == Outcome.RETAINED
    c.delete_role.assert_not_called()
    assert Applier(c, role()).apply(dry_run=True).results[0].outcome == Outcome.PLANNED
    c.create_role.assert_not_called()


def test_failure_stops_unscheduled_work_and_records_skipped():
    c = client()
    c.create_role.side_effect = RuntimeError("bad request")
    report = Applier(c, [role("one"), role("two"), role("three")], workers=1).apply()
    assert [r.outcome for r in report.results] == [
        Outcome.FAILED,
        Outcome.SKIPPED,
        Outcome.SKIPPED,
    ]
    assert c.create_role.call_count == 1


def test_explicit_external_readiness_and_missing_dependency():
    c = client()
    c.get_deployment = Mock(
        return_value=SimpleNamespace(
            status=SimpleNamespace(status="Pending", phase="Provisioning")
        )
    )
    c.create_deployment = Mock()
    report = Applier(
        c,
        deployment("child", "existing", True),
        readiness_attempts=2,
        readiness_interval=0,
    ).apply()
    assert report.results[0].outcome == Outcome.FAILED
    assert c.get_deployment.call_count == 2
    c.create_deployment.assert_not_called()
    c.get_deployment.return_value.status.status = "Running"
    report = Applier(
        c, deployment("child", "existing", True), readiness_interval=0
    ).apply()
    assert report.successful
    c.create_deployment.assert_called_once()


def test_bulk_role_binding_add_remove():
    binding = RoleBinding.model_validate(
        {
            "kind": "RoleBinding",
            "metadata": {},
            "spec": {
                "roleRef": {"name": "reader"},
                "domain": {"kind": "Project", "name": "proj"},
                "subject": {"kind": "ServiceAccount", "name": "robot"},
            },
        }
    )
    c = client()
    c.update_role_binding = Mock()
    assert Applier(c, binding).apply().successful
    added = c.update_role_binding.call_args.args[0]
    assert len(added.new_bindings) == 1 and added.old_bindings == []
    assert Applier(c, binding).delete().successful
    removed = c.update_role_binding.call_args.args[0]
    assert removed.new_bindings == [] and len(removed.old_bindings) == 1


def test_project_docker_cache_create_then_update_without_mutating_input():
    from rapyuta_io_sdk_v2.models import Project, ProjectList

    project = Project.model_validate(
        {
            "kind": "Project",
            "metadata": {"name": "project"},
            "spec": {
                "features": {
                    "dockerCache": {
                        "enabled": True,
                        "proxyDevice": "device",
                        "proxyInterface": "eth0",
                        "registrySecret": "registry",
                        "registryURL": "https://registry.test",
                    }
                }
            },
        }
    )
    c = client()
    existing = project.model_copy(deep=True)
    existing.metadata.guid = "p1"
    existing.status = SimpleNamespace(status="Success")
    c.list_projects = Mock(
        side_effect=[ProjectList(items=[]), ProjectList(items=[existing])]
    )
    c.create_project = Mock(return_value=existing)
    c.update_project = Mock(return_value=existing)
    report = Applier(c, project, readiness_interval=0).apply()
    assert report.successful
    assert not c.create_project.call_args.args[0].spec.features.docker_cache.enabled
    assert c.update_project.call_args.args[0].spec.features.docker_cache.enabled
    assert c.update_project.call_args.kwargs["project_guid"] == "p1"
    assert project.spec.features.docker_cache.enabled
    assert project.metadata.guid is None


def test_user_group_lookup_and_update_explicit_ids():
    from rapyuta_io_sdk_v2.models import UserGroupCreate, UserGroupList

    group = UserGroupCreate.model_validate(
        {"kind": "UserGroup", "metadata": {"name": "robots"}, "spec": {}}
    )
    c = client()
    existing = group.model_copy(deep=True)
    existing.metadata.guid = "g1"
    c.create_user_group = Mock(side_effect=HttpAlreadyExistsError())
    c.list_user_groups = Mock(return_value=UserGroupList(items=[existing]))
    c.update_user_group = Mock(return_value=existing)
    c.delete_user_group = Mock()
    assert Applier(c, group).apply().successful
    assert c.update_user_group.call_args.args[:2] == ("robots", "g1")
    assert Applier(c, group).delete().successful
    assert c.delete_user_group.call_args.args == ("robots", "g1")
    assert group.metadata.guid is None


def test_delete_secret_response_does_not_require_create_credentials():
    from rapyuta_io_sdk_v2.models import Secret

    secret = Secret.model_validate(
        {
            "kind": "Secret",
            "metadata": {"name": "registry"},
            "spec": {
                "type": "Docker",
                "docker": {
                    "registry": "https://registry.test",
                    "username": "u",
                    "email": "e",
                },
            },
        }
    )
    c = client()
    c.delete_secret = Mock()
    assert Applier(c, secret).delete().successful
    c.delete_secret.assert_called_once_with("registry", context=None)


@pytest.mark.parametrize(
    "kind,spec,state",
    [
        ("Disk", {"capacity": 4}, {"status": "Available"}),
        (
            "Network",
            {"runtime": "cloud", "type": "routed", "rosDistro": "noetic"},
            {"phase": "Succeeded", "status": "Running"},
        ),
    ],
)
def test_disk_and_network_wait_for_ready(kind, spec, state):
    c = client()
    resource = {"kind": kind, "metadata": {"name": "resource"}, "spec": spec}
    created = SimpleNamespace(metadata=SimpleNamespace(name="resource"))
    setattr(c, f"create_{kind.lower()}", Mock(return_value=created))
    ready = SimpleNamespace(status=SimpleNamespace(**state))
    getter = Mock(return_value=ready)
    setattr(c, f"get_{kind.lower()}", getter)
    assert Applier(c, resource, readiness_interval=0).apply().successful
    getter.assert_called_once_with("resource", context=None)


def test_real_client_resource_request_contracts():
    import json

    import httpx

    from rapyuta_io_sdk_v2.client import Client

    calls = []

    def respond(request):
        calls.append(request)
        if request.method == "POST":
            return httpx.Response(409)
        if request.method == "PUT":
            return httpx.Response(200, json=json.loads(request.content))
        return httpx.Response(204)

    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        with Client(configuration(), transport=transport) as c:
            assert Applier(c, role()).apply().successful
            assert Applier(c, role()).delete().successful
    assert [(r.method, r.url.path) for r in calls] == [
        ("POST", "/v2/roles/"),
        ("PUT", "/v2/roles/reader/"),
        ("DELETE", "/v2/roles/reader/"),
    ]


@pytest.mark.asyncio
async def test_async_execution_and_failure_settles_inflight():
    c = client()
    events = []

    async def create(value, *, context=None):
        if value.metadata.name == "one":
            raise RuntimeError("failed")
        await asyncio.sleep(0)
        events.append(value.metadata.name)
        return value

    c.create_role = AsyncMock(side_effect=create)
    report = await AsyncApplier(
        c, [role("one"), role("two"), role("three")], workers=2
    ).apply()
    assert [r.outcome for r in report.results] == [
        Outcome.FAILED,
        Outcome.CREATED,
        Outcome.SKIPPED,
    ]
    assert events == ["two"]
    assert c.create_role.await_count == 2


@pytest.mark.asyncio
async def test_async_cancellation_settles_all_inflight_tasks():
    c = client()
    started = set()
    settled = set()
    ready = asyncio.Event()

    async def create(value, *, context=None):
        name = value.metadata.name
        started.add(name)
        if len(started) == 2:
            ready.set()
        try:
            await asyncio.Event().wait()
        finally:
            settled.add(name)

    c.create_role = AsyncMock(side_effect=create)
    operation = asyncio.create_task(
        AsyncApplier(c, [role("one"), role("two"), role("three")], workers=2).apply()
    )
    await asyncio.wait_for(ready.wait(), timeout=2)
    operation.cancel()
    with pytest.raises(asyncio.CancelledError):
        await operation
    assert started == settled == {"one", "two"}
    assert c.create_role.await_count == 2


@pytest.mark.asyncio
async def test_async_readiness_and_context():
    c = client()
    c.get_deployment = AsyncMock(
        return_value=SimpleNamespace(
            status=SimpleNamespace(status="Running", phase="Succeeded")
        )
    )
    c.create_deployment = AsyncMock()
    context = RequestContext(request_id="apply-request")
    report = await AsyncApplier(
        c, deployment("child", "existing", True), context=context
    ).apply()
    assert report.successful
    assert c.get_deployment.call_args.kwargs["context"] is context
    c.create_deployment.assert_awaited_once()


def test_cli_getenv_filter_is_available_and_can_be_overridden(tmp_path, monkeypatch):
    path = tmp_path / "role.yaml"
    path.write_text(
        'kind: Role\nmetadata:\n  name: \'{{ "default" | getenv("SDK_TEST_ROLE_NAME") }}\'\nspec: {}\n'
    )
    monkeypatch.setenv("SDK_TEST_ROLE_NAME", "from-env")
    assert Applier(client(), path).render()[0].metadata.name == "from-env"
    assert (
        Applier(client(), path, filters={"getenv": lambda default, name: "custom"})
        .render()[0]
        .metadata.name
        == "custom"
    )


def test_generator_resources_survive_planning_and_repeated_execution():
    c = client()
    applier = Applier(c, (r for r in [role("generator")]))
    assert applier.plan().layers == [["role:generator"]]
    assert len(applier.apply().results) == 1
    assert len(applier.apply().results) == 1
    assert len(applier.delete().results) == 1
    assert c.create_role.call_count == 2
    c.delete_role.assert_called_once_with("generator", context=None)


def test_broken_symlink_manifest_is_rejected_without_recursion(tmp_path):
    link = tmp_path / "broken.yaml"
    link.symlink_to(tmp_path / "missing.yaml")
    with pytest.raises(ApplyError, match="broken symlink"):
        Applier(client(), link).render()


def test_custom_resource_model_registration_and_operations():
    from typing import ClassVar, Literal

    class CustomRole(Role):
        resource_kind: ClassVar[str] = "CustomRole"
        kind: Literal["CustomRole"] = "CustomRole"

        def create(self, client, *, context=None):
            return client.apply_custom(self, context=context)

        def _delete(self, client, *, context=None):
            client.delete_custom(self, context=context)

        async def create_async(self, client, *, context=None):
            return await client.apply_custom(self, context=context)

        async def _delete_async(self, client, *, context=None):
            await client.delete_custom(self, context=context)

    c = client()
    c.apply_custom = Mock(side_effect=lambda resource, **kwargs: resource)
    c.delete_custom = Mock()
    custom = CustomRole.model_validate({"metadata": {"name": "custom"}, "spec": {}})
    applier = Applier(c, custom, resource_models={"CustomRole": CustomRole})
    assert applier.plan().layers == [["customrole:custom"]]
    assert applier.apply().results[0].outcome == Outcome.CREATED
    assert applier.delete().results[0].outcome == Outcome.DELETED
    assert isinstance(c.apply_custom.call_args.args[0], CustomRole)
    assert isinstance(c.delete_custom.call_args.args[0], CustomRole)


def test_applier_dispatches_to_model_methods(monkeypatch):
    from rapyuta_io_sdk_v2.resource_operations import ResourceResult

    c = client()
    calls = []
    context = RequestContext(request_id="apply-request")

    def operate(resource, client, **kwargs):
        calls.append((resource, client, kwargs))
        return ResourceResult(identity=resource.identity, outcome=Outcome.CREATED)

    monkeypatch.setattr(Role, "apply", operate)
    monkeypatch.setattr(Role, "delete", operate)
    applier = Applier(
        c, role(), context=context, readiness_attempts=3, readiness_interval=0.1
    )
    assert applier.apply(dry_run=True).successful
    assert calls == []
    assert applier.apply().successful
    assert applier.delete().successful
    assert len(calls) == 2
    assert all(call[1] is c for call in calls)
    assert all(
        call[2]
        == {
            "context": context,
            "readiness_attempts": 3,
            "readiness_interval": 0.1,
        }
        for call in calls
    )
    c.create_role.assert_not_called()
    c.delete_role.assert_not_called()


@pytest.mark.asyncio
async def test_async_applier_dispatches_to_model_methods(monkeypatch):
    from rapyuta_io_sdk_v2.resource_operations import ResourceResult

    c = client()
    calls = []
    context = RequestContext(request_id="apply-request")

    async def operate(resource, client, **kwargs):
        calls.append((resource, client, kwargs))
        return ResourceResult(identity=resource.identity, outcome=Outcome.CREATED)

    monkeypatch.setattr(Role, "apply_async", operate)
    monkeypatch.setattr(Role, "delete_async", operate)
    applier = AsyncApplier(
        c, role(), context=context, readiness_attempts=3, readiness_interval=0.1
    )
    assert (await applier.apply(dry_run=True)).successful
    assert calls == []
    assert (await applier.apply()).successful
    assert (await applier.delete()).successful
    assert len(calls) == 2
    assert all(call[1] is c for call in calls)
    assert all(
        call[2]
        == {
            "context": context,
            "readiness_attempts": 3,
            "readiness_interval": 0.1,
        }
        for call in calls
    )


def test_resource_registration_requires_model_subclasses():
    with pytest.raises(TypeError, match="ResourceModel subclasses"):
        Applier(client(), resource_models={"Wrong": object})


@pytest.mark.parametrize(
    "kwargs",
    [
        {"workers": 0},
        {"workers": 1.5},
        {"workers": True},
        {"readiness_attempts": 0},
        {"readiness_attempts": 1.5},
        {"readiness_attempts": True},
        {"readiness_interval": -1},
        {"readiness_interval": float("inf")},
        {"readiness_interval": float("nan")},
        {"readiness_interval": True},
    ],
)
def test_invalid_execution_limits_rejected_before_operations(kwargs):
    c = client()
    with pytest.raises(ValueError):
        Applier(c, role(), **kwargs)
    c.create_role.assert_not_called()


def test_invalid_context_rejected_before_operations():
    c = client()
    with pytest.raises(TypeError, match="RequestContext"):
        Applier(c, role(), context=object())
    c.create_role.assert_not_called()


def test_render_rejects_invalid_operation_before_reading_manifests(tmp_path):
    with pytest.raises(ValueError, match="operation must be"):
        Applier(client(), tmp_path / "missing.yaml").render(operation="unknown")


def test_delete_response_secret_with_omitted_kind():
    from rapyuta_io_sdk_v2.models import Secret

    secret = Secret.model_validate(
        {
            "kind": None,
            "metadata": {"name": "hidden"},
            "spec": {"type": "Opaque"},
        }
    )
    c = client()
    c.delete_secret = Mock()
    assert Applier(c, secret).delete().successful
    c.delete_secret.assert_called_once_with("hidden", context=None)
    assert secret.kind is None


@pytest.mark.asyncio
async def test_custom_model_operations_use_async_client():
    from typing import ClassVar, Literal

    class CustomRole(Role):
        resource_kind: ClassVar[str] = "CustomRole"
        kind: Literal["CustomRole"] = "CustomRole"

        def create(self, client, *, context=None):
            return client.apply_custom(self, context=context)

        def _delete(self, client, *, context=None):
            client.delete_custom(self, context=context)

        async def create_async(self, client, *, context=None):
            return await client.apply_custom(self, context=context)

        async def _delete_async(self, client, *, context=None):
            await client.delete_custom(self, context=context)

    c = client()
    c.apply_custom = AsyncMock(side_effect=lambda resource, **kwargs: resource)
    c.delete_custom = AsyncMock()
    custom = CustomRole.model_validate({"metadata": {"name": "custom"}, "spec": {}})
    applier = AsyncApplier(c, custom, resource_models={"CustomRole": CustomRole})
    assert (await applier.apply()).successful
    assert (await applier.delete()).successful
    c.apply_custom.assert_awaited_once()
    c.delete_custom.assert_awaited_once()


def test_custom_model_kind_is_explicit_and_independent_of_class_name():
    from typing import ClassVar, Literal

    class DifferentClassName(Role):
        resource_kind: ClassVar[str] = "CustomKind"
        kind: Literal["CustomKind"] | None = None

    resource = DifferentClassName.model_validate(
        {"metadata": {"name": "custom"}, "spec": {}}
    )
    applier = Applier(
        client(), resource, resource_models={"CUSTOMKIND": DifferentClassName}
    )
    assert resource.identity == "customkind:custom"
    assert applier.plan().layers == [["customkind:custom"]]
    assert isinstance(applier.render()[0], DifferentClassName)
    assert resource.kind is None


def test_registry_kind_must_match_explicit_model_kind_before_imports(monkeypatch):
    importer = Mock(side_effect=AssertionError("must validate registry first"))
    monkeypatch.setattr("rapyuta_io_sdk_v2.apply.engine.require_dependency", importer)
    with pytest.raises(ValueError, match="resource_kind"):
        Applier(client(), resource_models={"Alias": Role})
    importer.assert_not_called()


def test_custom_create_model_preserves_delete_override():
    from rapyuta_io_sdk_v2.models import SecretCreate

    class CustomSecret(SecretCreate):
        def _delete(self, client, *, context=None):
            client.delete_custom_secret(self, context=context)

    secret = CustomSecret.model_validate(
        {
            "metadata": {"name": "custom"},
            "spec": {"type": "Opaque", "data": {"key": "value"}},
        }
    )
    c = client()
    c.delete_custom_secret = Mock()
    applier = Applier(c, secret, resource_models={"Secret": CustomSecret})
    assert isinstance(applier.render(operation="delete")[0], CustomSecret)
    assert applier.delete().successful
    c.delete_custom_secret.assert_called_once()
    assert isinstance(c.delete_custom_secret.call_args.args[0], CustomSecret)


def test_project_context_binding_uses_copy_and_configured_rio_values():
    from rapyuta_io_sdk_v2.models import Project

    c = client()
    c.config.project_name = "project-label"
    c.config.organization_name = "organization-label"
    c.config.organization_short_id = "short-id"
    c.config.organization_guid = "configured-org"
    context = RequestContext(organization_guid="selected-org")
    project = Project.model_validate({"metadata": {"name": "project"}, "spec": {}})
    applier = Applier(c, project, context=context)
    assert applier.render()[0].metadata.organization_guid == "selected-org"
    assert project.metadata.organization_guid is None
    assert applier.values["rio"]["project"]["name"] == "project-label"
    assert applier.values["rio"]["organization"]["name"] == "organization-label"
    assert applier.values["rio"]["organization"]["short_id"] == "short-id"
