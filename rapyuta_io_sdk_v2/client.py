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
import json
from typing import Any, Dict, List, Optional

import httpx
from utils import handle_server_errors

from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.constants import GET_USER_PATH


class Client(object):
    PROD_V2API_URL = "https://api.rapyuta.io"

    def __init__(self, config: Configuration = None):
        self.config = config
        self.v2api_host = config.hosts.get("v2api_host", self.PROD_V2API_URL)

    def _get_headers(self, with_project: bool = True) -> dict:
        headers = {
            "Authorization": "Bearer " + self.config.auth_token,
            "Content-Type": "application/json",
            "project": self.config.project_guid,
            "organizationguid": self.config.organization_guid,
        }
        return headers

    def get_authenticated_user(self) -> Optional[Dict]:
        try:
            _core_api_host = self.config.hosts.get("core_api_host")
            url = "{}{}".format(_core_api_host, GET_USER_PATH)
            headers = self._get_headers()
            response = httpx.get(url=url, headers=headers)
            handle_server_errors(response)
            return response.json()
        except Exception as e:
            raise

    @staticmethod
    def get_token(self, email: str, password: str) -> str:
        url = "{}/v2/user/login/".format(self.v2api_host)  # URL not confirmed
        headers = {"Content-Type": "application/json"}
        data = {"email": email, "password": password}
        response = httpx.post(url=url, headers=headers, json=data)
        handle_server_errors(response)
        return response.json().get("token")
    
    @staticmethod
    def expire_token(token: str) -> None:
        pass
    
    def set_project(self, project_guid: str):
        self.config.project_guid = project_guid
    
    def set_organization(self, organization_guid: str):
        self.config.organization_guid = organization_guid

    def list_projects(self, organization_guid: str = None):
        """

        :param organization_guid:
        :return:
        """
        url = "{}/v2/projects/".format(self.v2api_host)
        headers = self._get_headers(with_project=False)
        params = {}
        if organization_guid:
            params.update(
                {
                    "organizations": organization_guid,
                }
            )
        response = httpx.get(url=url, headers=headers, params=params)
        handle_server_errors(response)
        return response.json()

    def get_project(self, project_guid: str):
        """

        :param project_guid:
        :return:
        """
        url = "{}/v2/projects/{}/".format(self.v2api_host, project_guid)
        headers = self._get_headers(with_project=False)
        response = httpx.get(url=url, headers=headers)
        handle_server_errors(response)
        return response.json()

    def get_config_tree(
        self,
        tree_name: str,
        rev_id: Optional[str] = None,
        include_data: bool = False,
        filter_content_types: Optional[List[str]] = None,
        filter_prefixes: Optional[List[str]] = None,
    ):
        url = "{}/v2/configtrees/{}/".format(self.v2api_host, tree_name)
        query = {
            "includeData": include_data,
            "contentTypes": filter_content_types,
            "keyPrefixes": filter_prefixes,
            "revision": rev_id,
        }
        headers = self._get_headers()
        response = httpx.get(url=url, headers=headers, params=query)
        handle_server_errors(response)
        return response.json()

    def create_config_tree(self, tree_spec: dict):
        url = "{}/v2/configtrees/".format(self.v2api_host)
        headers = self._get_headers()
        response = httpx.post(url=url, headers=headers, json=tree_spec)
        handle_server_errors(response)
        return response.json()

    def delete_config_tree(self, tree_name: str):
        url = "{}/v2/configtrees/{}/".format(self.v2api_host, tree_name)
        headers = self._get_headers()
        response = httpx.delete(url=url, headers=headers)
        handle_server_errors(response)
        return response.json()

    def list_config_trees(self):
        url = "{}/v2/configtrees/".format(self.v2api_host)
        headers = self._get_headers()
        response = httpx.get(url=url, headers=headers)
        handle_server_errors(response)
        return response.json()

    def set_revision_config_tree(self, tree_name: str, spec: dict) -> None:
        url = "{}/v2/configtrees/{}/".format(self.v2api_host, tree_name)
        headers = self._get_headers()
        response = httpx.put(url=url, headers=headers, json=spec)
        handle_server_errors(response)

        data = json.loads(response.text)
        print(data)
        if not data.ok:
            err_msg = data.get("error")
            raise Exception("configtree: {}".format(err_msg))
