import json

# ruff: noqa: F811, F401

import pytest
from rapyuta_io_sdk_v2.config import Configuration
from tests.data.mock_data import mock_config, config_obj


def test_from_file(mocker, mock_config):
    mock_file_content = json.dumps(mock_config)

    # Mock the open function
    mocker.patch("builtins.open", mocker.mock_open(read_data=mock_file_content))

    # Mock the default directory function
    mocker.patch(
        "rapyuta_io_sdk_v2.config.get_default_app_dir", return_value="/mock/default/dir"
    )

    # Call the method to test
    config = Configuration.from_file(file_path="/mock/path/to/config.json")

    # Assert the Configuration object contains the expected values
    assert config.project_guid == mock_config["project_id"]
    assert config.organization_guid == mock_config["organization_id"]
    assert config.auth_token == mock_config["auth_token"]


def test_get_headers_basic(config_obj):
    # Call the method without passing any arguments
    headers = config_obj.get_headers()

    # Verify the headers
    assert headers["Authorization"] == "Bearer mock_auth_token"
    assert headers["organizationguid"] == "mock_org_guid"
    assert headers["project"] == "mock_project_guid"


def test_get_headers_without_project(config_obj):
    # Call the method with `with_project=False`
    headers = config_obj.get_headers(with_project=False)

    # Verify the headers
    assert headers["Authorization"] == "Bearer mock_auth_token"
    assert headers["organizationguid"] == "mock_org_guid"
    assert "project" not in headers


def test_get_headers_with_custom_values(config_obj):
    # Call the method with custom organization_guid and project_guid
    headers = config_obj.get_headers(
        organization_guid="custom_org_guid",
        project_guid="custom_project_guid",
    )

    # Verify the headers
    assert headers["Authorization"] == "Bearer mock_auth_token"
    assert headers["organizationguid"] == "custom_org_guid"
    assert headers["project"] == "custom_project_guid"


def test_get_headers_with_request_id(mocker, config_obj):
    # Mock the environment variable
    mocker.patch("os.getenv", return_value="mock_request_id")

    # Call the method
    headers = config_obj.get_headers()

    # Verify the headers
    assert headers["Authorization"] == "Bearer mock_auth_token"
    assert headers["organizationguid"] == "mock_org_guid"
    assert headers["project"] == "mock_project_guid"
    assert headers["X-Request-ID"] == "mock_request_id"
