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
from typing import Optional, List, Dict, Any
from benedict import benedict
from rapyuta_io_sdk_v2.utils import unflatten_keys
import httpx, json

from .utils import handle_server_errors
from rapyuta_io_sdk_v2.constants import GET_USER_PATH

class Client(object):
    PROD_V2API_URL = "https://api.rapyuta.io"
    def __init__(self,config):
        self.config = config
        self.v2api_host = config.hosts.get("v2api_host",self.PROD_V2API_URL)

    def _get_headers(self, with_project: bool = True) -> dict:
        headers = {
            "Authorization" : 'Bearer '+self.config.auth_token,
            "Content-Type": "application/json",
            "project": self.config.project_guid,
            "organizationguid": self.config.organization_guid,
        }
        return headers

    @staticmethod
    def _preprocess_config_tree_data(raw_config_tree: Optional[Dict[str, Any]]):
        if raw_config_tree:
            return unflatten_keys(raw_config_tree)
        else:
            return benedict()

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

    def list_projects(self,organization_guid: str = None):
        """

        :param organization_guid:
        :return:
        """
        url = "{}/v2/projects/".format(self.v2api_host)
        headers = self._get_headers(with_project=False)
        params = {}
        if organization_guid:
            params.update({
                "organizations": organization_guid,
            })
        response = httpx.get(url=url,headers=headers,params=params)
        handle_server_errors(response)
        return response.json()

    def get_project(self, project_guid: str):
        """

        :param project_guid:
        :return:
        """
        url = "{}/v2/projects/{}/".format(self.v2api_host, project_guid)
        headers = self._get_headers(with_project=False)
        response = httpx.get(url=url,headers=headers)
        handle_server_errors(response)
        return response.json()

    def get_config_tree(self,tree_name: str, rev_id: Optional[str]=None,
        include_data: bool = False, filter_content_types: Optional[List[str]] = None,
        filter_prefixes: Optional[List[str]] = None):

        url = "{}/v2/configtrees/{}/".format(self.v2api_host, tree_name)
        query = {
            'includeData': include_data,
            'contentTypes': filter_content_types,
            'keyPrefixes': filter_prefixes,
            'revision': rev_id,
        }
        headers = self._get_headers()
        response = httpx.get(url=url,headers=headers,params=query)
        handle_server_errors(response)
        return response.json()

    def create_config_tree(self,tree_spec: dict):
        url = "{}/v2/configtrees/".format(self.v2api_host)
        headers = self._get_headers()
        response = httpx.post(url=url,headers=headers,json=tree_spec)
        handle_server_errors(response)
        return response.json()

    def delete_config_tree(self,tree_name:str):
        url = "{}/v2/configtrees/{}/".format(self.v2api_host, tree_name)
        headers = self._get_headers()
        response = httpx.delete(url=url,headers=headers)
        handle_server_errors(response)
        return response.json()

    def list_config_trees(self):
        url = "{}/v2/configtrees/".format(self.v2api_host)
        headers = self._get_headers()
        response = httpx.get(url=url,headers=headers)
        handle_server_errors(response)
        return response.json()

    def set_revision_config_tree(self, tree_name: str, spec: dict) -> None:
        url = "{}/v2/configtrees/{}/".format(self.v2api_host, tree_name)
        headers = self._get_headers()
        response = httpx.put(url=url,headers=headers,json=spec)
        handle_server_errors(response)

        data = json.loads(response.text)
        print(data)
        if not data.ok:
            err_msg = data.get('error')
            raise Exception("configtree: {}".format(err_msg))


