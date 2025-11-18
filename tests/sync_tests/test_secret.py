import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import Secret, SecretList
from tests.data.mock_data import secret_body, secret_model_mock, secretlist_model_mock
from tests.utils.fixtures import client


def test_list_secrets_success(client, secretlist_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=secretlist_model_mock,
    )

    # Call the list_secrets method
    response = client.list_secrets()

    # Validate the response
    assert isinstance(response, SecretList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    secret = response.items[0]
    assert secret.metadata.guid == "secret-aaaaaaaaaaaaaaaaaaaa"
    assert secret.metadata.name == "test_secret"
    assert secret.kind == "Secret"


def test_list_secrets_not_found(client, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        client.list_secrets()

    assert str(exc.value) == "not found"


def test_create_secret_success(
    client, secret_body, secret_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=secret_model_mock,
    )

    # Call the create_secret method
    response = client.create_secret(secret_body)

    # Validate the response
    assert isinstance(response, Secret)
    assert response.metadata.guid == "secret-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test_secret"


def test_create_secret_already_exists(client, secret_body, mocker: MockFixture):
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "secret already exists"},
    )

    with pytest.raises(Exception) as exc:
        client.create_secret(secret_body)

    assert str(exc.value) == "secret already exists"


def test_update_secret_success(
    client, secret_body, secret_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=secret_model_mock,
    )

    # Call the update_secret method
    response = client.update_secret("secret-aaaaaaaaaaaaaaaaaaaa", body=secret_body)

    # Validate the response
    assert isinstance(response, Secret)
    assert response.metadata.guid == "secret-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test_secret"


def test_delete_secret_success(client, mocker: MockFixture):
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_secret method
    response = client.delete_secret("secret-aaaaaaaaaaaaaaaaaaaa")

    # Validate the response
    assert response is None


def test_get_secret_success(client, secret_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=secret_model_mock,
    )

    # Call the get_secret method
    response = client.get_secret("secret-aaaaaaaaaaaaaaaaaaaa")

    # Validate the response
    assert isinstance(response, Secret)
    assert response.metadata.guid == "secret-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test_secret"
