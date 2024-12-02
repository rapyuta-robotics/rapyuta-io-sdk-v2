import httpx
import pytest
from munch import Munch
from pytest_mock import MockerFixture

from tests.utils.test_util import client, staticroute_body  # noqa: F401


def test_list_staticroutes_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-staticroute", "guid": "mock_staticroute_guid"}],
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

    # Call the list_staticroutes method
    response = client.list_staticroutes()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [
        {"name": "test-staticroute", "guid": "mock_staticroute_guid"}
    ]


def test_list_staticroutes_not_found(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        "Authorization": f"Bearer {client.auth_token}",
        "organizationguid": client.organization_guid,
        "project": "mock_project_guid" if with_project else None,
    }

    with pytest.raises(Exception) as exc:
        client.list_staticroutes()

    assert str(exc.value) == "not found"


def test_create_staticroute_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_staticroute_guid", "name": "test_staticroute"},
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

    # Call the create_staticroute method
    response = client.create_staticroute(body=staticroute_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_staticroute_guid"


def test_create_staticroute_bad_request(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "already exists"},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        "Authorization": f"Bearer {client.auth_token}",
        "organizationguid": client.organization_guid,
        "project": "mock_project_guid" if with_project else None,
    }

    with pytest.raises(Exception) as exc:
        client.create_staticroute(body=staticroute_body)

    assert str(exc.value) == "already exists"


def test_get_staticroute_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_staticroute_guid", "name": "test_staticroute"},
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

    # Call the get_staticroute method
    response = client.get_staticroute(name="mock_staticroute_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_staticroute_guid"


def test_update_staticroute_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_staticroute_guid", "name": "test_staticroute"},
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

    # Call the update_staticroute method
    response = client.update_staticroute(
        name="mock_staticroute_name", body=staticroute_body
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_staticroute_guid"


def test_delete_staticroute_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=False: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": None,
        }.items()
        if v is not None
    }

    # Call the delete_staticroute method
    response = client.delete_staticroute(name="mock_staticroute_name")

    # Validate the response
    assert response["success"] is True
