import httpx
import pytest
from munch import Munch
from pytest_mock import MockerFixture

from tests.utils.test_util import client, configtree_body  # noqa: F401


def test_list_configtrees_success(client, mocker: MockerFixture):  # noqa: F811
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

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the list_configtrees method
    response = client.list_configtrees()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [
        {"name": "test-configtree", "guid": "mock_configtree_guid"}
    ]


def test_list_configtrees_bad_gateway(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=502,
        json={"error": "bad gateway"},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        "Authorization": f"Bearer {client.auth_token}",
        "organizationguid": client.organization_guid,
        "project": "mock_project_guid" if with_project else None,
    }

    # Call the list_configtrees method
    with pytest.raises(Exception) as exc:
        client.list_configtrees()

    assert str(exc.value) == "bad gateway"


def test_create_configtree_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_configtree_guid", "name": "test_configtree"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        "Authorization": f"Bearer {client.auth_token}",
        "organizationguid": client.organization_guid,
        "project": "mock_project_guid" if with_project else None,
    }

    # Call the create_configtree method
    response = client.create_configtree(configtree_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "test_configtree_guid"


def test_create_configtree_service_unavailable(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=503,
        json={"error": "service unavailable"},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        "Authorization": f"Bearer {client.auth_token}",
        "organizationguid": client.organization_guid,
        "project": "mock_project_guid" if with_project else None,
    }

    # Call the create_configtree method
    with pytest.raises(Exception) as exc:
        client.create_configtree(configtree_body)

    assert str(exc.value) == "service unavailable"


def test_get_configtree_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_configtree_guid", "name": "test_configtree"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the get_configtree method
    response = client.get_configtree(name="mock_configtree_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_configtree_guid"
    assert response.metadata.name == "test_configtree"


def test_set_configtree_revision_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_configtree_guid", "name": "test_configtree"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the set_configtree_revision method
    response = client.set_configtree_revision(
        name="mock_configtree_name", configtree=configtree_body
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_configtree_guid"
    assert response.metadata.name == "test_configtree"


def test_update_configtree_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_configtree_guid", "name": "test_configtree"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the update_configtree method
    response = client.update_configtree(name="mock_configtree_name", body=configtree_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_configtree_guid"
    assert response.metadata.name == "test_configtree"


def test_delete_configtree_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the delete_configtree method
    response = client.delete_configtree(name="mock_configtree_name")

    # Validate the response
    assert response["success"] is True


def test_list_revisions_success(client, mocker: MockerFixture):  # noqa: F811
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

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the list_revisions method
    response = client.list_revisions(name="mock_configtree_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [
        {"name": "test-configtree", "guid": "mock_configtree_guid"}
    ]


def test_create_revision_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_revision_guid", "name": "test_revision"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True, **kwargs: {
        "Authorization": f"Bearer {client.auth_token}",
        "organizationguid": client.organization_guid,
        "project": kwargs.get("project_guid") if with_project else None,
    }

    # Call the create_revision method
    response = client.create_revision(name="mock_configtree_name", body=configtree_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "test_revision_guid"


def test_put_keys_in_revision_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_revision_guid", "name": "test_revision"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the put_keys_in_revision method
    response = client.put_keys_in_revision(
        name="mock_configtree_name",
        revision_id="mock_revision_id",
        configValues=["mock_value1", "mock_value2"],
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_revision_guid"
    assert response.metadata.name == "test_revision"


def test_commit_revision_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.put method
    mock_patch = mocker.patch("httpx.Client.patch")

    # Set up the mock response
    mock_patch.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_revision_guid", "name": "test_revision"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the commit_revision method
    response = client.commit_revision(
        name="mock_configtree_name",
        revision_id="mock_revision_id",
        configTreeRevision=configtree_body,
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_revision_guid"
    assert response.metadata.name == "test_revision"


def test_get_key_in_revision(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_revision_guid", "name": "test_revision"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the get_key_in_revision method
    response = client.get_key_in_revision(
        name="mock_configtree_name", revision_id="mock_revision_id", key="mock_key"
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_revision_guid"
    assert response.metadata.name == "test_revision"


def test_put_key_in_revision_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_revision_guid", "name": "test_revision"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the put_key_in_revision method
    response = client.put_key_in_revision(
        name="mock_configtree_name", revision_id="mock_revision_id", key="mock_key"
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_revision_guid"
    assert response.metadata.name == "test_revision"


def test_delete_key_in_revision_success(client, mocker: MockerFixture):  # noqa: F811
    mock_delete = mocker.patch("httpx.Client.delete")

    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    client.config.get_headers = lambda with_project=True, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    response = client.delete_key_in_revision(
        name="mock_configtree_name", revision_id="mock_revision_id", key="mock_key"
    )

    assert response["success"] is True


def test_rename_key_in_revision_success(client, mocker: MockerFixture):  # noqa: F811
    mock_patch = mocker.patch("httpx.Client.patch")

    mock_patch.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_revision_guid", "name": "test_revision"},
        },
    )

    client.config.get_headers = lambda with_project=True, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    response = client.rename_key_in_revision(
        name="mock_configtree_name",
        revision_id="mock_revision_id",
        key="mock_key",
        configKeyRename={"metadata": {"name": "test_key"}},
    )

    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_revision_guid"
    assert response.metadata.name == "test_revision"
