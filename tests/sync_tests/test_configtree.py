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

from rapyuta_io_sdk_v2.exceptions import (
    BadGatewayError,
    ServiceUnavailableError,
)
from rapyuta_io_sdk_v2.models import (
    ConfigKeyRename,
    ConfigKeyUpload,
    ConfigTree,
    ConfigTreeRevision,
    ConfigValue,
    ConfigValues,
)

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import Client


def test_list_configtrees_success(*, client: Client, mocker: MockFixture) -> None:
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [
                {
                    "metadata": {
                        "name": "test-configtree",
                        "guid": "mock_configtree_guid",
                    }
                }
            ],
        },
    )
    response = client.list_configtrees()
    assert response.items[0].metadata.name == "test-configtree"
    assert response.items[0].metadata.guid == "mock_configtree_guid"


def test_list_configtrees_bad_gateway(*, client: Client, mocker: MockFixture) -> None:
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=502,
        json={"error": "bad gateway"},
    )
    with pytest.raises(BadGatewayError) as exc:
        client.list_configtrees()
    assert str(exc.value) == "bad gateway"


def test_create_configtree_success(
    *, client: Client, mocker: MockFixture, configtree_body: dict[str, Any]
) -> None:
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_configtree_guid", "name": "test_configtree"},
        },
    )
    response = client.create_configtree(ConfigTree.model_validate(configtree_body))
    assert response.metadata.guid == "test_configtree_guid"


def test_create_configtree_service_unavailable(
    *, client: Client, mocker: MockFixture, configtree_body: dict[str, Any]
) -> None:
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=503,
        json={"error": "service unavailable"},
    )
    with pytest.raises(ServiceUnavailableError) as exc:
        client.create_configtree(ConfigTree.model_validate(configtree_body))
    assert str(exc.value) == "service unavailable"


def test_get_configtree_success(*, client: Client, mocker: MockFixture) -> None:
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_configtree_guid", "name": "test_configtree"},
        },
    )
    response = client.get_configtree(name="mock_configtree_name")
    assert response.metadata.guid == "test_configtree_guid"
    assert response.metadata.name == "test_configtree"


def test_set_configtree_revision_success(
    *, client: Client, mocker: MockFixture, configtree_body: dict[str, Any]
) -> None:
    mock_put = mocker.patch("httpx.Client.put")
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_configtree_guid", "name": "test_configtree"},
        },
    )
    response = client.set_configtree_revision(
        name="mock_configtree_name",
        configtree=ConfigTree.model_validate(configtree_body),
    )
    assert response.metadata.guid == "test_configtree_guid"
    assert response.metadata.name == "test_configtree"


def test_update_configtree_success(
    *, client: Client, mocker: MockFixture, configtree_body: dict[str, Any]
) -> None:
    mock_put = mocker.patch("httpx.Client.put")
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_configtree_guid", "name": "test_configtree"},
        },
    )
    response = client.update_configtree(
        name="mock_configtree_name", body=ConfigTree.model_validate(configtree_body)
    )
    assert response.metadata.guid == "test_configtree_guid"
    assert response.metadata.name == "test_configtree"


def test_delete_configtree_success(*, client: Client, mocker: MockFixture) -> None:
    mock_delete = mocker.patch("httpx.Client.delete")
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )
    response = client.delete_configtree(name="mock_configtree_name")
    assert response is None


def test_list_revisions_success(*, client: Client, mocker: MockFixture) -> None:
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [
                {
                    "metadata": {
                        "name": "test-configtree",
                        "guid": "mock_configtree_guid",
                    }
                }
            ],
        },
    )
    response = client.list_revisions(tree_name="mock_configtree_name")
    assert response.items[0].metadata.name == "test-configtree"
    assert response.items[0].metadata.guid == "mock_configtree_guid"


def test_create_revision_success(
    *, client: Client, mocker: MockFixture, configtree_body: dict[str, Any]
) -> None:
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_revision_guid", "name": "test_revision"},
        },
    )
    response = client.create_revision(
        name="mock_configtree_name",
        body=ConfigTreeRevision.model_validate(configtree_body),
    )
    assert response.metadata.guid == "test_revision_guid"


