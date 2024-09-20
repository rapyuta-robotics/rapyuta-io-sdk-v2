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
from rapyuta_io_sdk_v2.async_client import AsyncClient
from rapyuta_io_sdk_v2.client import Client
from rapyuta_io_sdk_v2.constants import LOGIN_ROUTE_PATH, NAMED_ENVIRONMENTS, STAGING_ENVIRONMENT_SUBDOMAIN, PROD_ENVIRONMENT_SUBDOMAIN
from rapyuta_io_sdk_v2.exceptions import ValidationError, AuthenticationError, LoggedOutError, UnauthorizedError
import httpx

from rapyuta_io_sdk_v2.utils import validate_auth_token


class Configuration(object):

    def __init__(self, email: str, password: str, project_guid: str, organization_guid: str,auth_token: str=None, environment: str=None):
        self.email = email
        self.password = password
        self.auth_token = auth_token
        self.project_guid = project_guid
        self.organization_guid = organization_guid
        self.environment = environment
        self.hosts = {}
        self._configure_environment(environment)

    def login(self):
        _rip_host = self.hosts.get("rip_host")

        if self.auth_token is not None:
            is_valid: bool = validate_auth_token(self)
            if is_valid:
                return
        try:
            url = '{}{}'.format(_rip_host,LOGIN_ROUTE_PATH)
            response = httpx.post(url, json={'email': self.email, 'password': self.password}).json()
            if response['success']:
                self.auth_token = response['data']['token']
                return
            raise AuthenticationError()
        except AuthenticationError as e:
            raise
        except Exception as e:
            raise

    def logout(self):
        self.email=None
        self.auth_token=None
        self.project_guid=None
        self.organization_guid=None
        self.environment=None

    def set_project(self, project):
        self.project_guid = project

    def set_organization(self,organization_guid):
        self.organization_guid = organization_guid

    def sync_client(self):
        if self.auth_token is None:
            raise LoggedOutError("You are not logged in. Run config.login() to login.")

        # validate the auth_token
        return Client(self)

    def async_client(self):
        if self.auth_token is None:
            raise LoggedOutError("You are not logged in. Run config.login() to login.")

        # validate the auth_token
        return AsyncClient(self)

    def _configure_environment(self, name: str) -> None:

        subdomain = PROD_ENVIRONMENT_SUBDOMAIN
        if name is not None:
            is_valid_env = name in NAMED_ENVIRONMENTS or name.startswith('pr')
            if not is_valid_env:
                raise ValidationError("Invalid environment")
            subdomain = STAGING_ENVIRONMENT_SUBDOMAIN
        else:
            name = "ga"

        catalog = 'https://{}catalog.{}'.format(name, subdomain)
        core = 'https://{}apiserver.{}'.format(name, subdomain)
        rip = 'https://{}rip.{}'.format(name, subdomain)
        v2api = 'https://{}api.{}'.format(name, subdomain)

        self.hosts['environment'] = name
        self.hosts['catalog_host'] = catalog
        self.hosts['core_api_host'] = core
        self.hosts['rip_host'] = rip
        self.hosts['v2api_host'] = v2api
