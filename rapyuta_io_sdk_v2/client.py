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
from typing import Dict, Optional

import httpx

from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.constants import GET_USER_API_PATH
from rapyuta_io_sdk_v2.utils import handle_server_errors


class Client(object):
    PROD_V2API_URL = "https://api.rapyuta.io"

    def __init__(self, config: Configuration = None):
        self.config = config
        if config is None:
            self.v2api_host = self.PROD_V2API_URL
        else:
            self.v2api_host = config.hosts.get("v2api_host", self.PROD_V2API_URL)

    def _get_headers(self, with_project: bool = True) -> dict:
        headers = {
            "Authorization": "Bearer " + self.config.auth_token,
            "Content-Type": "application/json",
            "organizationguid": self.config.organization_guid,
        }
        if with_project:
            headers["project"] = self.config.project_guid
        return headers

    def get_authenticated_user(self) -> Optional[Dict]:
        try:
            _core_api_host = self.config.hosts.get("core_api_host")
            url = "{}{}".format(_core_api_host, GET_USER_API_PATH)
            headers = self._get_headers()
            response = httpx.get(url=url, headers=headers, timeout=10)
            handle_server_errors(response)
            return response.json()
        except Exception:
            raise

    def get_token(
        self, email: str = None, password: str = None, env: str = "ga"
    ) -> str:
        """Get the authentication token for the user.

        Args:
            email (str)
            password (str)

        Returns:
            str: authentication token
        """
        if email is None and password is None and self.config is None:
            raise ValueError("email and password are required")

        if self.config is None:
            self.config = Configuration(email=email, password=password, environment=env)

        data = {
            "email": email or self.config.email,
            "password": password or self.config._password,
        }

        rip_host = self.config.hosts.get("rip_host")
        url = "{}/user/login".format(rip_host)
        headers = {"Content-Type": "application/json"}
        response = httpx.post(url=url, headers=headers, json=data, timeout=10)
        handle_server_errors(response)
        self.config.auth_token = response.json()["data"].get("token")
        return self.config.auth_token

    @staticmethod
    def expire_token(token: str) -> None:
        pass

    def refresh_token(self, token: str) -> str:
        """Refresh the authentication token.

        Args:
            token (str): The token to refresh.

        Returns:
            str: The refreshed token.
        """
        rip_host = self.config.hosts.get("rip_host")
        url = "{}/refreshtoken".format(rip_host)
        headers = {"Content-Type": "application/json"}

        response = httpx.post(
            url=url, headers=headers, json={"token": token}, timeout=10
        )
        handle_server_errors(response)

        data = response.json()["data"]
        self.config.auth_token = data["Token"]
        return self.config.auth_token

    def set_project(self, project_guid: str):
        self.config.project_guid = project_guid

    def set_organization(self, organization_guid: str):
        self.config.organization_guid = organization_guid
        
    def list_projects(self, organization_guid: str):
        if organization_guid is None:
            raise ValueError("organization_guid is required")
        v2api_host = self.config.hosts.get("v2api_host")
        self.config.organization_guid = organization_guid
        headers = self._get_headers(with_project=False)
        response = httpx.get(
            url="{}/v2/projects/".format(v2api_host), headers=headers, timeout=10
        )
        handle_server_errors(response)
        return response.json()