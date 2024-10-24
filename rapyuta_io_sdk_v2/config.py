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
import os

from rapyuta_io_sdk_v2.constants import (
    NAMED_ENVIRONMENTS,
    PROD_ENVIRONMENT_SUBDOMAIN,
    STAGING_ENVIRONMENT_SUBDOMAIN,
)
from rapyuta_io_sdk_v2.utils import get_default_app_dir
from rapyuta_io_sdk_v2.exceptions import ValidationError


@dataclass
class Configuration(object):
    email: str = None
    _password: str = None
    auth_token: str = None
    project_guid: str = None
    organization_guid: str = None
    environment: str = "ga"  # Default environment is prod

    def __post_init__(self):
        self.hosts = {}
        self.set_environment(self.environment)

    @staticmethod
    def from_file(file_path: str) -> "Configuration":
        """Create a configuration object from a file.

        Args:
            file_path (str): Path to the file.

        Returns:
            Configuration: Configuration object.
        """
        if file_path is None:
            app_name = "rio_cli"
            default_dir = get_default_app_dir(app_name)
            file_path = os.path.join(default_dir, "config.json")

        with open(file_path, "r") as file:
            data = json.load(file)
            return Configuration(
                email=data.get("email"),
                _password=data.get("password"),
                project_guid=data.get("project_guid"),
                organization_guid=data.get("organization_guid"),
                environment=data.get("environment"),
                auth_token=data.get("auth_token"),
            )

    def set_project(self, project_guid: str) -> None:
        self.project_guid = project_guid

    def set_organization(self, organization_guid: str) -> None:
        self.organization_guid = organization_guid

    def set_environment(self, name: str = None) -> None:
        """Set the environment for the configuration.

        Args:
            name (str): Name of the environment, default is ga.

        Raises:
            ValidationError: If the environment is invalid.
        """
        subdomain = PROD_ENVIRONMENT_SUBDOMAIN
        if self.environment is not None:
            name = self.environment
        if name is not None:
            if not (name in NAMED_ENVIRONMENTS or name.startswith("pr")):
                raise ValidationError("Invalid environment")
            subdomain = STAGING_ENVIRONMENT_SUBDOMAIN
        name = name or "ga"

        rip = "https://{}rip.{}".format(name, subdomain)
        v2api = "https://{}api.{}".format(name, subdomain)

        self.hosts["environment"] = name
        self.hosts["rip_host"] = rip
        self.hosts["v2api_host"] = v2api
