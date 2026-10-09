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

from typing import TYPE_CHECKING, Any

import httpx
import pytest

from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError, UnauthorizedAccessError
from rapyuta_io_sdk_v2.models import Package, PackageList
from rapyuta_io_sdk_v2.models.package import EnvironmentSpec

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import AsyncClient


@pytest.mark.asyncio
async def test_list_packages_success(
    *,
    async_client: AsyncClient,
    packagelist_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=packagelist_model_mock,
    )

    response = await async_client.list_packages()

    assert isinstance(response, PackageList)
    assert len(response.items) == len(packagelist_model_mock["items"])
    assert response.items[0].metadata.name == "gostproxy"
    assert response.items[1].metadata.name == "database"


@pytest.mark.asyncio
async def test_get_cloud_package_success(
    *,
    async_client: AsyncClient,
    cloud_package_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=cloud_package_model_mock,
    )
    response = await async_client.get_package(name="gostproxy")
    assert isinstance(response, Package)
    assert response.metadata.name == "gostproxy"


@pytest.mark.asyncio
async def test_get_device_package_success(
    *,
    async_client: AsyncClient,
    device_package_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=device_package_model_mock,
    )
    response = await async_client.get_package(name="database")
    assert isinstance(response, Package)
    assert response.metadata.name == "database"


@pytest.mark.asyncio
async def test_get_package_not_found(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "package not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        await async_client.get_package(name="notfound")

    assert str(exc.value) == "package not found"


@pytest.mark.asyncio
async def test_create_package_unauthorized(
    *, async_client: AsyncClient, package_body: dict[str, Any], mocker: MockFixture
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        await async_client.create_package(body=package_body)

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_delete_package_success(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = await async_client.delete_package(name="gostproxy", version="v1.0.0")

    assert response is None


# ── New: valueFrom / SecretKeyRef ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_package_with_valuefrom_success(
    *,
    async_client: AsyncClient,
    package_with_valuefrom_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    """GET a package whose env vars are sourced from Secret key refs."""
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=package_with_valuefrom_mock,
    )

    response = await async_client.get_package(name="secret-injected-app")

    assert isinstance(response, Package)
    assert response.metadata.guid == "pkg-cccccccccccccccccccc"

    api_key_var = next(v for v in response.spec.environmentVars if v.name == "API_KEY")
    assert api_key_var.valueFrom is not None
    assert api_key_var.valueFrom.secret_key_ref.name == "my-api-secret"
    assert api_key_var.valueFrom.secret_key_ref.key == "API_KEY"
    assert api_key_var.valueFrom.secret_key_ref.value == "resolved-api-key"


@pytest.mark.asyncio
async def test_create_package_with_valuefrom_success(
    *,
    async_client: AsyncClient,
    package_with_valuefrom_body: dict[str, Any],
    package_with_valuefrom_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    """POST a package with valueFrom env vars and verify the response is parsed."""
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=package_with_valuefrom_mock,
    )

    response = await async_client.create_package(body=package_with_valuefrom_body)

    assert isinstance(response, Package)
    api_key_var = next(v for v in response.spec.environmentVars if v.name == "API_KEY")
    assert api_key_var.valueFrom.secret_key_ref.key == "API_KEY"


# ── New: EnvironmentSpec model validation ────────────────────────────────────


def test_environment_spec_valuefrom_model_validation() -> None:
    """EnvironmentSpec correctly parses a valueFrom.secretKeyRef payload."""
    env = EnvironmentSpec.model_validate(
        {
            "name": "MY_SECRET_VAR",
            "valueFrom": {
                "secretKeyRef": {
                    "name": "my-secret",
                    "key": "MY_KEY",
                }
            },
        }
    )
    assert env.valueFrom.secret_key_ref.name == "my-secret"
    assert env.valueFrom.secret_key_ref.key == "MY_KEY"
    assert env.valueFrom.secret_key_ref.value is None
