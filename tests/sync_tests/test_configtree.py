import httpx
import pytest
from munch import Munch
from pytest_mock import MockFixture

from tests.data.mock_data import configtree_body  # noqa: F401
from tests.utils.fixtures import client  # noqa: F401


def test_list_configtrees_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-configtree", "guid": "mock_configtree_guid"}],
        },
    )

    # Call the list_configtrees method
    response = client.list_configtrees()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [
        {"name": "test-configtree", "guid": "mock_configtree_guid"}
    ]


def test_list_configtrees_bad_gateway(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=502,
        json={"error": "bad gateway"},
    )

    # Call the list_configtrees method
    with pytest.raises(Exception) as exc:
        client.list_configtrees()

    assert str(exc.value) == "bad gateway"


def test_create_configtree_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_configtree_guid", "name": "test_configtree"},
        },
    )

    # Call the create_configtree method
    response = client.create_configtree(configtree_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "test_configtree_guid"


def test_create_configtree_service_unavailable(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=503,
        json={"error": "service unavailable"},
    )

    # Call the create_configtree method
    with pytest.raises(Exception) as exc:
        client.create_configtree(configtree_body)

    assert str(exc.value) == "service unavailable"


def test_get_configtree_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_configtree_guid", "name": "test_configtree"},
        },
    )

    # Call the get_configtree method
    response = client.get_configtree(name="mock_configtree_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_configtree_guid"
    assert response.metadata.name == "test_configtree"


def test_set_configtree_revision_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_configtree_guid", "name": "test_configtree"},
        },
    )

    # Call the set_configtree_revision method
    response = client.set_configtree_revision(
        name="mock_configtree_name", configtree=configtree_body
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_configtree_guid"
    assert response.metadata.name == "test_configtree"


def test_update_configtree_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_configtree_guid", "name": "test_configtree"},
        },
    )

    # Call the update_configtree method
    response = client.update_configtree(name="mock_configtree_name", body=configtree_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_configtree_guid"
    assert response.metadata.name == "test_configtree"


def test_delete_configtree_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_configtree method
    response = client.delete_configtree(name="mock_configtree_name")

    # Validate the response
    assert response["success"] is True


def test_list_revisions_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-configtree", "guid": "mock_configtree_guid"}],
        },
    )

    # Call the list_revisions method
    response = client.list_revisions(tree_name="mock_configtree_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [
        {"name": "test-configtree", "guid": "mock_configtree_guid"}
    ]


def test_create_revision_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_revision_guid", "name": "test_revision"},
        },
    )

    # Call the create_revision method
    response = client.create_revision(name="mock_configtree_name", body=configtree_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "test_revision_guid"


def test_put_keys_in_revision_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_revision_guid", "name": "test_revision"},
        },
    )

    # Call the put_keys_in_revision method
    response = client.put_keys_in_revision(
        name="mock_configtree_name",
        revision_id="mock_revision_id",
        config_values=["mock_value1", "mock_value2"],
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_revision_guid"
    assert response.metadata.name == "test_revision"


def test_commit_revision_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.put method
    mock_patch = mocker.patch("httpx.Client.patch")

    # Set up the mock response
    mock_patch.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_revision_guid", "name": "test_revision"},
        },
    )

    # Call the commit_revision method
    response = client.commit_revision(
        tree_name="mock_configtree_name",
        revision_id="mock_revision_id",
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_revision_guid"
    assert response.metadata.name == "test_revision"


def test_get_key_in_revision_str(client, mocker: MockFixture):  # noqa: F811
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
    assert isinstance(response, str)
    assert response == "test_value"


def test_get_key_in_revision_int(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
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
    assert isinstance(response, int)
    assert response == 1500


def test_get_key_in_revision_bool(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        text="true",
    )

    # Call the get_key_in_revision method
    response = client.get_key_in_revision(
        tree_name="mock_configtree_name", revision_id="mock_revision_id", key="mock_key"
    )

    # Validate the response
    assert isinstance(response, bool)
    assert response


def test_put_key_in_revision_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_revision_guid", "name": "test_revision"},
        },
    )

    # Call the put_key_in_revision method
    response = client.put_key_in_revision(
        tree_name="mock_configtree_name", revision_id="mock_revision_id", key="mock_key"
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_revision_guid"
    assert response.metadata.name == "test_revision"


def test_delete_key_in_revision_success(client, mocker: MockFixture):  # noqa: F811
    mock_delete = mocker.patch("httpx.Client.delete")

    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    response = client.delete_key_in_revision(
        tree_name="mock_configtree_name", revision_id="mock_revision_id", key="mock_key"
    )

    assert response["success"] is True


def test_rename_key_in_revision_success(client, mocker: MockFixture):  # noqa: F811
    mock_patch = mocker.patch("httpx.Client.patch")

    mock_patch.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_revision_guid", "name": "test_revision"},
        },
    )

    response = client.rename_key_in_revision(
        tree_name="mock_configtree_name",
        revision_id="mock_revision_id",
        key="mock_key",
        config_key_rename={"metadata": {"name": "test_key"}},
    )

    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_revision_guid"
    assert response.metadata.name == "test_revision"
