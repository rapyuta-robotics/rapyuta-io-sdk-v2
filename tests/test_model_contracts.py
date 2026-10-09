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


from __future__ import annotations

import collections.abc
import importlib
import inspect
import pkgutil
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any, get_args, get_origin, get_type_hints

import httpx
import pytest
from pydantic import BaseModel, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from rapyuta_io_sdk_v2 import AsyncClient, Client, Configuration, models
from rapyuta_io_sdk_v2 import _client_options as client_options
from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError
from rapyuta_io_sdk_v2.models import (
    APIResponse,
    AuthSubjectResponse,
    BulkRoleBindingUpdate,
    ConfigKeyContent,
    ConfigKeyRename,
    ConfigKeyUpload,
    ConfigTree,
    ConfigTreeRevision,
    ConfigValue,
    ConfigValues,
    DeploymentGraph,
    DeploymentHistoryList,
    OAuth2Client,
    OAuth2ClientList,
    OAuth2UpdateURI,
    SharedURL,
)
from rapyuta_io_sdk_v2.models.daemons import DockerProxyConfig
from rapyuta_io_sdk_v2.models.deployment import DeploymentSpec
from rapyuta_io_sdk_v2.models.network import NetworkSpec
from rapyuta_io_sdk_v2.models.package import PackageSpec
from rapyuta_io_sdk_v2.models.user import UserProject
from rapyuta_io_sdk_v2.models.utils import BaseMetadata, Depends
from rapyuta_io_sdk_v2.pydantic_source import ConfigTreeSource

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockFixture


class TreeSettings(BaseSettings):
    """Accept all keys when verifying the modeled configuration-tree source."""

    model_config = SettingsConfigDict(extra="allow")


async def _call(
    method: Callable[..., object], *args: object, **kwargs: object
) -> object:
    result = method(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _all_models() -> list[type[BaseModel]]:
    discovered = set()
    for module in pkgutil.iter_modules(models.__path__, models.__name__ + "."):
        imported = importlib.import_module(module.name)
        discovered.update(
            member
            for _, member in inspect.getmembers(imported, inspect.isclass)
            if issubclass(member, BaseModel)
        )
    return sorted(discovered, key=lambda model: model.__name__)


@pytest.mark.parametrize("model", _all_models(), ids=lambda model: model.__name__)
def test_all_model_field_names_are_snake_case(model: type[BaseModel]) -> None:
    assert all(name == name.lower() for name in model.model_fields)


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
def test_public_client_annotations_exclude_dictionaries(
    client_type: type[Client | AsyncClient],
) -> None:
    for name, method in inspect.getmembers(client_type, inspect.isfunction):
        if name.startswith("_"):
            continue
        hints = _client_type_hints(method)
        assert "return" in hints, name
        for annotation in hints.values():
            assert not _contains_dict(annotation), name
    assert not hasattr(client_type, "update_project_owner")


def _contains_dict(annotation: object) -> bool:
    return (
        annotation is dict
        or get_origin(annotation) is dict
        or any(_contains_dict(arg) for arg in get_args(annotation))
    )


def _request_model(annotation: object) -> type[BaseModel] | None:
    choices = get_args(annotation) or (annotation,)
    return next(
        (
            candidate
            for candidate in choices
            if inspect.isclass(candidate) and issubclass(candidate, BaseModel)
        ),
        None,
    )


def _client_type_hints(method: Callable[..., object]) -> dict[str, Any]:
    # Resolve the shared options and iterators imported only during type checking.
    return get_type_hints(method, localns=vars(client_options) | vars(collections.abc))


def _model_requests() -> list[tuple[str, str, str]]:
    return [
        (mode, name, argument)
        for mode, client_type in [("sync", Client), ("async", AsyncClient)]
        for name, method in inspect.getmembers(client_type, inspect.isfunction)
        for argument, annotation in _client_type_hints(method).items()
        if argument != "return" and _request_model(annotation) is not None
    ]


def _invalid_arguments(method: Callable[..., object], payload: str) -> dict[str, Any]:
    arguments = {
        name: "resource-id"
        for name, parameter in inspect.signature(method).parameters.items()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    }
    arguments[payload] = {}
    return arguments


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _model_requests())
async def test_every_structured_request_rejects_dict_before_http(
    *,
    case: tuple[str, str, str],
    client: Client,
    async_client: AsyncClient,
    mocker: MockFixture,
) -> None:
    mode, name, payload = case
    target = client if mode == "sync" else async_client
    request = mocker.patch.object(target.c, "request")
    method = getattr(target, name)
    with pytest.raises(AttributeError):
        await _call(method, **_invalid_arguments(method, payload))
    request.assert_not_called()


