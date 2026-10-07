"""Direct model operations share policy without the manifest renderer."""

import asyncio
import subprocess
import sys
from types import SimpleNamespace
from typing import ClassVar, Literal
from unittest.mock import AsyncMock, Mock

import pytest

from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.context import RequestContext
from rapyuta_io_sdk_v2.exceptions import (
    HttpAlreadyExistsError,
    HttpNotFoundError,
    UnauthorizedAccessError,
)
from rapyuta_io_sdk_v2.features import FeatureDisabledError
from rapyuta_io_sdk_v2.models import (
    Network,
    Organization,
    Package,
    Project,
    Role,
    RoleBinding,
    Secret,
    SecretCreate,
    UserGroup,
    UserGroupCreate,
)
from rapyuta_io_sdk_v2.models.resource import ResourceModel
from rapyuta_io_sdk_v2.resource_operations import ApplyError, Outcome, Request


def client(**methods):
    return SimpleNamespace(
        config=Configuration(load_cli_config=False, features={"apply": True}), **methods
    )


def role(**metadata):
    return Role.model_validate({"metadata": {"name": "reader", **metadata}, "spec": {}})


def test_direct_apply_context_and_no_input_mutation():
    original = role()
    before = original.model_dump(by_alias=True)
    context = RequestContext(project_guid="project")

    def create(body, **kwargs):
        assert body is not original
        assert kwargs == {"context": context}
        body.metadata.guid = "created"
        return body

    result = original.apply(client(create_role=Mock(side_effect=create)), context=context)
    assert result.identity == "role:reader"
    assert result.outcome == Outcome.CREATED
    assert result.resource.metadata.guid == "created"
    assert original.model_dump(by_alias=True) == before
    assert {"endpoint", "resource_kind", "mutable", "can_apply"}.isdisjoint(
        original.model_dump()
    )


@pytest.mark.asyncio
async def test_direct_async_apply_and_delete():
    original = role()
    context = RequestContext(request_id="test")
    c = client(create_role=AsyncMock(return_value=original), delete_role=AsyncMock())
    result = await original.apply_async(c, context=context)
    assert result.outcome == Outcome.CREATED
    c.create_role.assert_awaited_once()
    assert c.create_role.call_args.kwargs == {"context": context}
    result = await original.delete_async(c, context=context)
    assert result.outcome == Outcome.DELETED
    c.delete_role.assert_awaited_once_with("reader", context=context)


@pytest.mark.parametrize(
    "status,expected", [(401, Outcome.FAILED), (403, Outcome.UPDATED)]
)
def test_authentication_and_mutable_permission_policy(status, expected):
    c = client(
        create_role=Mock(side_effect=UnauthorizedAccessError(status_code=status)),
        update_role=Mock(return_value=role()),
    )
    assert role().apply(c).outcome == expected
    assert c.update_role.call_count == (status == 403)


def test_conflict_update_and_immutable_exists():
    c = client(create_role=Mock(side_effect=HttpAlreadyExistsError()), update_role=Mock())
    assert role().apply(c).outcome == Outcome.UPDATED
    c.update_role.assert_called_once()
    resource = Package.model_validate(
        {"metadata": {"name": "app", "version": "v2"}, "spec": {"runtime": "cloud"}}
    )
    c.create_package = Mock(side_effect=HttpAlreadyExistsError())
    assert resource.apply(c).outcome == Outcome.EXISTS
    c.delete_package = Mock()
    assert resource.delete(c).identity == "package:app:v2"
    c.delete_package.assert_called_once_with("app", "v2")


def test_delete_retain_and_not_found():
    c = client(delete_role=Mock(side_effect=HttpNotFoundError()))
    assert role().delete(c).outcome == Outcome.NOT_FOUND
    c.delete_role.reset_mock()
    assert (
        role(labels={"rapyuta.io/deletionPolicy": "retain"}).delete(c).outcome
        == Outcome.RETAINED
    )
    c.delete_role.assert_not_called()


def test_disabled_feature_and_unsupported_models_before_requests():
    c = client(create_role=Mock())
    c.config.features.apply = False
    with pytest.raises(FeatureDisabledError):
        role().apply(c)
    c.create_role.assert_not_called()
    with pytest.raises(ApplyError, match="does not support"):
        ResourceModel().apply(client())
    with pytest.raises(ApplyError, match="Unsupported"):
        role().validate_operation("destroy")
    organization = Organization.model_validate(
        {"metadata": {"name": "org"}, "spec": {"members": []}}
    )
    with pytest.raises(ApplyError, match="requires metadata.guid"):
        organization.apply(client())
    with pytest.raises(ApplyError, match="does not support deletion"):
        organization.delete(client())


@pytest.mark.parametrize(
    "options",
    [
        {"readiness_attempts": 0},
        {"readiness_attempts": True},
        {"readiness_attempts": 1.5},
        {"readiness_interval": -1},
        {"readiness_interval": float("inf")},
        {"readiness_interval": float("nan")},
        {"context": object()},
    ],
)
def test_invalid_execution_arguments_before_requests(options):
    c = client(create_role=Mock())
    with pytest.raises((ValueError, TypeError)):
        role().apply(c, **options)
    c.create_role.assert_not_called()


