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
import os
from dataclasses import dataclass

from rapyuta_io_sdk_v2.constants import (
    APP_NAME,
    NAMED_ENVIRONMENTS,
    STAGING_ENVIRONMENT_SUBDOMAIN,
)
from rapyuta_io_sdk_v2.exceptions import ValidationError
from rapyuta_io_sdk_v2.utils import get_default_app_dir


@dataclass
class Configuration(object):
    """Configuration class for the SDK."""

    email: str = None
    password: str = None
    auth_token: str = None
    project_guid: str = None
    organization_guid: str = None
    environment: str = "ga"  # Default environment is prod

    def __post_init__(self):
        self.hosts = {}
        self.set_environment(self.environment)

    @classmethod
    def from_env(cls) -> "Configuration":
        raise NotImplementedError

    @classmethod
    def from_file(cls, file_path: str = None) -> "Configuration":
        """Create a configuration object from a file.

        Args:
            file_path (str): Path to the file.

        Returns:
            Configuration: Configuration object.
        """
        if file_path is None:
            default_dir = get_default_app_dir(APP_NAME)
            file_path = os.path.join(default_dir, "config.json")

        with open(file_path, "r") as file:
            data = json.load(file)
            return cls(
                email=data.get("email"),
                password=data.get("password"),
                project_guid=data.get("project_id"),
                organization_guid=data.get("organization_id"),
                environment=data.get("environment"),
                auth_token=data.get("auth_token"),
            )

    def get_headers(
        self,
        with_organization: bool = True,
        organization_guid: str = None,
        with_project: bool = True,
        project_guid: str = None,
    ) -> dict:
        """Get the headers for the configuration.

        Args:
            organization_guid (str): The organization guid.
            with_project (bool): Whether to include the project headers.
            project_guid (str): The project guid.

        Returns:
            dict: Headers for the configuration.
        """
        auth_value = self.auth_token.strip() if self.auth_token else None
        if auth_value and not auth_value.lower().startswith("bearer "):
            auth_value = f"Bearer {auth_value}"
        headers = {"Authorization": auth_value} if auth_value else {}

        organization_guid = organization_guid or self.organization_guid
        if with_organization and organization_guid:
            headers["organizationguid"] = organization_guid

        project_guid = project_guid or self.project_guid
        if with_project and project_guid is not None:
            headers["project"] = project_guid

        custom_client_request_id = os.getenv("REQUEST_ID")
        if custom_client_request_id:
            headers["X-Request-ID"] = custom_client_request_id

        return headers

    def set_project(self, project_guid: str) -> None:
        """Set the project for the configuration.

        Args:
            project_guid (str): The project guid to be set.
        """
        self.project_guid = project_guid

    def set_organization(self, organization_guid: str) -> None:
        """Set the organization for the configuration.

        Args:
            organization_guid (str): The organization guid to be set.
        """
        self.organization_guid = organization_guid

    def set_environment(self, name: str = None) -> None:
        """Set the environment for the configuration.

        Args:
            name (str): Name of the environment, default is ga.

        Raises:
            ValidationError: If the environment is invalid.
        """
        name = name or "ga"  # Default to prod.

        if name == "local":
            # Allow overriding the local API host via environment variables.
            # Priority: LOCAL_V2API_HOST > default fallback.
            override_host = (
                os.getenv("LOCAL_V2API_HOST")
                or "http://gateway/io"
            )
            self.hosts["environment"] = name
            self.hosts["v2api_host"] = override_host
            return

        if name == "ga":
            self.hosts["environment"] = "ga"
            self.hosts["rip_host"] = "https://garip.apps.okd4v2.prod.rapyuta.io"
            self.hosts["v2api_host"] = "https://api.rapyuta.io"
            return

        if not (name in NAMED_ENVIRONMENTS or name.startswith("pr")):
            raise ValidationError("invalid environment")

        self.hosts["environment"] = name
        self.hosts["rip_host"] = f"https://{name}rip.{STAGING_ENVIRONMENT_SUBDOMAIN}"
        self.hosts["v2api_host"] = f"https://{name}api.{STAGING_ENVIRONMENT_SUBDOMAIN}"
