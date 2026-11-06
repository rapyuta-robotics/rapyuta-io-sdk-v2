# Copyright 2026 Rapyuta Robotics
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import pytest

from rapyuta_io_sdk_v2 import AsyncClient, Client


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