@pytest.mark.parametrize(
    "response,create_type",
    [
        ({"metadata": {"name": "secret"}, "spec": {"type": "Docker"}}, SecretCreate),
        ({"metadata": {"name": "group"}, "spec": {}}, UserGroupCreate),
    ],
)
def test_response_models_require_create_type_but_support_delete(response, create_type):
    model = Secret if create_type is SecretCreate else UserGroup
    resource = model.model_validate(response)
    with pytest.raises(ApplyError, match="Create model"):
        resource.apply(client())
    if model is Secret:
        c = client(delete_secret=Mock())
        assert resource.delete(c).outcome == Outcome.DELETED
        c.delete_secret.assert_called_once_with("secret")
    else:
        resource.metadata.guid = "group-guid"
        c = client(delete_user_group=Mock())
        assert resource.delete(c).outcome == Outcome.DELETED
        c.delete_user_group.assert_called_once_with("group", "group-guid")


def test_user_group_update_resolves_guid_without_mutation():
    resource = UserGroupCreate.model_validate({"metadata": {"name": "group"}, "spec": {}})
    found = resource.model_copy(deep=True)
    found.metadata.guid = "group-guid"
    c = client(
        create_user_group=Mock(side_effect=HttpAlreadyExistsError()),
        list_user_groups=Mock(return_value=SimpleNamespace(items=[found], metadata=None)),
        update_user_group=Mock(),
    )
    assert resource.apply(c).outcome == Outcome.UPDATED
    args = c.update_user_group.call_args.args
    assert args[:2] == ("group", "group-guid")
    assert args[2].metadata.guid == "group-guid"
    assert resource.metadata.guid is None


def test_project_docker_cache_shell_and_update_preserve_input():
    resource = Project.model_validate(
        {
            "metadata": {"name": "project"},
            "spec": {
                "features": {
                    "dockerCache": {
                        "enabled": True,
                        "proxyDevice": "device",
                        "proxyInterface": "eth0",
                        "registrySecret": "registry",
                        "registryURL": "https://registry",
                    }
                }
            },
        }
    )
    created = resource.model_copy(deep=True)
    created.metadata.guid = "project-guid"
    ready = created.model_copy(update={"status": SimpleNamespace(status="Success")})
    c = client(
        list_projects=Mock(
            side_effect=[
                SimpleNamespace(items=[], metadata=None),
                SimpleNamespace(items=[ready]),
            ]
        ),
        create_project=Mock(return_value=created),
        update_project=Mock(return_value=created),
    )
    before = resource.model_dump(by_alias=True)
    assert resource.dependencies() == ["secret:registry"]
    assert resource.apply(c).outcome == Outcome.UPDATED
    shell = c.create_project.call_args.args[0]
    assert not shell.spec.features.docker_cache.enabled
    assert shell.spec.features.docker_cache.registry_secret is None
    assert c.update_project.call_args.kwargs == {"project_guid": "project-guid"}
    assert resource.model_dump(by_alias=True) == before


def test_role_binding_bulk_and_no_metadata_name():
    resource = RoleBinding.model_validate(
        {
            "metadata": {},
            "spec": {
                "roleRef": {"name": "reader"},
                "domain": {"kind": "Project", "guid": "project-guid"},
                "subject": {"kind": "User", "name": "person"},
            },
        }
    )
    c = client(update_role_binding=Mock())
    assert (
        resource.apply(c).identity
        == "rolebinding:Role:reader:Project:project-guid:User:person"
    )
    body = c.update_role_binding.call_args.args[0]
    assert len(body.new_bindings) == 1 and body.old_bindings == []
    assert resource.delete(c).outcome == Outcome.DELETED
    body = c.update_role_binding.call_args.args[0]
    assert body.new_bindings == [] and len(body.old_bindings) == 1


def test_network_without_kind_and_failed_readiness():
    resource = Network.model_validate(
        {
            "kind": None,
            "metadata": {"name": "ros"},
            "spec": {"runtime": "cloud", "type": "routed", "rosDistro": "noetic"},
        }
    )
    c = client(
        create_network=Mock(),
        get_network=Mock(
            return_value=SimpleNamespace(status=SimpleNamespace(phase="FailedToStart"))
        ),
    )
    result = resource.apply(c, readiness_attempts=1)
    assert result.identity == "network:ros"
    assert result.outcome == Outcome.FAILED
    assert "FailedToStart" in result.error
    assert resource.kind is None


@pytest.mark.asyncio
async def test_async_cancellation_propagates_and_closes_custom_workflow():
    closed = []

    class CustomRole(Role):
        kind: Literal["CustomRole"] = "CustomRole"
        resource_kind: ClassVar[str] = "CustomRole"

        def workflow(self, operation, attempts, interval):
            try:
                yield Request("create_role", (self,))
                return Outcome.CREATED, self
            finally:
                closed.append(True)

    resource = CustomRole.model_validate({"metadata": {"name": "reader"}, "spec": {}})
    c = client(create_role=AsyncMock(side_effect=asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):
        await resource.apply_async(c)
    assert closed == [True]
    c.create_role.side_effect = None
    assert (await resource.apply_async(c)).identity == "customrole:reader"


def test_core_import_and_direct_operation_never_import_renderer_dependencies():
    script = """
import importlib.abc, sys
class RejectExtras(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in ("yaml", "jinja2"):
            raise AssertionError("unexpected extra import: " + fullname)
sys.meta_path.insert(0, RejectExtras())
from types import SimpleNamespace
from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.models import Role
from rapyuta_io_sdk_v2.resource_operations import Outcome
client = SimpleNamespace(config=Configuration(load_cli_config=False, features={"apply": True}), create_role=lambda resource: resource)
resource = Role.model_validate({"metadata": {"name": "reader"}, "spec": {}})
assert resource.apply(client).outcome == Outcome.CREATED
assert "rapyuta_io_sdk_v2.apply.engine" not in sys.modules
"""
    subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    )
