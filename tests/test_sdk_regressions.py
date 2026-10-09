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

import json
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from pydantic import ValidationError as PydanticValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from rapyuta_io_sdk_v2 import AsyncClient, Client, Configuration, exceptions
from rapyuta_io_sdk_v2.models import Deployment, Package, ServiceAccount
from rapyuta_io_sdk_v2.models.usergroup import UserGroupCreate
from rapyuta_io_sdk_v2.pydantic_source import ConfigTreeSource
from rapyuta_io_sdk_v2.utils import handle_server_errors

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockFixture


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (httpx.codes.BAD_REQUEST, exceptions.MethodNotAllowedError),
        (httpx.codes.FORBIDDEN, exceptions.MethodNotAllowedError),
        (httpx.codes.NOT_FOUND, exceptions.HttpNotFoundError),
        (httpx.codes.METHOD_NOT_ALLOWED, exceptions.MethodNotAllowedError),
        (httpx.codes.CONFLICT, exceptions.HttpAlreadyExistsError),
        (httpx.codes.INTERNAL_SERVER_ERROR, exceptions.InternalServerError),
        (httpx.codes.NOT_IMPLEMENTED, exceptions.NotImplementedError),
        (httpx.codes.BAD_GATEWAY, exceptions.BadGatewayError),
        (httpx.codes.SERVICE_UNAVAILABLE, exceptions.ServiceUnavailableError),
        (httpx.codes.GATEWAY_TIMEOUT, exceptions.GatewayTimeoutError),
        (httpx.codes.UNAUTHORIZED, exceptions.UnauthorizedAccessError),
        (httpx.codes.IM_A_TEAPOT, exceptions.UnknownError),
    ],
)
def test_http_error_mapping(*, status: int, error_type: type[Exception]) -> None:
    response = httpx.Response(status, json={"error": "server rejected the request"})
    with pytest.raises(error_type, match=r"^server rejected the request$"):
        handle_server_errors(response)


@pytest.mark.parametrize("body", [{}, {"error": None}, {"error": ""}])
def test_http_error_fallback(*, body: dict[str, str | None]) -> None:
    response = httpx.Response(httpx.codes.NOT_FOUND, json=body)
    with pytest.raises(exceptions.HttpNotFoundError) as error:
        handle_server_errors(response)
    assert str(error.value) == (
        f"HttpNotFoundError (status_code={httpx.codes.NOT_FOUND})"
    )


def test_plain_text_http_error() -> None:
    response = httpx.Response(httpx.codes.BAD_GATEWAY, text="upstream unavailable")
    with pytest.raises(exceptions.BadGatewayError, match=r"^upstream unavailable$"):
        handle_server_errors(response)


def test_success_does_not_parse_response_body() -> None:
    response = httpx.Response(httpx.codes.NO_CONTENT)
    handle_server_errors(response)


@pytest.mark.parametrize(
    ("model", "payload", "expected"),
    [
        (
            Deployment,
            {
                "metadata": {
                    "name": "app",
                    "depends": {"nameOrGUID": "pkg", "version": "1"},
                },
                "spec": {
                    "runtime": "cloud",
                    "volumes": [{"depends": {"nameOrGUID": "disk"}}],
                    "staticRoutes": [{"depends": {"nameOrGUID": "route"}}],
                    "depends": [{"nameOrGUID": "prerequisite"}],
                    "rosNetworks": [{"depends": {"nameOrGUID": "network"}}],
                },
            },
            [
                "package:pkg",
                "disk:disk",
                "staticroute:route",
                "deployment:prerequisite",
                "network:network",
            ],
        ),
        (
            Deployment,
            {
                "metadata": {"name": "app"},
                "spec": {
                    "runtime": "device",
                    "device": {"depends": {"nameOrGUID": "robot"}},
                    "volumes": [{"depends": {"nameOrGUID": "local-disk"}}],
                },
            },
            ["device:robot"],
        ),
        (
            UserGroupCreate,
            {
                "metadata": {"name": "operators"},
                "spec": {
                    "members": [
                        {
                            "subject": {"kind": "User", "name": "operator"},
                            "roleNames": ["viewer", "viewer"],
                        },
                        {"subject": {"kind": "User", "guid": "user-guid"}},
                    ],
                    "roles": [
                        {
                            "domain": {"kind": "Project", "name": "project"},
                            "roleName": "member",
                        },
                    ],
                },
            },
            [
                "user:operator",
                "role:viewer",
                "role:viewer",
                "project:project",
                "role:member",
            ],
        ),
        (ServiceAccount, {"metadata": {"name": "service"}}, []),
        (
            ServiceAccount,
            {
                "metadata": {"name": "service"},
                "spec": {
                    "roles": [
                        {
                            "domain": {"kind": "Project", "guid": "project-guid"},
                            "roleNames": ["reader"],
                        },
                    ]
                },
            },
            ["role:reader"],
        ),
        (
            Package,
            {
                "metadata": {"name": "pkg", "version": "1"},
                "spec": {
                    "runtime": "cloud",
                    "executables": [
                        {
                            "docker": {
                                "image": "app:1",
                                "pullSecret": {"depends": {"nameOrGUID": "registry"}},
                            }
                        },
                        {
                            "docker": {
                                "image": "worker:1",
                                "pullSecret": {"depends": {"nameOrGUID": "registry"}},
                            }
                        },
                    ],
                },
            },
            ["secret:registry", "secret:registry"],
        ),
        (
            Package,
            {"metadata": {"name": "pkg", "version": "1"}, "spec": {"runtime": "cloud"}},
            None,
        ),
    ],
)
def test_dependency_order_and_empty_results(
    *,
    model: type[Deployment | Package | ServiceAccount | UserGroupCreate],
    payload: dict[str, Any],
    expected: list[str] | None,
) -> None:
    resource = model.model_validate(payload)
    assert resource.list_dependencies() == expected


