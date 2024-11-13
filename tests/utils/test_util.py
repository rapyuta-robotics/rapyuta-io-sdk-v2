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
        "kind": "Project",
        "metadata": {"name": "test-project", "guid": "mock_project_guid"},
        "spec": {
            "users": [
                {"userGUID": "mock_user_guid", "emailID": "test.user@example.com"}
            ]
        },
    }


@pytest.fixture
def project_body():
    return {
        "apiVersion": "api.rapyuta.io/v2",
        "kind": "Project",
        "metadata": {
            "name": "test-project",
            "labels": {"purpose": "testing", "version": "1.0"},
        },
        "spec": {
            "users": [{"emailID": "test.user@example.com", "role": "admin"}],
            "features": {"vpn": {"enabled": False}},
        },
    }