@pytest.mark.parametrize(
    ("model", "python_values", "json_values"),
    [
        (
            BaseMetadata,
            {
                "name": "resource",
                "project_guid": "project",
                "organization_guid": "org",
                "organization_creator_guid": "org-owner",
                "creator_guid": "owner",
                "created_at": "2026-10-09T00:00:00+00:00",
                "updated_at": "2026-10-09T00:00:00+00:00",
                "deleted_at": None,
                "organization_name": "organization",
                "short_guid": "short",
                "project_name": "project-name",
            },
            {
                "name": "resource",
                "projectGUID": "project",
                "organizationGUID": "org",
                "organizationCreatorGUID": "org-owner",
                "creatorGUID": "owner",
                "createdAt": "2026-10-09T00:00:00+00:00",
                "updatedAt": "2026-10-09T00:00:00+00:00",
                "deletedAt": None,
                "organizationName": "organization",
                "shortGUID": "short",
                "projectName": "project-name",
            },
        ),
        (
            DeploymentSpec,
            {
                "runtime": "cloud",
                "env_args": [
                    {
                        "name": "SECRET",
                        "value_from": {
                            "secret_key_ref": {"name": "secret", "key": "key"}
                        },
                    }
                ],
                "ros_networks": [
                    {"depends": {"name_or_guid": "network"}, "domain_id": 7}
                ],
                "static_routes": [{"depends": {"name_or_guid": "route"}}],
                "service_account": "service",
                "network_interface": "eth0",
                "features": {"params": {"block_until_synced": True}},
            },
            {
                "runtime": "cloud",
                "envArgs": [
                    {
                        "name": "SECRET",
                        "valueFrom": {"secretKeyRef": {"name": "secret", "key": "key"}},
                    }
                ],
                "rosNetworks": [{"depends": {"nameOrGUID": "network"}, "domainID": 7}],
                "staticRoutes": [{"depends": {"nameOrGUID": "route"}}],
                "serviceAccount": "service",
                "networkInterface": "eth0",
                "features": {"params": {"blockUntilSynced": True}},
            },
        ),
        (
            NetworkSpec,
            {
                "runtime": "cloud",
                "type": "routed",
                "ros_distro": "foxy",
                "discovery_server": {"server_id": 1, "server_port": 8080},
                "resource_limits": {"cpu": 0.1, "memory": 128},
                "rabbit_mq_creds": {
                    "default_user": "user",
                    "default_password": "password",
                },
                "network_interface": "eth0",
                "restart_policy": "always",
            },
            {
                "runtime": "cloud",
                "type": "routed",
                "rosDistro": "foxy",
                "discoveryServer": {"serverID": 1, "serverPort": 8080},
                "resourceLimits": {"cpu": 0.1, "memory": 128},
                "rabbitMQCreds": {"defaultUser": "user", "defaultPassword": "password"},
                "networkInterface": "eth0",
                "restartPolicy": "always",
            },
        ),
        (
            PackageSpec,
            {
                "runtime": "cloud",
                "host_pid": True,
                "environment_vars": [
                    {
                        "name": "VAR",
                        "exposed_name": "VAR",
                        "value_from": {
                            "secret_key_ref": {"name": "secret", "key": "key"}
                        },
                    }
                ],
                "executables": [
                    {
                        "docker": {"image": "image:1", "image_pull_policy": "Always"},
                        "liveness_probe": {
                            "http_get": {
                                "path": "/health",
                                "port": 80,
                                "http_headers": [{"name": "header", "value": "value"}],
                            },
                            "tcp_socket": {"port": 80},
                            "initial_delay_seconds": 1,
                            "timeout_seconds": 10,
                            "period_seconds": 1,
                            "success_threshold": 1,
                            "failure_threshold": 1,
                        },
                    }
                ],
                "endpoints": [
                    {"name": "endpoint", "target_port": 80, "port_range": "80-90"}
                ],
                "ros": {"ros_endpoints": [{"type": "topic", "name": "topic"}]},
            },
            {
                "runtime": "cloud",
                "hostPID": True,
                "environmentVars": [
                    {
                        "name": "VAR",
                        "exposedName": "VAR",
                        "valueFrom": {"secretKeyRef": {"name": "secret", "key": "key"}},
                    }
                ],
                "executables": [
                    {
                        "docker": {"image": "image:1", "imagePullPolicy": "Always"},
                        "livenessProbe": {
                            "httpGet": {
                                "path": "/health",
                                "port": 80,
                                "httpHeaders": [{"name": "header", "value": "value"}],
                            },
                            "tcpSocket": {"port": 80},
                            "initialDelaySeconds": 1,
                            "timeoutSeconds": 10,
                            "periodSeconds": 1,
                            "successThreshold": 1,
                            "failureThreshold": 1,
                        },
                    }
                ],
                "endpoints": [
                    {"name": "endpoint", "targetPort": 80, "portRange": "80-90"}
                ],
                "ros": {"rosEndpoints": [{"type": "topic", "name": "topic"}]},
            },
        ),
        (DockerProxyConfig, {"data_directory": "/cache"}, {"dataDirectory": "/cache"}),
        (
            UserProject,
            {
                "name": "project",
                "organization_creator_guid": "owner",
                "organization_guid": "org",
                "role_names": [],
            },
            {
                "name": "project",
                "organizationCreator": "owner",
                "organizationGUID": "org",
                "roleNames": [],
            },
        ),
        (
            ConfigValue,
            {"content_type": "kv", "content_length": 5, "data": "dmFsdWU="},
            {"contentType": "kv", "contentLength": 5, "data": "dmFsdWU="},
        ),
        (
            DeploymentGraph,
            {
                "nodes": [{"name": "app", "type": "Deployment"}],
                "lines": [
                    {
                        "from_": {"name": "app", "type": "Deployment"},
                        "to": {"name": "disk", "type": "Disk"},
                        "text": "mount",
                        "type": "Disk",
                    }
                ],
            },
            {
                "Nodes": [{"Name": "app", "Type": "Deployment"}],
                "Lines": [
                    {
                        "From": {"Name": "app", "Type": "Deployment"},
                        "To": {"Name": "disk", "Type": "Disk"},
                        "Text": "mount",
                        "Type": "Disk",
                    }
                ],
            },
        ),
    ],
)
def test_python_names_and_api_aliases_round_trip(
    model: type[BaseModel], python_values: dict[str, Any], json_values: dict[str, Any]
) -> None:
    from_names = model(**python_values)
    from_json = model.model_validate(json_values)
    assert from_names == from_json
    assert from_json.model_dump(by_alias=True, exclude_unset=True) == json_values
    assert from_names.model_dump(by_alias=True, exclude_unset=True) == json_values


