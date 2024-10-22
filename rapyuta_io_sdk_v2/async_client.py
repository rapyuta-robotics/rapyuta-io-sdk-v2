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

    @staticmethod
    async def get_token(self, email: str, password: str) -> str:
        url = "{}/user/login/".format(self.v2api_host)  
        headers = {"Content-Type": "application/json"}
        data = {"email": email, "password": password}
        response = httpx.post(url=url, headers=headers, json=data, timeout=10)
        handle_server_errors(response)
        return response.json().get("token")

    @staticmethod
    async def expire_token(token: str) -> None:
        pass
