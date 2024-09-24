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
from typing import Optional

from rapyuta_io_sdk_v2.async_client import AsyncClient
from rapyuta_io_sdk_v2.client import Client
from rapyuta_io_sdk_v2.constants import LOGIN_ROUTE_PATH, NAMED_ENVIRONMENTS, STAGING_ENVIRONMENT_SUBDOMAIN, PROD_ENVIRONMENT_SUBDOMAIN
from rapyuta_io_sdk_v2.exceptions import ValidationError, AuthenticationError, LoggedOutError
import httpx

from rapyuta_io_sdk_v2.utils import validate_auth_token


class Configuration(object):

    def __init__(self, project_guid: str, organization_guid: str, password: str=None,auth_token: str=None, environment: str=None,email: str=None):
        self.email = email
        self._password = password
        self.auth_token = auth_token
        self.project_guid = project_guid
        self.organization_guid = organization_guid
        self.environment = environment
        self.hosts = {}
        self.set_environment(environment)

        # login
        self._login()

    def _login(self) -> None:
        _rip_host = self.hosts.get("rip_host")
        try:
            if self.auth_token is not None:
                user = validate_auth_token(self)
                self.email=user["emailID"]
                return

            url = '{}{}'.format(_rip_host,LOGIN_ROUTE_PATH)
            response = httpx.post(url, json={'email': self.email, 'password': self._password}).json()
            if response['success']:
                self.auth_token = response['data']['token']
            else:
                raise AuthenticationError()
        except AuthenticationError as e:
            raise
        except Exception as e:
            raise

    def set_project(self, project) -> None:
        self.project_guid = project

    def set_organization(self,organization_guid) -> None:
        self.project_guid=None
        self.organization_guid = organization_guid

    def sync_client(self) -> Optional[Client]:
        if self.auth_token is None:
            raise LoggedOutError("You are not logged in. Run config.login() to login.")
        return Client(self)

    def async_client(self) -> Optional[AsyncClient]:
        if self.auth_token is None:
            raise LoggedOutError("You are not logged in. Run config.login() to login.")
        return AsyncClient(self)

    def set_environment(self, name: str) -> None:

        subdomain = PROD_ENVIRONMENT_SUBDOMAIN
        if name is not None:
            is_valid_env = name in NAMED_ENVIRONMENTS or name.startswith('pr')
            if not is_valid_env:
                raise ValidationError("Invalid environment")
            subdomain = STAGING_ENVIRONMENT_SUBDOMAIN
        else:
            name = "ga"

        core = 'https://{}apiserver.{}'.format(name, subdomain)
        rip = 'https://{}rip.{}'.format(name, subdomain)
        v2api = 'https://{}api.{}'.format(name, subdomain)

        self.hosts['environment'] = name
        self.hosts['core_api_host'] = core
        self.hosts['rip_host'] = rip
        self.hosts['v2api_host'] = v2api
