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
"""Authentication, request headers, and environment endpoint configuration."""

from __future__ import annotations

import json
import os
import pathlib
from dataclasses import dataclass
from typing import TypedDict, Unpack

from rapyuta_io_sdk_v2.constants import (
    APP_NAME,
    NAMED_ENVIRONMENTS,
    STAGING_ENVIRONMENT_SUBDOMAIN,
)
from rapyuta_io_sdk_v2.exceptions import ValidationError
from rapyuta_io_sdk_v2.utils import get_default_app_dir


class RequestHeaderOptions(TypedDict, total=False):
    """Optional checksum and content type values for request headers."""

    x_checksum: str
    content_type: str


@dataclass
class Configuration:
    """Configuration class for the SDK."""

    email: str | None = None
    password: str | None = None
    auth_token: str | None = None
    project_guid: str | None = None
    organization_guid: str | None = None
    environment: str = "ga"  # Default environment is prod
    v2_api_host: str | None = None
    rip_host: str | None = None

    def __post_init__(self) -> None:
        # Normalize empty or whitespace-only host strings to None so that they
        # are treated the same as "not provided".
        """Normalize host overrides and resolve environment endpoints."""
        if isinstance(self.v2_api_host, str):
            self.v2_api_host = self.v2_api_host.strip() or None
        if isinstance(self.rip_host, str):
            self.rip_host = self.rip_host.strip() or None

        self.hosts = {}
        self.set_environment(self.environment)

    @classmethod
    def from_env(cls) -> Configuration:
        """Reserve environment loading for a future implementation."""
        raise NotImplementedError

    @classmethod
    def from_file(cls, file_path: str | None = None) -> Configuration:
        """Create a configuration object from a file.

        Args:
            file_path (str): Path to the file.

        Returns:
            Configuration: Configuration object.
        """
        if file_path is None:
            default_dir = get_default_app_dir(APP_NAME)
            file_path = str(pathlib.Path(default_dir) / "config.json")

        with pathlib.Path(file_path).open() as file:
            data = json.load(file)
            return cls(
                email=data.get("email_id"),
                password=data.get("password"),
                project_guid=data.get("project_id"),
                organization_guid=data.get("organization_id"),
                environment=data.get("environment"),
                auth_token=data.get("auth_token"),
            )

    # Preserve the positional signature used by existing SDK callers.
    def get_headers(  # noqa: PLR0913, PLR0917
        self,
        with_organization: bool = True,  # noqa: FBT001, FBT002
        organization_guid: str | None = None,
        with_project: bool = True,  # noqa: FBT001, FBT002
        project_guid: str | None = None,
        with_group: bool = False,  # noqa: FBT001, FBT002
        group_guid: str | None = None,
        **kwargs: Unpack[RequestHeaderOptions],
    ) -> dict[str, str]:
        """Build authentication, resource context, and optional request headers.

        Args:
            with_organization: Include the organization context when available.
            organization_guid: Override the configured organization GUID.
            with_project: Include the project context when available.
            project_guid: Override the configured project GUID.
            with_group: Include the supplied group context.
            group_guid: GUID identifying the group.
            **kwargs: Optional x_checksum and content_type header values.
        """
        headers = self._auth_headers()
        contexts = {
            "organizationguid": (
                with_organization,
                organization_guid or self.organization_guid,
            ),
            "project": (with_project, project_guid or self.project_guid),
            "groupguid": (with_group, group_guid),
        }
        headers.update(
            {
                key: value
                for key, (include, value) in contexts.items()
                if include and value
            }
        )
        headers.update(self._request_headers(kwargs))
        return headers

    def _auth_headers(self) -> dict[str, str]:
        token = self.auth_token.strip() if self.auth_token else None
        if not token:
            return {}
        if not token.lower().startswith("bearer "):
            token = f"Bearer {token}"
        return {"Authorization": token}

    @staticmethod
    def _request_headers(options: RequestHeaderOptions) -> dict[str, str]:
        values = {
            "X-Request-ID": os.getenv("REQUEST_ID"),
            "X-Checksum": options.get("x_checksum"),
            "Content-Type": options.get("content_type"),
        }
        return {key: value for key, value in values.items() if value}

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

    def set_environment(self, name: str | None = None) -> None:
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
            message = "invalid environment"
            raise ValidationError(message)

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
