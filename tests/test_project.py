from pytest_mock import MockerFixture
from munch import Munch
import httpx
from tests.utils.test_util import client, mock_response  # noqa: F401


# Test function for list_projects
def test_list_projects(client, mock_response, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=mock_response,
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the list_projects method
    response = client.list_projects()

    # Validate the response
    assert isinstance(response, Munch)
    assert response.name == "test_project"
