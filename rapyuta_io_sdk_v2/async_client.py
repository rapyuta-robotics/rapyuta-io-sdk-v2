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
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx

from rapyuta_io_sdk_v2.client import Client
from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.utils import handle_server_errors


class AsyncClient(Client):
    def __init__(self, config):
        super().__init__(config)

    @asynccontextmanager
    async def _get_client(self) -> AsyncGenerator[httpx.AsyncClient, None]:
        async with httpx.AsyncClient(
            headers=self._get_headers(),
        ) as async_client:
            yield async_client

    async def get_token(
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

        async with httpx.AsyncClient() as asyncClient:
            response = await asyncClient.post(
                url=url, headers=headers, json=data, timeout=10
            )
            handle_server_errors(response)
            return response.json()["data"].get("token")

    @staticmethod
    async def expire_token(token: str) -> None:
        pass

    async def refresh_token(self, token: str) -> str:
        rip_host = self.config.hosts.get("rip_host")
        url = "{}/refreshtoken".format(rip_host)
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient() as asyncClient:
            response = await asyncClient.post(
                url=url, headers=headers, json={"token": token}, timeout=10
            )
            handle_server_errors(response)

            data = response.json()["data"]
            return data["Token"]
