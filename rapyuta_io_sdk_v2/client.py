# -*- coding: utf-8 -*-
# Copyright 2024 Rapyuta Robotics
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

import httpx
from munch import Munch, munchify

from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.utils import handle_server_errors


class Client(object):
    """Client class offers sync client for the v2 APIs.

    Args:
        config (Configuration): Configuration object.
        **kwargs: Additional keyword arguments.
    """

    def __init__(self, config: Configuration = None, **kwargs):
        self.config = config or Configuration()
        timeout = kwargs.get("timeout", 10)
        self.c = httpx.Client(
            timeout=timeout,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=5,
                keepalive_expiry=30,
            ),
        )

    def login(
        self,
        email: str = None,
        password: str = None,
        environment: str = "ga",
    ) -> str:
        """Get the authentication token for the user.

        Args:
            email (str)
            password (str)
            environment (str)

        Returns:
            str: authentication token
        """
        if email is None and password is None and self.config is None:
            raise ValueError("email and password are required")

        if self.config is None:
            self.config = Configuration(
                email=email, password=password, environment=environment
            )

        payload = {
            "email": email or self.config.email,
            "password": password or self.config.password,
        }

        rip_host = self.config.hosts.get("rip_host")
        url = f"{rip_host}/user/login"
        headers = {"Content-Type": "application/json"}

        response = self.c.post(url=url, headers=headers, json=payload)

        handle_server_errors(response)

        self.config.auth_token = response.json()["data"].get("token")

        return self.config.auth_token

    def logout(self, token: str = None) -> None:
        """Expire the authentication token.

        Args:
            token (str): The token to expire.
        """
        rip_host = self.config.hosts.get("rip_host")
        url = f"{rip_host}/user/logout"
        headers = {"Content-Type": "application/json"}

        if token is None:
            token = self.config.auth_token

        response = self.c.post(url=url, headers=headers, json={"token": token})

        handle_server_errors(response)

        return

    def refresh_token(self, token: str = None) -> str:
        """Refresh the authentication token.

        Args:
            token (str): The token to refresh.

        Returns:
            str: The refreshed token.
        """
        rip_host = self.config.hosts.get("rip_host")
        url = f"{rip_host}/refreshtoken"
        headers = {"Content-Type": "application/json"}

        if token is None:
            token = self.config.auth_token

        response = self.c.post(url=url, headers=headers, json={"token": token})

        handle_server_errors(response)

        data = response.json()["data"]
        self.config.auth_token = data["Token"]

        return self.config.auth_token

    def set_organization(self, organization_guid: str) -> None:
        """Set the organization GUID.

        Args:
            organization_guid (str): Organization GUID
        """
        self.config.set_organization(organization_guid)

    def set_project(self, project_guid: str) -> None:
        """Set the project GUID.

        Args:
            project_guid (str): Project GUID
        """
        self.config.set_project(project_guid)

    def get_project(self, project_guid: str = None) -> Munch:
        """Get a project by its GUID.

        If no project or organization GUID is provided,
        the default project and organization GUIDs will
        be picked from the current configuration.

        Args:
            project_guid (str): Project GUID

        Raises:
            ValueError: If organization_guid or project_guid is None

        Returns:
            Munch: Project details as a Munch object.
        """
        headers = self.config.get_headers(with_project=False)

        if project_guid is None:
            project_guid = self.config.project_guid

        if not project_guid:
            raise ValueError("project_guid is required")

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/projects/{project_guid}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())
