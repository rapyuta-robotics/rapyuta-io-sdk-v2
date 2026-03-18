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
class Configuration:
    """Configuration class for the SDK."""

    email: str = None
    password: str = None
    auth_token: str = None
    project_guid: str = None
    organization_guid: str = None
    environment: str = "ga"  # Default environment is prod
    v2_api_host: str = None
    rip_host: str = None

    def __post_init__(self):
        # Normalize empty or whitespace-only host strings to None so that they
        # are treated the same as "not provided".
        if isinstance(self.v2_api_host, str):
            self.v2_api_host = self.v2_api_host.strip() or None
        if isinstance(self.rip_host, str):
            self.rip_host = self.rip_host.strip() or None

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

        with open(file_path) as file:
            data = json.load(file)
            return cls(
                email=data.get("email_id"),
                password=data.get("password"),
                project_guid=data.get("project_id"),
                organization_guid=data.get("organization_id"),
                environment=data.get("environment"),
                auth_token=data.get("auth_token"),
            )

    def get_headers(
        self,
        with_organization: bool = True,
        organization_guid: str | None = None,
        with_project: bool = True,
        project_guid: str | None = None,
        with_group: bool = False,
        group_guid: str | None = None,
        **kwargs,
    ) -> dict[str, str]:
        """Get the headers for the configuration.

        Args:
            with_organization (bool): Whether to include the organization headers. Defaults to True.
            organization_guid (str, optional): The organization guid. Defaults to None.
            with_project (bool): Whether to include the project headers. Defaults to True.
            project_guid (str, optional): The project guid. Defaults to None.
            with_group (bool): Whether to include the group headers. Defaults to False.
            group_guid (str, optional): The group guid. Defaults to None.
            **kwargs: Additional keyword arguments (e.g., x_checksum, content_type).

        Returns:
            dict: Headers for the configuration, including Authorization, organizationguid,
                  project, groupguid, and other custom headers.
        """
        auth_value = self.auth_token.strip() if self.auth_token else None
        if auth_value and not auth_value.lower().startswith("bearer "):
            auth_value = f"Bearer {auth_value}"
        headers = {"Authorization": auth_value} if auth_value else {}

        organization_guid = organization_guid or self.organization_guid
        if with_organization and organization_guid:
            headers["organizationguid"] = organization_guid

        project_guid = project_guid or self.project_guid
        if with_project and project_guid:
            headers["project"] = project_guid

        if with_group and group_guid:
            headers["groupguid"] = group_guid

        custom_client_request_id = os.getenv("REQUEST_ID")
        if custom_client_request_id:
            headers["X-Request-ID"] = custom_client_request_id

        x_checksum = kwargs.get("x_checksum", None)
        if x_checksum:
            headers["X-Checksum"] = x_checksum

        content_type = kwargs.get("content_type", None)
        if content_type:
            headers["Content-Type"] = content_type

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

        Populates ``hosts`` with the correct URLs for *name*.  If the caller
        provided ``v2_api_host`` or ``rip_host`` at construction time those
        values are used as-is; otherwise the canonical defaults for the
        environment are applied.  Calling this method again with a different
        environment name always recomputes the default slots so that switching
        environments produces correct URLs.

        Args:
            name (str): Name of the environment. Defaults to ``"ga"`` (production).

        Raises:
            ValidationError: If *name* is not a recognised environment.
        """
        name = name or "ga"

        if (
            name not in ("local", "ga")
            and name not in NAMED_ENVIRONMENTS
            and not name.startswith("pr")
        ):
            raise ValidationError("invalid environment")

        self.hosts["environment"] = name

        if name == "local":
            self.hosts["v2api_host"] = self.v2_api_host or (
                os.getenv("LOCAL_V2API_HOST") or "http://gateway/io"
            )
            self.hosts["rip_host"] = self.rip_host or (
                os.getenv("LOCAL_RIP_HOST") or "http://rip"
            )
        elif name == "ga":
            self.hosts["rip_host"] = (
                self.rip_host or "https://garip.apps.okd4v2.prod.rapyuta.io"
            )
            self.hosts["v2api_host"] = self.v2_api_host or "https://api.rapyuta.io"
        else:
            # Staging environments: qa, dev, pr*
            self.hosts["rip_host"] = (
                self.rip_host or f"https://{name}rip.{STAGING_ENVIRONMENT_SUBDOMAIN}"
            )
            self.hosts["v2api_host"] = (
                self.v2_api_host or f"https://{name}api.{STAGING_ENVIRONMENT_SUBDOMAIN}"
            )