def test_put_keys_in_revision_success(*, client: Client, mocker: MockFixture) -> None:
    mock_put = mocker.patch("httpx.Client.put")
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={"success": True},
    )
    response = client.put_keys_in_revision(
        name="mock_configtree_name",
        revision_id="mock_revision_id",
        config_values=ConfigValues({"mock_key": ConfigValue(data="dmFsdWU=")}),
    )
    assert response.success is True
    assert response.success is True


def test_commit_revision_success(*, client: Client, mocker: MockFixture) -> None:
    mock_patch = mocker.patch("httpx.Client.patch")
    mock_patch.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_revision_guid", "name": "test_revision"},
        },
    )
    response = client.commit_revision(
        tree_name="mock_configtree_name",
        revision_id="mock_revision_id",
        body=ConfigTreeRevision(),
    )
    assert response.metadata.guid == "test_revision_guid"
    assert response.metadata.name == "test_revision"


def test_commit_revision_with_labels(*, client: Client, mocker: MockFixture) -> None:
    mock_patch = mocker.patch("httpx.Client.patch")
    mock_patch.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {
                "guid": "test_revision_guid",
                "name": "test_revision",
                "labels": {"rapyuta.io/milestone": "v1.0"},
            },
        },
    )
    response = client.commit_revision(
        tree_name="mock_configtree_name",
        revision_id="mock_revision_id",
        body=ConfigTreeRevision(metadata={"labels": {"rapyuta.io/milestone": "v1.0"}}),
    )
    assert response.metadata.guid == "test_revision_guid"
    assert response.metadata.labels["rapyuta.io/milestone"] == "v1.0"

    # Verify the request body included metadata.labels
    call_kwargs = mock_patch.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["metadata"]["labels"] == {"rapyuta.io/milestone": "v1.0"}


def test_get_key_in_revision_str(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        text="test_value",
    )

    # Call the get_key_in_revision method
    response = client.get_key_in_revision(
        tree_name="mock_configtree_name", revision_id="mock_revision_id", key="mock_key"
    )

    # Validate the response
    assert isinstance(response.root, str)
    assert response.root == "test_value"


def test_get_key_in_revision_int(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.get method
    expected_value = 1500
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        text="1500",
    )

    # Call the get_key_in_revision method
    response = client.get_key_in_revision(
        tree_name="mock_configtree_name", revision_id="mock_revision_id", key="mock_key"
    )

    # Validate the response
    assert isinstance(response.root, int)
    assert response.root == expected_value


def test_get_key_in_revision_bool(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        text="true",
    )
    response = client.get_key_in_revision(
        tree_name="mock_configtree_name", revision_id="mock_revision_id", key="mock_key"
    )

    # Validate the response
    assert isinstance(response.root, bool)
    assert response.root


def test_put_key_in_revision_success(*, client: Client, mocker: MockFixture) -> None:
    mock_put = mocker.patch("httpx.Client.put")
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={"success": True},
    )
    response = client.put_key_in_revision(
        tree_name="mock_configtree_name",
        revision_id="mock_revision_id",
        key="mock_key",
        body=ConfigKeyUpload("value"),
    )
    assert response.success is True
    assert response.success is True


def test_delete_key_in_revision_success(*, client: Client, mocker: MockFixture) -> None:
    mock_delete = mocker.patch("httpx.Client.delete")
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )
    response = client.delete_key_in_revision(
        tree_name="mock_configtree_name", revision_id="mock_revision_id", key="mock_key"
    )
    assert response is None


def test_rename_key_in_revision_success(*, client: Client, mocker: MockFixture) -> None:
    mock_patch = mocker.patch("httpx.Client.patch")
    mock_patch.return_value = httpx.Response(
        status_code=200,
        json={"success": True},
    )
    response = client.rename_key_in_revision(
        tree_name="mock_configtree_name",
        revision_id="mock_revision_id",
        key="mock_key",
        config_key_rename=ConfigKeyRename(name="test_key"),
    )
    assert response.success is True
    assert response.success is True
