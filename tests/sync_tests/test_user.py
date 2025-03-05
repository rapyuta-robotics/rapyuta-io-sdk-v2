import httpx
import pytest
from munch import Munch
from pytest_mock import MockFixture

from tests.data.mock_data import mock_response_user, user_body  # noqa: F401
from tests.utils.fixtures import client  # noqa: F401


def test_get_user_success(client, mocker: MockFixture):  # noqa: F811
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "User",
            "metadata": {"name": "test-org", "guid": "mock_org_guid"},
        },
    )

    response = client.get_user()

    assert isinstance(response, Munch)
    assert response["metadata"] == {"name": "test-org", "guid": "mock_org_guid"}


def test_get_user_unauthorized(client, mocker: MockFixture):  # noqa: F811
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(Exception) as exc:
        client.get_user()

    assert str(exc.value) == "user cannot be authenticated"


def test_update_user_success(
    client,  # noqa: F811
    mock_response_user,  # noqa: F811
    mocker: MockFixture,
):
    mock_put = mocker.patch("httpx.Client.put")

    mock_put.return_value = httpx.Response(
        status_code=200,
        json=mock_response_user,
    )

    response = client.update_user(
        body=user_body,
    )

    assert isinstance(response, Munch)
    assert response["metadata"] == {"name": "test user", "guid": "mock_user_guid"}


def test_update_user_unauthorized(client, mocker: MockFixture):  # noqa: F811
    mock_put = mocker.patch("httpx.Client.put")

    mock_put.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(Exception) as exc:
        client.update_user(user_body)

    assert str(exc.value) == "user cannot be authenticated"
