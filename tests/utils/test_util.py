import pytest
from rapyuta_io_sdk_v2.client import Client


# Fixture to initialize the Client
@pytest.fixture
def client():
    client = Client()
    client.config.hosts["v2api_host"] = "https://mock-api.rapyuta.io"
    client.auth_token = "mock_token"
    client.organization_guid = "mock_org_guid"
    client.project = "mock_project_guid"
    return client


@pytest.fixture
def mock_response():
    return {
        "name": "test_project",
        "organization": "mock_org_guid",
    }
