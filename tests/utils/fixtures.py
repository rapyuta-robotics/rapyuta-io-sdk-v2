import pytest
from rapyuta_io_sdk_v2 import Client, AsyncClient


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
def async_client():
    client = AsyncClient()
    client.config.hosts["v2api_host"] = "https://mock-api.rapyuta.io"
    client.auth_token = "mock_token"
    client.organization_guid = "mock_org_guid"
    client.project = "mock_project_guid"
    return client
