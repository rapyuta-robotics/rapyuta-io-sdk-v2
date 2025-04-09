import pytest
from rapyuta_io_sdk_v2 import Client, AsyncClient


# Fixture to initialize the Client
@pytest.fixture
def client() -> Client:
    client = Client()
    client.config.hosts["v2api_host"] = "https://mock-api.rapyuta.io"
    client.config.auth_token = "mock_token"
    client.config.organization_guid = "mock_org_guid"
    client.config.project_guid = "mock_project_guid"
    client.config.environment = "mock"
    return client


@pytest.fixture
def async_client() -> AsyncClient:
    client = AsyncClient()
    client.config.hosts["v2api_host"] = "https://mock-api.rapyuta.io"
    client.config.auth_token = "mock_token"
    client.config.organization_guid = "mock_org_guid"
    client.config.project_guid = "mock_project_guid"
    client.config.environment = "mock"
    return client