@pytest.mark.parametrize("field", ["uid", "gid", "perm"])
@pytest.mark.parametrize("value", [0, 1])
def test_cloud_volume_rejects_device_fields(*, field: str, value: int) -> None:
    payload = {
        "metadata": {"name": "app"},
        "spec": {"runtime": "cloud", "volumes": [{field: value}]},
    }
    with pytest.raises(PydanticValidationError, match="device-specific volume fields"):
        Deployment.model_validate(payload)


@pytest.mark.parametrize(
    ("filter_name", "query_name"),
    [
        ("label_selector", "labelSelector"),
        ("role_names", "roleNames"),
        ("subject_guids", "subjectGUIDS"),
        ("subject_names", "subjectNames"),
        ("subject_kinds", "subjectKinds"),
        ("domain_guids", "domainGUIDS"),
        ("domain_names", "domainNames"),
        ("domain_kinds", "domainKinds"),
        ("guids", "guids"),
    ],
)
def test_role_binding_filter_names(
    *,
    client: Client,
    mocker: MockFixture,
    filter_name: str,
    query_name: str,
) -> None:
    request = mocker.patch("httpx.Client.get")
    request.return_value = httpx.Response(httpx.codes.OK, json={"items": []})
    client.list_role_bindings(**{filter_name: ["selected"]})
    assert request.call_args.kwargs["params"][query_name] == ["selected"]


def test_role_binding_empty_filters_are_omitted(
    *,
    client: Client,
    mocker: MockFixture,
) -> None:
    request = mocker.patch("httpx.Client.get")
    request.return_value = httpx.Response(httpx.codes.OK, json={"items": []})
    client.list_role_bindings(role_names=[], label_selector=[])
    assert set(request.call_args.kwargs["params"]) == {"continue", "limit"}


@pytest.mark.asyncio
async def test_async_role_binding_filters(
    *,
    async_client: AsyncClient,
    mocker: MockFixture,
) -> None:
    request = mocker.patch("httpx.AsyncClient.get")
    request.return_value = httpx.Response(httpx.codes.OK, json={"items": []})
    await async_client.list_role_bindings(subject_guids=["subject"], domain_names=[])
    assert request.call_args.kwargs["params"]["subjectGUIDS"] == ["subject"]
    assert "domainNames" not in request.call_args.kwargs["params"]


def test_bulk_binding_response_fallback(*, client: Client, mocker: MockFixture) -> None:
    request = mocker.patch("httpx.Client.put")
    request.return_value = httpx.Response(httpx.codes.OK, json={"updated": True})
    response = client.update_role_binding({"newBindings": [], "oldBindings": []})
    assert response == {"updated": True}


def test_unexpected_binding_error_propagates(
    *,
    client: Client,
    mocker: MockFixture,
) -> None:
    request = mocker.patch("httpx.Client.put")
    request.return_value = httpx.Response(httpx.codes.OK, json={"updated": True})
    mocker.patch(
        "rapyuta_io_sdk_v2.client.RoleBinding",
        side_effect=RuntimeError("unexpected model error"),
    )
    with pytest.raises(RuntimeError, match=r"^unexpected model error$"):
        client.update_role_binding({"newBindings": [], "oldBindings": []})


class TreeSettings(BaseSettings):
    """Accept the complete configuration tree for settings source verification."""

    model_config = SettingsConfigDict(extra="allow")


@pytest.mark.parametrize("file_format", ["json", "yaml"])
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"value": "setting", "metadata": {}}, "setting"),
        (
            {"value": "setting", "metadata": None},
            {"value": "setting", "metadata": None},
        ),
        (
            {"value": "setting", "metadata": {"revision": "1"}, "other": "retained"},
            {"value": "setting", "metadata": {"revision": "1"}, "other": "retained"},
        ),
    ],
)
def test_metadata_wrappers(
    *,
    tmp_path: Path,
    value: dict[str, Any],
    expected: object,
    file_format: str,
) -> None:
    # JSON content is valid YAML, so exercise both decoders with the same payload.
    path = tmp_path / f"settings.{file_format}"
    path.write_text(json.dumps({"entry": value}), encoding="utf-8")
    source = ConfigTreeSource(TreeSettings, Configuration(), local_file=str(path))
    assert source()["settings"]["entry"] == expected


@pytest.mark.asyncio
async def test_async_bulk_binding_response_fallback(
    *,
    async_client: AsyncClient,
    mocker: MockFixture,
) -> None:
    request = mocker.patch("httpx.AsyncClient.put")
    request.return_value = httpx.Response(httpx.codes.OK, json={"updated": True})
    response = await async_client.update_role_binding(
        {"newBindings": [], "oldBindings": []}
    )
    assert response == {"updated": True}


@pytest.mark.asyncio
async def test_async_unexpected_binding_error_propagates(
    *,
    async_client: AsyncClient,
    mocker: MockFixture,
) -> None:
    request = mocker.patch("httpx.AsyncClient.put")
    request.return_value = httpx.Response(httpx.codes.OK, json={"updated": True})
    mocker.patch(
        "rapyuta_io_sdk_v2.async_client.RoleBinding",
        side_effect=RuntimeError("unexpected model error"),
    )
    with pytest.raises(RuntimeError, match=r"^unexpected model error$"):
        await async_client.update_role_binding({"newBindings": [], "oldBindings": []})
