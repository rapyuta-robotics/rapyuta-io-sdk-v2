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

import platform

import httpx
from munch import Munch

from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.utils import handle_and_munchify_response, handle_server_errors


class AsyncClient(object):
    """AsyncClient class for the SDK."""

    def __init__(self, config=None, **kwargs):
        self.config = config or Configuration()
        timeout = kwargs.get("timeout", 10)
        self.c = httpx.AsyncClient(
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
        self.sync_client = httpx.Client(
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
        self.rip_host = self.config.hosts.get("rip_host")
        self.v2api_host = self.config.hosts.get("v2api_host")

    def get_auth_token(self, email: str, password: str) -> str:
        """Get the authentication token for the user.

        Args:
            email (str)
            password (str)

        Returns:
            str: authentication token
        """
        response = self.sync_client.post(
            url=f"{self.rip_host}/user/login",
            headers={"Content-Type": "application/json"},
            json={
                "email": email,
                "password": password,
            },
        )
        handle_server_errors(response)
        return response.json()["data"].get("token")

    def login(
        self,
        email: str,
        password: str,
        environment: str = "ga",
    ) -> None:
        """Get the authentication token for the user.

        Args:
            email (str)
            password (str)
            environment (str)

        Returns:
            str: authentication token
        """

        token = self.get_auth_token(email, password)
        self.config.auth_token = token

    @handle_and_munchify_response
    def logout(self, token: str = None) -> Munch:
        """Expire the authentication token.

        Args:
            token (str): The token to expire.
        """

        if token is None:
            token = self.config.auth_token

        return self.sync_client.post(
            url=f"{self.rip_host}/user/logout",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

    async def refresh_token(self, token: str = None) -> str:
        if token is None:
            token = self.config.auth_token

        response = await self.c.post(
            url=f"{self.rip_host}/refreshtoken",
            headers={"Content-Type": "application/json"},
            json={"token": token},
        )
        return response.json()["data"].get("token")

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

    # ----------------- Projects -----------------
    @handle_and_munchify_response
    async def list_projects(
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] = None,
        status: list[str] = None,
        organizations: list[str] = None,
        **kwargs,
    ) -> Munch:
        """List all projects.

        Args:
            cont (int, optional): Continue. async defaults to 0.
            limit (int, optional): Limit. async defaults to 50.

        Returns:
            Munch: List of projects
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/projects/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "status": status,
                "organizations": organizations,
                "labelSelector": label_selector,
            },
        )

    @handle_and_munchify_response
    async def get_project(self, project_guid: str = None, **kwargs) -> Munch:
        """Get a project by its GUID.

        If no project or organization GUID is provided,
        the async default project and organization GUIDs will
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

        return await self.c.get(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )

    @handle_and_munchify_response
    async def create_project(self, body: dict, **kwargs) -> Munch:
        """Create a new project.

        Args:
            body (object): Project details

        Returns:
            Munch: Project details as a Munch object.
        """

        return await self.c.post(
            url=f"{self.v2api_host}/v2/projects/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=body,
        )

    @handle_and_munchify_response
    async def update_project(
        self, body: dict, project_guid: str = None, **kwargs
    ) -> Munch:
        """Update a project by its GUID.

        Returns:
            Munch: Project details as a Munch object.
        """

        return await self.c.put(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=body,
        )

    @handle_and_munchify_response
    async def delete_project(self, project_guid: str, **kwargs) -> Munch:
        """Delete a project by its GUID.

        Args:
            project_guid (str): Project GUID

        Returns:
            Munch: Project details as a Munch object.
        """

        return await self.c.delete(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )

    @handle_and_munchify_response
    async def update_project_owner(
        self, body: dict, project_guid: str = None, **kwargs
    ) -> Munch:
        """Update the owner of a project by its GUID.

        Returns:
            Munch: Project details as a Munch object.
        """
        project_guid = project_guid or self.config.project_guid

        return await self.c.put(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/owner/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    # -------------------Package-------------------
    @handle_and_munchify_response
    async def list_packages(
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] = None,
        name: str = None,
        regions: list[str] = None,
        **kwargs,
    ) -> Munch:
        """List all packages in a project.

        Returns:
            Munch: List of packages as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/packages/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "labelSelector": label_selector,
                "name": name,
                "regions": regions,
            },
        )

    @handle_and_munchify_response
    async def create_package(self, body: dict, **kwargs) -> Munch:
        """Create a new package.

        The Payload is the JSON format of the Package Manifest.
        For a documented example, run the rio explain package command.

        Returns:
            Munch: Package details as a Munch object.
        """

        return await self.c.post(
            url=f"{self.v2api_host}/v2/packages/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    async def get_package(
        self, name: str, project_guid: str = None, version: str = None, **kwargs
    ) -> Munch:
        """Get a package by its name.

        Returns:
            Munch: Package details as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/packages/{name}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            params={"version": version},
        )

    @handle_and_munchify_response
    async def delete_package(self, name: str, **kwargs) -> Munch:
        """Delete a package by its name.

        Returns:
            Munch: Package details as a Munch object.
        """

        return await self.c.delete(
            url=f"{self.v2api_host}/v2/packages/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    # -------------------Deployment-------------------
    @handle_and_munchify_response
    async def list_deployments(
        self,
        cont: int = 0,
        dependencies: bool = False,
        deviceName: str = None,
        guids: list[str] = None,
        label_selector: list[str] = None,
        limit: int = 50,
        name: str = None,
        names: list[str] = None,
        packageName: str = None,
        packageVersion: str = None,
        phases: list[str] = None,
        regions: list[str] = None,
        **kwargs,
    ) -> Munch:
        """List all deployments in a project.

        Args:
            cont (int, optional): Start index of deployments. Defaults to 0.
            dependencies (bool, optional): Filter by dependencies. Defaults to False.
            deviceName (str, optional): Filter deployments by device name. Defaults to None.
            guids (list[str], optional): Filter by GUIDs. Defaults to None.
            label_selector (list[str], optional): Define labelSelector to get deployments from. Defaults to None.
            limit (int, optional): Number of deployments to list. Defaults to 50.
            name (str, optional): Define name to get deployments from. Defaults to None.
            names (list[str], optional): Define names to get deployments from. Defaults to None.
            packageName (str, optional): Filter by package name. Defaults to None.
            packageVersion (str, optional): Filter by package version. Defaults to None.
            phases (list[str], optional): Filter by phases. Available values : InProgress, Provisioning, Succeeded, FailedToUpdate, FailedToStart, Stopped. Defaults to None.
            regions (list[str], optional): Filter by regions. Defaults to None.

        Returns:
            Munch: List of deployments as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/deployments/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "dependencies": dependencies,
                "deviceName": deviceName,
                "guids": guids,
                "labelSelector": label_selector,
                "name": name,
                "names": names,
                "packageName": packageName,
                "packageVersion": packageVersion,
                "phases": phases,
                "regions": regions,
            },
        )

    @handle_and_munchify_response
    async def create_deployment(self, body: dict, **kwargs) -> Munch:
        """Create a new deployment.

        Args:
            body (object): Deployment details

        Returns:
            Munch: Deployment details as a Munch object.
        """

        return await self.c.post(
            url=f"{self.v2api_host}/v2/deployments/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    async def get_deployment(self, name: str, **kwargs) -> Munch:
        """Get a deployment by its name.

        Returns:
            Munch: Deployment details as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    async def update_deployment(self, name: str, body: dict, **kwargs) -> Munch:
        """Update a deployment by its name.

        Returns:
            Munch: Deployment details as a Munch object.
        """

        return await self.c.put(
            url=f"{self.v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    async def delete_deployment(self, name: str, **kwargs) -> Munch:
        """Delete a deployment by its name.

        Returns:
            Munch: Deployment details as a Munch object.
        """

        return await self.c.delete(
            url=f"{self.v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    async def get_deployment_graph(self, name: str, **kwargs) -> Munch:
        """Get a deployment graph by its name. [Experimental]

        Returns:
            Munch: Deployment graph as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/deployments/{name}/graph/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    async def get_deployment_history(
        self, name: str, guid: str = None, **kwargs
    ) -> Munch:
        """Get a deployment history by its name.

        Returns:
            Munch: Deployment history as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/deployments/{name}/history/",
            headers=self.config.get_headers(**kwargs),
            params={"guid": guid},
        )

    # -------------------Disks-------------------
    @handle_and_munchify_response
    async def list_disks(
        self,
        cont: int = 0,
        label_selector: list[str] = None,
        limit: int = 50,
        name: str = None,
        names: list[str] = None,
        regions: list[str] = None,
        status: list[str] = None,
        **kwargs,
    ) -> Munch:
        """List all disks in a project.

        Args:
            cont (int, optional): Start index of disks. Defaults to 0.
            label_selector (list[str], optional): Define labelSelector to get disks from. Defaults to None.
            limit (int, optional): Number of disks to list. Defaults to 50.
            name (str, optional): Define name to get disks from. Defaults to None.
            names (list[str], optional): Define names to get disks from. Defaults to None.
            regions (list[str], optional): Define regions to get disks from. Defaults to None.
            status (list[str], optional): Define status to get disks from. Available values : Available, Bound, Released, Failed, Pending.Defaults to None.


        Returns:
            Munch: List of disks as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/disks/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "labelSelector": label_selector,
                "name": name,
                "names": names,
                "regions": regions,
                "status": status,
            },
        )

    @handle_and_munchify_response
    async def get_disk(self, name: str, **kwargs) -> Munch:
        """Get a disk by its name.

        Args:
            name (str): Disk name

        Returns:
            Munch: Disk details as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/disks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    async def create_disk(self, body: str, **kwargs) -> Munch:
        """Create a new disk.

        Returns:
            Munch: Disk details as a Munch object.
        """

        return await self.c.post(
            url=f"{self.v2api_host}/v2/disks/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    async def delete_disk(self, name: str, **kwargs) -> Munch:
        """Delete a disk by its name.

        Args:
            name (str): Disk name

        Returns:
            Munch: Disk details as a Munch object.
        """

        return await self.c.delete(
            url=f"{self.v2api_host}/v2/disks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    # -------------------Static Routes-------------------
    @handle_and_munchify_response
    async def list_staticroutes(
        self,
        cont: int = 0,
        guids: list[str] = None,
        label_selector: list[str] = None,
        limit: int = 50,
        name: str = None,
        names: list[str] = None,
        regions: list[str] = None,
        **kwargs,
    ) -> Munch:
        """List all static routes in a project.

        Args:
            cont (int, optional): Start index of static routes. Defaults to 0.
            guids (list[str], optional): Define guids to get static routes from. Defaults to None.
            label_selector (list[str], optional): Define labelSelector to get static routes from. Defaults to None.
            limit (int, optional): Number of static routes to list. Defaults to 50.
            name (str, optional): Define name to get static routes from. Defaults to None.
            names (list[str], optional): Define names to get static routes from. Defaults to None.
            regions (list[str], optional): Define regions to get static routes from. Defaults to None.

        Returns:
            Munch: List of static routes as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/staticroutes/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "guids": guids,
                "labelSelector": label_selector,
                "name": name,
                "names": names,
                "regions": regions,
            },
        )

    @handle_and_munchify_response
    async def create_staticroute(self, body: dict, **kwargs) -> Munch:
        """Create a new static route.

        Returns:
            Munch: Static route details as a Munch object.
        """

        return await self.c.post(
            url=f"{self.v2api_host}/v2/staticroutes/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    async def get_staticroute(self, name: str, **kwargs) -> Munch:
        """Get a static route by its name.

        Args:
            name (str): Static route name

        Returns:
            Munch: Static route details as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    async def update_staticroute(self, name: str, body: dict, **kwargs) -> Munch:
        """Update a static route by its name.

        Args:
            name (str): Static route name
            body (dict): Update details

        Returns:
            Munch: Static route details as a Munch object.
        """

        return await self.c.put(
            url=f"{self.v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    async def delete_staticroute(self, name: str, **kwargs) -> Munch:
        """Delete a static route by its name.

        Args:
            name (str): Static route name

        Returns:
            Munch: Static route details as a Munch object.
        """

        return await self.c.delete(
            url=f"{self.v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    # -------------------Networks-------------------
    @handle_and_munchify_response
    async def list_networks(
        self,
        cont: int = 0,
        deviceName: str = None,
        label_selector: list[str] = None,
        limit: int = 50,
        name: str = None,
        names: list[str] = None,
        networkType: str = None,
        phases: list[str] = None,
        regions: list[str] = None,
        status: list[str] = None,
        **kwargs,
    ) -> Munch:
        """List all networks in a project.

        Args:
            cont (int, optional): Start index of networks. Defaults to 0.
            deviceName (str, optional): Filter networks by device name. Defaults to None.
            label_selector (list[str], optional): Define labelSelector to get networks from. Defaults to None.
            limit (int, optional): Number of networks to list. Defaults to 50.
            name (str, optional): Define name to get networks from. Defaults to None.
            names (list[str], optional): Define names to get networks from. Defaults to None.
            networkType (str, optional): Define network type to get networks from. Defaults to None.
            phases (list[str], optional): Define phases to get networks from. Available values : InProgress, Provisioning, Succeeded, FailedToUpdate, FailedToStart, Stopped. Defaults to None.
            regions (list[str], optional): Define regions to get networks from. Defaults to None.
            status (list[str], optional): Define status to get networks from. Available values : Running, Pending, Error, Unknown, Stopped. Defaults to None.

        Returns:
            Munch: List of networks as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/networks/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "deviceName": deviceName,
                "labelSelector": label_selector,
                "name": name,
                "names": names,
                "networkType": networkType,
                "phases": phases,
                "regions": regions,
                "status": status,
            },
        )

    @handle_and_munchify_response
    async def create_network(self, body: dict, **kwargs) -> Munch:
        """Create a new network.

        Returns:
            Munch: Network details as a Munch object.
        """

        return await self.c.post(
            url=f"{self.v2api_host}/v2/networks/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    async def get_network(self, name: str, **kwargs) -> Munch:
        """Get a network by its name.

        Args:
            name (str): Network name

        Returns:
            Munch: Network details as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/networks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    async def delete_network(self, name: str, **kwargs) -> Munch:
        """Delete a network by its name.

        Args:
            name (str): Network name

        Returns:
            Munch: Network details as a Munch object.
        """

        return await self.c.delete(
            url=f"{self.v2api_host}/v2/networks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    # -------------------Secrets-------------------
    @handle_and_munchify_response
    async def list_secrets(
        self,
        cont: int = 0,
        label_selector: list[str] = None,
        limit: int = 50,
        name: str = None,
        names: list[str] = None,
        regions: list[str] = None,
        **kwargs,
    ) -> Munch:
        """List all secrets in a project.

        Args:
            cont (int, optional): Start index of secrets. Defaults to 0.
            label_selector (list[str], optional): Define labelSelector to get secrets from. Defaults to None.
            limit (int, optional): Number of secrets to list. Defaults to 50.
            name (str, optional): Define name to get secrets from. Defaults to None.
            names (list[str], optional): Define names to get secrets from. Defaults to None.
            regions (list[str], optional): Define regions to get secrets from. Defaults to None.

        Returns:
            Munch: List of secrets as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/secrets/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "labelSelector": label_selector,
                "name": name,
                "names": names,
                "regions": regions,
            },
        )

    @handle_and_munchify_response
    async def create_secret(self, body: dict, **kwargs) -> Munch:
        """Create a new secret.

        Returns:
            Munch: Secret details as a Munch object.
        """

        return await self.c.post(
            url=f"{self.v2api_host}/v2/secrets/",
            headers=self.config.get_headers(*kwargs),
            json=body,
        )

    @handle_and_munchify_response
    async def get_secret(self, name: str, **kwargs) -> Munch:
        """Get a secret by its name.

        Args:
            name (str): Secret name

        Returns:
            Munch: Secret details as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    async def update_secret(self, name: str, body: dict, **kwargs) -> Munch:
        """Update a secret by its name.

        Args:
            name (str): Secret name
            body (dict): Update details

        Returns:
            Munch: Secret details as a Munch object.
        """

        return await self.c.put(
            url=f"{self.v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    async def delete_secret(self, name: str, **kwargs) -> Munch:
        """Delete a secret by its name.

        Args:
            name (str): Secret name

        Returns:
            Munch: Secret details as a Munch object.
        """

        return await self.c.delete(
            url=f"{self.v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    # -------------------Config Trees-------------------
    @handle_and_munchify_response
    async def list_configtrees(
        self,
        cont: int = 0,
        label_selector: list[str] = None,
        limit: int = 50,
        name: str = None,
        regions: list[str] = None,
        **kwargs,
    ) -> Munch:
        """List all config trees in a project.

        Args:
            cont (int, optional): Start index of config trees. Defaults to 0.
            label_selector (list[str], optional): Define labelSelector to get config trees from. Defaults to None.
            limit (int, optional): Number of config trees to list. Defaults to 50.
            name (str, optional): Define name to get config trees from. Defaults to None.
            regions (list[str], optional): Define regions to get config trees from. Defaults to None.

        Returns:
            Munch: List of config trees as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/configtrees/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "labelSelector": label_selector,
                "name": name,
                "regions": regions,
            },
        )

    @handle_and_munchify_response
    async def create_configtree(self, body: dict, **kwargs) -> Munch:
        """Create a new config tree.

        Args:
            body (object): Config tree details

        Returns:
            Munch: Config tree details as a Munch object.
        """

        return await self.c.post(
            url=f"{self.v2api_host}/v2/configtrees/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    async def get_configtree(
        self,
        name: str,
        contentTypes: list[str] = None,
        includeData: bool = False,
        keyPrefixes: list[str] = None,
        revision: str = None,
        **kwargs,
    ) -> Munch:
        """Get a config tree by its name.

        Args:
            name (str): Config tree name
            contentTypes (list[str], optional): Define contentTypes to get config tree from. Defaults to None.
            includeData (bool, optional): Include data. Defaults to False.
            keyPrefixes (list[str], optional): Define keyPrefixes to get config tree from. Defaults to None.
            revision (str, optional): Define revision to get config tree from. Defaults to None.

        Returns:
            Munch: Config tree details as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(**kwargs),
            params={
                "contentTypes": contentTypes,
                "includeData": includeData,
                "keyPrefixes": keyPrefixes,
                "revision": revision,
            },
        )

    @handle_and_munchify_response
    async def set_configtree_revision(
        self, name: str, configtree: object, project_guid: str = None, **kwargs
    ) -> Munch:
        """Set a config tree revision.

        Args:
            name (str): Config tree name
            configtree (object): Config tree details
            project_guid (str, optional): Project GUID. async defaults to None.

        Returns:
            Munch: Config tree details as a Munch object.
        """

        return await self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=configtree,
        )

    @handle_and_munchify_response
    async def update_configtree(self, name: str, body: dict, **kwargs) -> Munch:
        """Update a config tree by its name.

        Args:
            name (str): Config tree name
            body (dict): Update details

        Returns:
            Munch: Config tree details as a Munch object.
        """

        return await self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    async def delete_configtree(self, name: str, **kwargs) -> Munch:
        """Delete a config tree by its name.

        Args:
            name (str): Config tree name

        Returns:
            Munch: Config tree details as a Munch object.
        """

        return await self.c.delete(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    async def list_revisions(
        self,
        name: str,
        cont: int = 0,
        limit: int = 50,
        committed: bool = False,
        label_selector: list[str] = None,
        regions: list[str] = None,
        **kwargs,
    ) -> Munch:
        """List all revisions of a config tree.

        Args:
            name (str): Config tree name
            cont (int, optional): Continue param . Defaults to 0.
            limit (int, optional): Limit param . Defaults to 50.
            committed (bool, optional): Committed. Defaults to False.
            label_selector (list[str], optional): Define labelSelector to get revisions from. Defaults to None.
            regions (list[str], optional): Define regions to get revisions from. Defaults to None.

        Returns:
            Munch: List of revisions as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/configtrees/{name}/revisions/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "committed": committed,
                "labelSelector": label_selector,
                "regions": regions,
            },
        )

    @handle_and_munchify_response
    async def create_revision(
        self, name: str, body: dict, project_guid: str = None, **kwargs
    ) -> Munch:
        """Create a new revision.

        Args:
            name (str): Config tree name
            body (object): Revision details
            project_guid (str): Project GUID (optional)

        Returns:
            Munch: Revision details as a Munch object.
        """

        return await self.c.post(
            url=f"{self.v2api_host}/v2/configtrees/{name}/revisions/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=body,
        )

    @handle_and_munchify_response
    async def put_keys_in_revision(
        self, name: str, revision_id: str, configValues: list[(object)], **kwargs
    ) -> Munch:
        """Put keys in a revision.

        Returns:
            Munch: Revision details as a Munch object.
        """

        return await self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/keys/",
            headers=self.config.get_headers(**kwargs),
            json=configValues,
        )

    @handle_and_munchify_response
    async def commit_revision(
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

        return await self.c.patch(
            url=f"{self.v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/commit/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=configTreeRevision,
        )

    @handle_and_munchify_response
    async def get_key_in_revision(
        self, name: str, revision_id: str, key: str, project_guid: str = None, **kwargs
    ) -> Munch:
        """Get a key in a revision.

        Args:
            name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            project_guid (str, optional): Project GUID. async defaults to None.

        Returns:
            Munch: Key details as a Munch object.
        """

        return await self.c.get(
            url=f"{self.v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
        )

    @handle_and_munchify_response
    async def put_key_in_revision(
        self, name: str, revision_id: str, key: str, project_guid: str = None, **kwargs
    ) -> Munch:
        """Put a key in a revision.

        Args:
            name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            project_guid (str, optional): Project GUID. async defaults to None.

        Returns:
            Munch: Key details as a Munch object.
        """

        return await self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
        )

    @handle_and_munchify_response
    async def delete_key_in_revision(
        self, name: str, revision_id: str, key: str, project_guid: str = None, **kwargs
    ) -> Munch:
        """Delete a key in a revision.

        Args:
            name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            project_guid (str, optional): Project GUID. async defaults to None.

        Returns:
            Munch: Key details as a Munch object.
        """

        return await self.c.delete(
            url=f"{self.v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
        )

    @handle_and_munchify_response
    async def rename_key_in_revision(
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
            project_guid (str, optional): Project GUID. async defaults to None.

        Returns:
            Munch: Key details as a Munch object.
        """

        return await self.c.patch(
            url=f"{self.v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=configKeyRename,
        )
