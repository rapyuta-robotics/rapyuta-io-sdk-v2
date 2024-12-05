import json
from rapyuta_io_sdk_v2.config import Configuration
from tests.data.mock_data import mock_config  # noqa: F401


def test_from_file(mocker):
    # Mock configuration file content
    mock_config_data = {
        "project_id": "mock_project_guid",
        "organization_id": "mock_org_guid",
        "auth_token": "mock_auth_token",
    }
    mock_file_content = json.dumps(mock_config_data)

    # Mock the open function
    mocker.patch("builtins.open", mocker.mock_open(read_data=mock_file_content))

    # Mock the default directory function
    mocker.patch(
        "rapyuta_io_sdk_v2.config.get_default_app_dir", return_value="/mock/default/dir"
    )

    # Call the method to test
    config = Configuration.from_file(file_path="/mock/path/to/config.json")

    # Assert the Configuration object contains the expected values
    assert config.project_guid == mock_config_data["project_id"]
    assert config.organization_guid == mock_config_data["organization_id"]
    assert config.auth_token == mock_config_data["auth_token"]


def test_get_headers_basic(mock_config):  # noqa: F811
    # Call the method without passing any arguments
    headers = mock_config.get_headers()

    # Verify the headers
    assert headers["Authorization"] == "Bearer mock_auth_token"
    assert headers["organizationguid"] == "mock_org_guid"
    assert headers["project"] == "mock_project_guid"


def test_get_headers_without_project(mock_config):  # noqa: F811
    # Call the method with `with_project=False`
    headers = mock_config.get_headers(with_project=False)

    # Verify the headers
    assert headers["Authorization"] == "Bearer mock_auth_token"
    assert headers["organizationguid"] == "mock_org_guid"
    assert "project" not in headers


def test_get_headers_with_custom_values(mock_config):  # noqa: F811
    # Call the method with custom organization_guid and project_guid
    headers = mock_config.get_headers(
        organization_guid="custom_org_guid",
        project_guid="custom_project_guid",
    )

    # Verify the headers
    assert headers["Authorization"] == "Bearer mock_auth_token"
    assert headers["organizationguid"] == "custom_org_guid"
    assert headers["project"] == "custom_project_guid"


def test_get_headers_with_request_id(mocker, mock_config):  # noqa: F811
    # Mock the environment variable
    mocker.patch("os.getenv", return_value="mock_request_id")

    # Call the method
    headers = mock_config.get_headers()

    # Verify the headers
    assert headers["Authorization"] == "Bearer mock_auth_token"
    assert headers["organizationguid"] == "mock_org_guid"
    assert headers["project"] == "mock_project_guid"
    assert headers["X-Request-ID"] == "mock_request_id"
