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
from dataclasses import dataclass

from rapyuta_io_sdk_v2.constants import (
    NAMED_ENVIRONMENTS,
    PROD_ENVIRONMENT_SUBDOMAIN,
    STAGING_ENVIRONMENT_SUBDOMAIN,
)
from rapyuta_io_sdk_v2.exceptions import (
    ValidationError,
)


@dataclass
class Configuration(object):
    email: str
    _password: str
    auth_token: str
    project_guid: str
    organization_guid: str
    environment: str = "ga"  # Default environment is prod

    def __init__(
        self,
        project_guid: str,
        organization_guid: str,
        password: str = None,
        auth_token: str = None,
        environment: str = None,
        email: str = None,
    ):
        self.email = email
        self._password = password
        self.auth_token = auth_token
        self.project_guid = project_guid
        self.organization_guid = organization_guid
        if (environment is not None): 
            self.environment = environment
        self.hosts = {}
        self.set_environment(environment)

    @staticmethod
    def from_file(self, file_path: str) -> "Configuration":
        with open(file_path, "r") as file:
            data = json.load(file)
            return Configuration(
                email=data.get("email"),
                password=data.get("password"),
                project_guid=data.get("project_guid"),
                organization_guid=data.get("organization_guid"),
                environment=data.get("environment"),
            )

    def set_project(self, project) -> None:
        self.project_guid = project

    def set_organization(self, organization_guid) -> None:
        self.organization_guid = organization_guid

    def set_environment(self, name: str) -> None:
        subdomain = PROD_ENVIRONMENT_SUBDOMAIN
        if name is not None:
            is_valid_env = name in NAMED_ENVIRONMENTS or name.startswith("pr")
            if not is_valid_env:
                raise ValidationError("Invalid environment")
            subdomain = STAGING_ENVIRONMENT_SUBDOMAIN
        else:
            name = "ga"

        rip = "https://{}rip.{}".format(name, subdomain)
        v2api = "https://{}api.{}".format(name, subdomain)

        self.hosts["environment"] = name
        self.hosts["rip_host"] = rip
        self.hosts["v2api_host"] = v2api
