import pytest
from rapyuta_io_sdk_v2 import Client, AsyncClient, Configuration


# Fixture to initialize the Client
@pytest.fixture
def client() -> Client:
    client = Client(
        Configuration(load_cli_config=False, v2_api_host="https://mock-api.rapyuta.io")
    )
    client.config.auth_token = "mock_token"
    client.config.organization_guid = "mock_org_guid"
    client.config.project_guid = "mock_project_guid"
    return client


@pytest.fixture
def async_client() -> AsyncClient:
    client = AsyncClient(
        Configuration(load_cli_config=False, v2_api_host="https://mock-api.rapyuta.io")
    )
    client.config.auth_token = "mock_token"
    client.config.organization_guid = "mock_org_guid"
    client.config.project_guid = "mock_project_guid"
    return client