@pytest.mark.parametrize("alias", ["nameOrGUID", "nameOrGuid", "name_or_guid"])
def test_dependency_alias_choices(alias: str) -> None:
    dependency = Depends.model_validate({alias: "resource"})
    assert dependency.name_or_guid == "resource"
    assert dependency.model_dump(by_alias=True) == {"nameOrGUID": "resource"}


def test_metadata_datetime_validator_uses_python_field_names() -> None:
    metadata = BaseMetadata(
        name="resource", created_at=datetime(2026, 10, 9, tzinfo=UTC)
    )
    assert metadata.created_at == "2026-10-09T00:00:00+00:00"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_oauth_clients_preserve_snake_case_wire_fields(
    *, mode: str, client: Client, async_client: AsyncClient, mocker: MockFixture
) -> None:
    target = client if mode == "sync" else async_client
    payload = {
        "client_id": "client",
        "redirect_uris": ["https://app/callback"],
        "metadata": {"organizationGUID": "org"},
    }
    post = mocker.patch.object(
        target.c, "post", return_value=httpx.Response(201, json=payload)
    )
    response = target.create_oauth2_client(OAuth2Client(**payload))
    if inspect.isawaitable(response):
        response = await response
    assert isinstance(response, OAuth2Client)
    assert response.client_id == "client"
    assert post.call_args.kwargs["json"] == payload


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_oauth_uri_updates_preserve_acronym_aliases(
    *, mode: str, client: Client, async_client: AsyncClient, mocker: MockFixture
) -> None:
    target = client if mode == "sync" else async_client
    put = mocker.patch.object(
        target.c, "put", return_value=httpx.Response(200, json={"client_id": "client"})
    )
    response = target.update_oauth2_client_uris(
        "client",
        OAuth2UpdateURI(
            redirect_uris=["https://app/callback"], post_logout_redirect_uris=[]
        ),
    )
    if inspect.isawaitable(response):
        response = await response
    assert isinstance(response, OAuth2Client)
    assert put.call_args.kwargs["json"] == {
        "redirectURIs": ["https://app/callback"],
        "postLogoutRedirectURIs": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_config_value_map_has_no_root_wrapper(
    *, mode: str, client: Client, async_client: AsyncClient, mocker: MockFixture
) -> None:
    target = client if mode == "sync" else async_client
    put = mocker.patch.object(
        target.c, "put", return_value=httpx.Response(201, json={"success": True})
    )
    response = target.put_keys_in_revision(
        "tree",
        "revision",
        ConfigValues({"setting": ConfigValue(content_type="kv", data="dmFsdWU=")}),
    )
    if inspect.isawaitable(response):
        response = await response
    assert isinstance(response, APIResponse)
    assert put.call_args.kwargs["json"] == {
        "setting": {"contentType": "kv", "data": "dmFsdWU="}
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_key_upload_preserves_raw_content_and_rename_json(
    *, mode: str, client: Client, async_client: AsyncClient, mocker: MockFixture
) -> None:
    target = client if mode == "sync" else async_client
    content = b"\x00\xff\x80raw content"
    put = mocker.patch.object(
        target.c, "put", return_value=httpx.Response(201, json={"success": True})
    )
    response = target.put_key_in_revision(
        "tree", "revision", "key", ConfigKeyUpload(content)
    )
    if inspect.isawaitable(response):
        await response
    assert put.call_args.kwargs["content"] == content
    patch = mocker.patch.object(
        target.c, "patch", return_value=httpx.Response(200, json={"success": True})
    )
    response = target.rename_key_in_revision(
        "tree", "revision", "key", ConfigKeyRename(name="renamed")
    )
    if inspect.isawaitable(response):
        await response
    assert patch.call_args.kwargs["json"] == {"name": "renamed"}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_commit_revision_keeps_fields_flattened(
    *, mode: str, client: Client, async_client: AsyncClient, mocker: MockFixture
) -> None:
    target = client if mode == "sync" else async_client
    payload = {
        "author": "author",
        "message": "commit",
        "metadata": {"labels": {"release": "1"}},
    }
    patch = mocker.patch.object(
        target.c, "patch", return_value=httpx.Response(200, json=payload)
    )
    response = target.commit_revision("tree", "revision", ConfigTreeRevision(**payload))
    if inspect.isawaitable(response):
        response = await response
    assert isinstance(response, ConfigTreeRevision)
    assert response.author == "author"
    assert patch.call_args.kwargs["json"] == payload


def test_settings_source_consumes_config_value_models(mocker: MockFixture) -> None:
    mocker.patch.object(
        Client,
        "get_configtree",
        return_value=ConfigTree(
            metadata={"name": "tree"},
            keys={"setting": ConfigValue(data="Nw=="), "no-data": ConfigValue()},
        ),
    )
    source = ConfigTreeSource(TreeSettings, Configuration(), tree_name="tree")
    assert source() == {"setting": 7}


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (OAuth2ClientList, {"items": [{"client_id": "client"}]}),
        (
            DeploymentHistoryList,
            {
                "items": [
                    {
                        "metadata": {
                            "creatorGUID": "user",
                            "createdAt": "2026-10-09T00:00:00Z",
                            "updatedAt": "2026-10-09T01:00:00Z",
                            "generation": 2,
                        },
                        "status": {"status": "Running", "error_codes": []},
                    }
                ]
            },
        ),
        (
            AuthSubjectResponse,
            {"success": True, "data": {"guid": "user", "firstName": "User"}},
        ),
    ],
)
def test_new_response_models_parse_nested_structures(
    model: type[BaseModel], payload: dict[str, Any]
) -> None:
    response = model.model_validate(payload)
    assert response.model_dump(by_alias=True, exclude_unset=True) == payload


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_shared_url_datetime_serializes_through_aliases(
    *, mode: str, client: Client, async_client: AsyncClient, mocker: MockFixture
) -> None:
    target = client if mode == "sync" else async_client
    body = SharedURL(spec={"expiry_time": datetime(2026, 10, 10, tzinfo=UTC)})
    post = mocker.patch.object(
        target.c,
        "post",
        return_value=httpx.Response(
            201, json=body.model_dump(by_alias=True, mode="json")
        ),
    )
    response = target.create_sharedurl("upload", body)
    if inspect.isawaitable(response):
        await response
    assert post.call_args.kwargs["json"]["spec"]["expiryTime"] == "2026-10-10T00:00:00Z"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_invalid_bulk_response_is_not_returned_as_dict(
    *, mode: str, client: Client, async_client: AsyncClient, mocker: MockFixture
) -> None:
    target = client if mode == "sync" else async_client
    mocker.patch.object(
        target.c,
        "put",
        return_value=httpx.Response(200, json={"newBindings": "invalid"}),
    )
    with pytest.raises(ValidationError):
        await _call(target.update_role_binding, BulkRoleBindingUpdate())


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_key_download_handles_errors_before_yaml_decoding(
    *, mode: str, client: Client, async_client: AsyncClient, mocker: MockFixture
) -> None:
    target = client if mode == "sync" else async_client
    mocker.patch.object(
        target.c, "get", return_value=httpx.Response(200, text="[true, 7, value]")
    )
    response = target.get_key_in_revision("tree", "revision", "key")
    if inspect.isawaitable(response):
        response = await response
    assert isinstance(response, ConfigKeyContent)
    assert response.root == [True, 7, "value"]

    mocker.patch.object(
        target.c, "get", return_value=httpx.Response(404, json={"error": "missing key"})
    )
    with pytest.raises(HttpNotFoundError, match="missing key"):
        await _call(target.get_key_in_revision, "tree", "revision", "key")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize(
    "case",
    [
        (b"2026-10-09", "application/yaml", date(2026, 10, 9)),
        (
            b"2026-10-09T12:34:56Z",
            "application/yaml",
            datetime(2026, 10, 9, 12, 34, 56, tzinfo=UTC),
        ),
        (b"!!binary AP+A", "application/yaml", b"\x00\xff\x80"),
        (b"1: value", "application/yaml", {1: "value"}),
        (b"!!set {one: null, two: null}", "application/yaml", {"one", "two"}),
        (
            b"date: 2026-10-09\ndata: !!binary AP+A\n1: [true, null]",
            "application/yaml",
            {"date": date(2026, 10, 9), "data": b"\x00\xff\x80", 1: [True, None]},
        ),
        (b'{"setting": 7}', "application/json", {"setting": 7}),
        (b'{"setting": 7}', "application/vnd.settings+json", {"setting": 7}),
        (b"2026-10-09", "application/vnd.yaml", date(2026, 10, 9)),
        (b"2026-10-09", "application/vnd.settings+yaml", date(2026, 10, 9)),
        (b"caf\xe9", "text/plain; charset=iso-8859-1", "café"),
        (b"true", "text/plain; charset=utf-8", True),
        (b"", "text/plain", None),
        (b"\x00\xff\x80", "application/octet-stream", b"\x00\xff\x80"),
        (b"true", "application/octet-stream", b"true"),
        (b"%PDF-1.7", "application/pdf", b"%PDF-1.7"),
        (b"\x00\xff\x80", "", b"\x00\xff\x80"),
        (b"\xff\x80", "", b"\xff\x80"),
        (b"a\x00b", "", b"a\x00b"),
        (b"2026-10-09", "", date(2026, 10, 9)),
    ],
)
async def test_key_download_preserves_yaml_types_and_binary_content(
    *,
    mode: str,
    case: tuple[bytes, str, object],
    client: Client,
    async_client: AsyncClient,
    mocker: MockFixture,
) -> None:
    target = client if mode == "sync" else async_client
    content, content_type, expected = case
    headers = {"Content-Type": content_type} if content_type else {}
    mocker.patch.object(
        target.c,
        "get",
        return_value=httpx.Response(200, content=content, headers=headers),
    )
    response = await _call(target.get_key_in_revision, "tree", "revision", "key")
    assert isinstance(response, ConfigKeyContent)
    assert type(response.root) is type(expected)
    assert response.root == expected
    assert response.model_dump() == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize(
    "case",
    [
        (
            "get_deployment_graph",
            {"name": "app"},
            DeploymentGraph,
            {"Nodes": [{"Name": "app", "Type": "Deployment"}], "Lines": []},
        ),
        (
            "get_deployment_history",
            {"name": "app"},
            DeploymentHistoryList,
            {
                "items": [
                    {
                        "metadata": {
                            "creatorGUID": "user",
                            "createdAt": "2026-10-09T00:00:00Z",
                            "updatedAt": "2026-10-09T01:00:00Z",
                            "generation": 2,
                        },
                        "status": {"status": "Running"},
                    }
                ]
            },
        ),
        (
            "list_oauth2_clients",
            {},
            OAuth2ClientList,
            {"items": [{"client_id": "client"}]},
        ),
        (
            "get_oauth2_client",
            {"client_id": "client"},
            OAuth2Client,
            {"client_id": "client"},
        ),
        (
            "get_subject",
            {"auth_token": "token"},
            AuthSubjectResponse,
            {"success": True, "data": {"guid": "user", "firstName": "User"}},
        ),
    ],
)
async def test_json_endpoints_return_the_annotated_models(
    *,
    mode: str,
    case: tuple[str, dict[str, str], type[BaseModel], dict[str, Any]],
    client: Client,
    async_client: AsyncClient,
    mocker: MockFixture,
) -> None:
    target = client if mode == "sync" else async_client
    name, arguments, model, payload = case
    http_client = target.c
    if name == "get_subject" and mode == "async":
        http_client = async_client.sync_client
    mocker.patch.object(
        http_client, "get", return_value=httpx.Response(200, json=payload)
    )
    response = await _call(getattr(target, name), **arguments)
    assert isinstance(response, model)
    assert response.model_dump(by_alias=True, exclude_unset=True) == payload


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_add_user_serializes_json_and_returns_user(
    *, mode: str, client: Client, async_client: AsyncClient, mocker: MockFixture
) -> None:
    target = client if mode == "sync" else async_client
    payload = {
        "metadata": {"name": "user"},
        "spec": {"emailID": "user@example.com"},
    }
    user = models.User.model_validate(payload)
    post = mocker.patch.object(
        target.c, "post", return_value=httpx.Response(200, json=payload)
    )
    response = await _call(target.add_user, user)
    assert isinstance(response, models.User)
    assert response.spec.email_id == "user@example.com"
    assert post.call_args.kwargs["json"]["spec"]["emailID"] == "user@example.com"
    assert "body" not in post.call_args.kwargs
