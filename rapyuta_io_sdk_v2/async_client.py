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
from typing import Any, AsyncGenerator, Dict, List, Optional, override

import httpx

from rapyuta_io_sdk_v2.client import Client


class AsyncClient(Client):
    def __init__(self, config):
        super().__init__(config)

    @asynccontextmanager
    async def _get_client(self) -> AsyncGenerator[httpx.AsyncClient, None]:
        async with httpx.AsyncClient(
            headers=self._get_headers(),
        ) as async_client:
            yield async_client

    @override
    async def list_projects(self, organization_guid: str = None):
        url = "{}/v2/projects/".format(self.v2api_host)
        params = {}
        if organization_guid:
            params.update(
                {
                    "organizations": organization_guid,
                }
            )
        async with self._get_client() as client:
            response = await client.get(url=url, params=params)
            response.raise_for_status()
            return response.json()

    @override
    async def get_project(self, project_guid: str):
        url = "{}/v2/projects/{}/".format(self.v2api_host, project_guid)

        async with self._get_client() as client:
            response = await client.get(url=url)
            response.raise_for_status()
            return response.json()

    @override
    async def list_config_trees(self) -> List[str]:
        url = "{}/v2/configtrees/".format(self.v2api_host)
        try:
            async with self._get_client() as client:
                res = await client.get(url=url)
                res.raise_for_status()

        except Exception as e:
            raise ValueError(f"Failed to list config trees: {res.text}") from e

        if tree_list := res.json().get("items"):
            return [item["metadata"]["name"] for item in tree_list]
        else:
            return []

    @override
    async def get_config_tree(
        self,
        tree_name: str,
        rev_id: Optional[str] = None,
        include_data: bool = False,
        filter_content_types: Optional[List[str]] = None,
        filter_prefixes: Optional[List[str]] = None,
    ):
        url = "{}/v2/configtrees/{}/".format(self.v2api_host, tree_name)
        try:
            params: Dict[str, Any] = {
                "includeData": include_data,
                "contentTypes": filter_content_types,
                "keyPrefixes": filter_prefixes,
                "revision": rev_id,
            }

            async with self._get_client() as client:
                res = await client.get(url=url, params=params)
                res.raise_for_status()
        except Exception as e:
            raise ValueError(f"Failed to get config tree data: {res.text}")

        raw_config_tree = res.json()
        return raw_config_tree

    @override
    async def create_config_tree(self, tree_spec: dict):
        url = "{}/v2/configtrees/".format(self.v2api_host)
        try:
            async with self._get_client() as client:
                res = await client.post(url=url, json=tree_spec)
                res.raise_for_status()
        except Exception as e:
            raise ValueError(f"Failed to create config tree: {res.text}")

        raw_config_tree = res.json()
        return raw_config_tree
