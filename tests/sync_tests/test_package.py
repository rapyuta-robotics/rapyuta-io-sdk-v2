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

from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError
from rapyuta_io_sdk_v2.models import Package, PackageList
from rapyuta_io_sdk_v2.models.package import EnvironmentSpec

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import Client


def test_list_packages_success(
    *, client: Client, packagelist_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=packagelist_model_mock,
    )

    # Call the list_packages method
    response = client.list_packages()

    # Validate the response
    assert isinstance(response, PackageList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == len(packagelist_model_mock["items"])
    cloud_pkg = response.items[0]
    device_pkg = response.items[1]
    assert cloud_pkg.metadata.guid == "pkg-aaaaaaaaaaaaaaaaaaaa"
    assert cloud_pkg.metadata.name == "gostproxy"
    assert cloud_pkg.kind == "Package"
    assert cloud_pkg.spec.runtime == "cloud"
    assert device_pkg.metadata.guid == "pkg-bbbbbbbbbbbbbbbbbbbb"
    assert device_pkg.metadata.name == "database"
    assert device_pkg.kind == "Package"
    assert device_pkg.spec.runtime == "device"


def test_list_packages_not_found(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    # Call the list_packages method
    with pytest.raises(HttpNotFoundError) as exc:
        client.list_packages()

    # Validate the exception message
    assert str(exc.value) == "not found"


def test_get_cloud_package_success(
    *, client: Client, cloud_package_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=cloud_package_model_mock,
    )

    # Call the get_package method
    response = client.get_package(name="gostproxy")

    # Validate the response
    assert isinstance(response, Package)
    assert response.metadata.guid == "pkg-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "gostproxy"
    assert response.spec.runtime == "cloud"


def test_get_device_package_success(
    *, client: Client, device_package_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=device_package_model_mock,
    )

    # Call the get_package method
    response = client.get_package(name="database")

    # Validate the response
    assert isinstance(response, Package)
    assert response.metadata.guid == "pkg-bbbbbbbbbbbbbbbbbbbb"
    assert response.metadata.name == "database"
    assert response.spec.runtime == "device"


def test_get_package_not_found(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    # Call the get_package method
    with pytest.raises(HttpNotFoundError) as exc:
        client.get_package(name="mock_package_name")

    # Validate the exception message
    assert str(exc.value) == "not found"


def test_create_package_success(
    *,
    client: Client,
    package_body: dict[str, Any],
    cloud_package_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=cloud_package_model_mock,
    )

    # Call the create_package method
    response = client.create_package(body=package_body)

    # Validate the response
    assert isinstance(response, Package)
    assert response.metadata.guid == "pkg-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "gostproxy"


def test_delete_package_success(*, client: Client, mocker: MockFixture) -> None:
    mock_delete = mocker.patch("httpx.Client.delete")
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )
    response = client.delete_package(name="gostproxy", version="v1.0.0")
    assert response is None


def test_delete_package_not_found(*, client: Client, mocker: MockFixture) -> None:
    mock_delete = mocker.patch("httpx.Client.delete")
    mock_delete.return_value = httpx.Response(
        status_code=404,
        json={"error": "package not found"},
    )
    with pytest.raises(HttpNotFoundError) as exc:
        client.delete_package(name="notfound", version="v1.0.0")
    assert str(exc.value) == "package not found"


# ── New: valueFrom / SecretKeyRef ────────────────────────────────────────────


def test_get_package_with_valuefrom_success(
    *, client: Client, package_with_valuefrom_mock: dict[str, Any], mocker: MockFixture
) -> None:
    """GET a package whose env vars are sourced from Secret key refs."""
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=package_with_valuefrom_mock,
    )

    response = client.get_package(name="secret-injected-app")

    assert isinstance(response, Package)
    assert response.metadata.guid == "pkg-cccccccccccccccccccc"

    env_vars = response.spec.environmentVars
    assert env_vars is not None

    plain = next(v for v in env_vars if v.name == "PLAIN_VAR")
    assert plain.default == "plain-value"
    assert plain.valueFrom is None

    api_key_var = next(v for v in env_vars if v.name == "API_KEY")
    assert api_key_var.valueFrom is not None
    assert api_key_var.valueFrom.secret_key_ref is not None
    assert api_key_var.valueFrom.secret_key_ref.name == "my-api-secret"
    assert api_key_var.valueFrom.secret_key_ref.key == "API_KEY"
    # server resolves the value and returns it
    assert api_key_var.valueFrom.secret_key_ref.value == "resolved-api-key"

    db_pass_var = next(v for v in env_vars if v.name == "DB_PASS")
    assert db_pass_var.exposed is True
    assert db_pass_var.exposedName == "DB_PASS"
    assert db_pass_var.valueFrom.secret_key_ref.name == "db-credentials"


def test_create_package_with_valuefrom_success(
    *,
    client: Client,
    package_with_valuefrom_body: dict[str, Any],
    package_with_valuefrom_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    """POST a package with valueFrom env vars and verify the response is parsed."""
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=package_with_valuefrom_mock,
    )

    response = client.create_package(body=package_with_valuefrom_body)

    assert isinstance(response, Package)
    assert response.metadata.name == "secret-injected-app"
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
    assert env.name == "MY_SECRET_VAR"
    assert env.valueFrom is not None
    assert env.valueFrom.secret_key_ref.name == "my-secret"
    assert env.valueFrom.secret_key_ref.key == "MY_KEY"
    assert env.valueFrom.secret_key_ref.value is None


def test_environment_spec_plain_and_valuefrom_coexist() -> None:
    """Parse environment variables with both a default and a secret reference."""
    env = EnvironmentSpec.model_validate(
        {
            "name": "OVERRIDE_VAR",
            "default": "fallback",
            "valueFrom": {
                "secretKeyRef": {
                    "name": "override-secret",
                    "key": "override-key",
                    "value": "injected",
                }
            },
        }
    )
    assert env.default == "fallback"
    assert env.valueFrom.secret_key_ref.value == "injected"
