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

import httpx
from munch import Munch
import platform
from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.utils import (
    handle_and_munchify_response,
    handle_auth_token,
)


class Client(object):
    """Client class offers sync client for the v2 APIs.

    Args:
        config (Configuration): Configuration object.
        **kwargs: Additional keyword arguments.
    """

    def __init__(self, config: Configuration = None, **kwargs):
        self.config = config or Configuration()
        timeout = kwargs.get("timeout", 10)
        self.c = httpx.Client(
            timeout=timeout,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=5,
                keepalive_expiry=30,
            ),
            headers={
                "User-Agent": (
                    "rio-sdk-v2;N/A;{};{};{} {}".format(
                        platform.processor() or platform.machine(),
                        platform.system(),
                        platform.release(),
                        platform.version(),
                    )
                )
            },
        )

    @handle_auth_token
    def login(
        self,
        email: str = None,
        password: str = None,
        environment: str = "ga",
    ) -> str:
        """Get the authentication token for the user.

        Args:
            email (str)
            password (str)
            environment (str)

        Returns:
            str: authentication token
        """
        if email is None and password is None and self.config is None:
            raise ValueError("email and password are required")

        if self.config is None:
            self.config = Configuration(
                email=email, password=password, environment=environment
            )

        rip_host = self.config.hosts.get("rip_host")

        return self.c.post(
            url=f"{rip_host}/user/login",
            headers={"Content-Type": "application/json"},
            json={
                "email": email or self.config.email,
                "password": password or self.config.password,
            },
        )

    @handle_and_munchify_response
    def logout(self, token: str = None) -> None:
        """Expire the authentication token.

        Args:
            token (str): The token to expire.
        """
        rip_host = self.config.hosts.get("rip_host")

        if token is None:
            token = self.config.auth_token

        return self.c.post(
            url=f"{rip_host}/user/logout",
            headers={"Content-Type": "application/json"},
            json={"token": token},
        )

    @handle_auth_token
    def refresh_token(self, token: str = None) -> str:
        """Refresh the authentication token.

        Args:
            token (str): The token to refresh.

        Returns:
            str: The refreshed token.
        """
        rip_host = self.config.hosts.get("rip_host")

        if token is None:
            token = self.config.auth_token

        return self.c.post(
            url=f"{rip_host}/refreshtoken",
            headers={"Content-Type": "application/json"},
            json={"token": token},
        )

    def set_organization(self, organization_guid: str) -> None:
        """Set the organization GUID.

        Args:
            organization_guid (str): Organization GUID
        """
        self.config.set_organization(organization_guid)

    def set_project(self, project_guid: str) -> None:
        """Set the project GUID.

        Args:
            project_guid (str): Project GUID
        """
        self.config.set_project(project_guid)

    # -------------------Project-------------------
    @handle_and_munchify_response
    def get_project(self, project_guid: str = None, **kwargs) -> Munch:
        """Get a project by its GUID.

        If no project or organization GUID is provided,
        the default project and organization GUIDs will
        be picked from the current configuration.

        Args:
            project_guid (str): user provided project GUID or config project GUID

        Raises:
            ValueError: If organization_guid or project_guid is None

        Returns:
            Munch: Project details as a Munch object.
        """
        if project_guid is None:
            project_guid = self.config.project_guid

        if not project_guid:
            raise ValueError("project_guid is required")

        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )

    @handle_and_munchify_response
    def list_projects(self, cont: int = 0, limit: int = 50, **kwargs) -> Munch:
        """List all projects.

        Returns:
            Munch: List of projects as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/projects/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            params={"continue": cont, "limit": limit},
        )

        return response

    @handle_and_munchify_response
    def create_project(self, body: object, **kwargs) -> Munch:
        """Create a new project.

        Args:
            body (object): Project details

        Returns:
            Munch: Project details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.post(
            url=f"{v2api_host}/v2/projects/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def update_project(self, body: object, project_guid: str = None, **kwargs) -> Munch:
        """Update a project by its GUID.

        Returns:
            Munch: Project details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.put(
            url=f"{v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def delete_project(self, project_guid: str, **kwargs) -> Munch:
        """Delete a project by its GUID.

        Args:
            project_guid (str): Project GUID

        Returns:
            Munch: Project details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.delete(
            url=f"{v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )

    @handle_and_munchify_response
    def update_project_owner(
        self, body: object, project_guid: str = None, **kwargs
    ) -> Munch:
        """Update the owner of a project by its GUID.

        Returns:
            Munch: Project details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        project_guid = project_guid or self.config.project_guid

        return self.c.put(
            url=f"{v2api_host}/v2/projects/{project_guid}/owner/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    # -------------------Package-------------------
    @handle_and_munchify_response
    def list_packages(self, cont: int = 0, limit: int = 10, **kwargs) -> Munch:
        """List all packages in a project.

        Returns:
            Munch: List of packages as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/packages/",
            headers=self.config.get_headers(**kwargs),
            params={"continue": cont, "limit": limit},
        )

    @handle_and_munchify_response
    def create_package(self, body: object, **kwargs) -> Munch:
        """Create a new package.

        The Payload is the JSON format of the Package Manifest.
        For a documented example, run the rio explain package command.

        Returns:
            Munch: Package details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.post(
            url=f"{v2api_host}/v2/packages/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def get_package(
        self, name: str, project_guid: str = None, version: str = None, **kwargs
    ) -> Munch:
        """Get a package by its name.

        Returns:
            Munch: Package details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/packages/{name}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            params={"version": version},
        )

    @handle_and_munchify_response
    def delete_package(self, name: str, **kwargs) -> Munch:
        """Delete a package by its name.

        Returns:
            Munch: Package details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.delete(
            url=f"{v2api_host}/v2/packages/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    # -------------------Deployment-------------------
    @handle_and_munchify_response
    def list_deployments(self, cont: int = 0, limit: int = 50, **kwargs) -> Munch:
        """List all deployments in a project.

        Args:
            cont (int): Start index of deployments
            limit (int): Number of deployments to list

        Returns:
            Munch: List of deployments as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/deployments/",
            headers=self.config.get_headers(**kwargs),
            params={"continue": cont, "limit": limit},
        )

    @handle_and_munchify_response
    def create_deployment(self, body: object, **kwargs) -> Munch:
        """Create a new deployment.

        Args:
            body (object): Deployment details

        Returns:
            Munch: Deployment details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.post(
            url=f"{v2api_host}/v2/deployments/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def get_deployment(self, name: str, **kwargs) -> Munch:
        """Get a deployment by its name.

        Returns:
            Munch: Deployment details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    def update_deployment(self, name: str, body: object, **kwargs) -> Munch:
        """Update a deployment by its name.

        Returns:
            Munch: Deployment details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.put(
            url=f"{v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def delete_deployment(self, name: str, **kwargs) -> Munch:
        """Delete a deployment by its name.

        Returns:
            Munch: Deployment details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.delete(
            url=f"{v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    # -------------------Disks-------------------
    @handle_and_munchify_response
    def list_disks(self, cont: int = 0, limit: int = 50, **kwargs) -> Munch:
        """List all disks in a project.

        Returns:
            Munch: List of disks as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/disks/",
            headers=self.config.get_headers(**kwargs),
            params={"continue": cont, "limit": limit},
        )

    @handle_and_munchify_response
    def get_disk(self, name: str, **kwargs) -> Munch:
        """Get a disk by its name.

        Args:
            name (str): Disk name

        Returns:
            Munch: Disk details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/disks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    def create_disk(self, body: str, **kwargs) -> Munch:
        """Create a new disk.

        Returns:
            Munch: Disk details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.post(
            url=f"{v2api_host}/v2/disks/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def delete_disk(self, name: str, **kwargs) -> Munch:
        """Delete a disk by its name.

        Args:
            name (str): Disk name

        Returns:
            Munch: Disk details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.delete(
            url=f"{v2api_host}/v2/disks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    # -------------------Static Routes-------------------
    @handle_and_munchify_response
    def list_staticroutes(self, cont: int = 0, limit: int = 0, **kwargs) -> Munch:
        """List all static routes in a project.

        Returns:
            Munch: List of static routes as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/staticroutes/",
            headers=self.config.get_headers(**kwargs),
            params={"continue": cont, "limit": limit},
        )

    @handle_and_munchify_response
    def create_staticroute(self, body: object, **kwargs) -> Munch:
        """Create a new static route.

        Returns:
            Munch: Static route details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.post(
            url=f"{v2api_host}/v2/staticroutes/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def get_staticroute(self, name: str, **kwargs) -> Munch:
        """Get a static route by its name.

        Args:
            name (str): Static route name

        Returns:
            Munch: Static route details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    def update_staticroute(self, name: str, body: object, **kwargs) -> Munch:
        """Update a static route by its name.

        Args:
            name (str): Static route name
            body (dict): Update details

        Returns:
            Munch: Static route details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.put(
            url=f"{v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def delete_staticroute(self, name: str, **kwargs) -> Munch:
        """Delete a static route by its name.

        Args:
            name (str): Static route name

        Returns:
            Munch: Static route details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.delete(
            url=f"{v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    # -------------------Networks-------------------
    @handle_and_munchify_response
    def list_networks(self, cont: int = 0, limit: int = 0, **kwargs) -> Munch:
        """List all networks in a project.

        Returns:
            Munch: List of networks as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/networks/",
            headers=self.config.get_headers(**kwargs),
            params={"continue": cont, "limit": limit},
        )

    @handle_and_munchify_response
    def create_network(self, body: object, **kwargs) -> Munch:
        """Create a new network.

        Returns:
            Munch: Network details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.post(
            url=f"{v2api_host}/v2/networks/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def get_network(self, name: str, **kwargs) -> Munch:
        """Get a network by its name.

        Args:
            name (str): Network name

        Returns:
            Munch: Network details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/networks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    def delete_network(self, name: str, **kwargs) -> Munch:
        """Delete a network by its name.

        Args:
            name (str): Network name

        Returns:
            Munch: Network details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.delete(
            url=f"{v2api_host}/v2/networks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    # -------------------Secrets-------------------
    @handle_and_munchify_response
    def list_secrets(self, cont: int = 0, limit: int = 50, **kwargs) -> Munch:
        """List all secrets in a project.

        Returns:
            Munch: List of secrets as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/secrets/",
            headers=self.config.get_headers(**kwargs),
            params={"continue": cont, "limit": limit},
        )

    @handle_and_munchify_response
    def create_secret(self, body: object, **kwargs) -> Munch:
        """Create a new secret.

        Returns:
            Munch: Secret details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.post(
            url=f"{v2api_host}/v2/secrets/",
            headers=self.config.get_headers(*kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def get_secret(self, name: str, **kwargs) -> Munch:
        """Get a secret by its name.

        Args:
            name (str): Secret name

        Returns:
            Munch: Secret details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    def update_secret(self, name: str, body: object, **kwargs) -> Munch:
        """Update a secret by its name.

        Args:
            name (str): Secret name
            body (dict): Update details

        Returns:
            Munch: Secret details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.put(
            url=f"{v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def delete_secret(self, name: str, **kwargs) -> Munch:
        """Delete a secret by its name.

        Args:
            name (str): Secret name

        Returns:
            Munch: Secret details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.delete(
            url=f"{v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    # -------------------Config Trees-------------------
    @handle_and_munchify_response
    def list_configtrees(self, cont: int = 0, limit: int = 50, **kwargs) -> Munch:
        """List all config trees in a project.

        Returns:
            Munch: List of config trees as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/configtrees/",
            headers=self.config.get_headers(**kwargs),
            params={"continue": cont, "limit": limit},
        )

    @handle_and_munchify_response
    def create_configtree(self, body: object, **kwargs) -> Munch:
        """Create a new config tree.

        Args:
            body (object): Config tree details

        Returns:
            Munch: Config tree details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.post(
            url=f"{v2api_host}/v2/configtrees/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def get_configtree(self, name: str, **kwargs) -> Munch:
        """Get a config tree by its name.

        Args:
            name (str): Config tree name

        Returns:
            Munch: Config tree details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    def set_configtree_revision(
        self, name: str, configtree: object, project_guid: str = None, **kwargs
    ) -> Munch:
        """Set a config tree revision.

        Args:
            name (str): Config tree name
            configtree (object): Config tree details
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            Munch: Config tree details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.put(
            url=f"{v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=configtree,
        )

    @handle_and_munchify_response
    def update_configtree(self, name: str, body: object, **kwargs) -> Munch:
        """Update a config tree by its name.

        Args:
            name (str): Config tree name
            body (dict): Update details

        Returns:
            Munch: Config tree details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.put(
            url=f"{v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def delete_configtree(self, name: str, **kwargs) -> Munch:
        """Delete a config tree by its name.

        Args:
            name (str): Config tree name

        Returns:
            Munch: Config tree details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.delete(
            url=f"{v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    def list_revisions(
        self,
        name: str,
        cont: int = 0,
        limit: int = 50,
        committed: bool = False,
        **kwargs,
    ) -> Munch:
        """List all revisions of a config tree.

        Args:
            name (str): Config tree name
            cont (int, optional): Continue param . Defaults to 0.
            limit (int, optional): Limit param . Defaults to 50.
            committed (bool, optional): Committed. Defaults to False.

        Returns:
            Munch: List of revisions as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/configtrees/{name}/revisions/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "committed": committed,
            },
        )

    @handle_and_munchify_response
    def create_revision(
        self, name: str, body: object, project_guid: str = None, **kwargs
    ) -> Munch:
        """Create a new revision.

        Args:
            name (str): Config tree name
            body (object): Revision details
            project_guid (str): Project GUID (optional)

        Returns:
            Munch: Revision details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.post(
            url=f"{v2api_host}/v2/configtrees/{name}/revisions/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def put_keys_in_revision(
        self, name: str, revision_id: str, configValues: list[(object)], **kwargs
    ) -> Munch:
        """Put keys in a revision.

        Returns:
            Munch: Revision details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.put(
            url=f"{v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/keys/",
            headers=self.config.get_headers(**kwargs),
            json=configValues,
        )

    @handle_and_munchify_response
    def commit_revision(
        self,
        name: str,
        revision_id: str,
        configTreeRevision: object,
        project_guid: str = None,
        **kwargs,
    ) -> Munch:
        """Commit a revision.

        Returns:
            Munch: Revision details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.patch(
            url=f"{v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/commit/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=configTreeRevision,
        )

    @handle_and_munchify_response
    def get_key_in_revision(
        self, name: str, revision_id: str, key: str, project_guid: str = None, **kwargs
    ) -> Munch:
        """Get a key in a revision.

        Args:
            name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            Munch: Key details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
        )

    @handle_and_munchify_response
    def put_key_in_revision(
        self, name: str, revision_id: str, key: str, project_guid: str = None, **kwargs
    ) -> Munch:
        """Put a key in a revision.

        Args:
            name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            Munch: Key details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.put(
            url=f"{v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
        )

    @handle_and_munchify_response
    def delete_key_in_revision(
        self, name: str, revision_id: str, key: str, project_guid: str = None, **kwargs
    ) -> Munch:
        """Delete a key in a revision.

        Args:
            name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            Munch: Key details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.delete(
            url=f"{v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
        )

    @handle_and_munchify_response
    def rename_key_in_revision(
        self,
        name: str,
        revision_id: str,
        key: str,
        configKeyRename: object,
        project_guid: str = None,
        **kwargs,
    ) -> Munch:
        """Rename a key in a revision.

        Args:
            name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            configKeyRename (object): Key rename details
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            Munch: Key details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.patch(
            url=f"{v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=configKeyRename,
        )
