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
from typing import Any

import httpx
from munch import Munch
from yaml import safe_load

from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.models import (
    Secret,
    StaticRoute,
    Disk,
    Deployment,
    Package,
    Project,
    Network,
    User,
    ProjectList,
    DeploymentList,
    DiskList,
    NetworkList,
    PackageList,
    SecretList,
    StaticRouteList,
    ManagedServiceBinding,
    ManagedServiceBindingList,
    ManagedServiceInstance,
    ManagedServiceInstanceList,
    ManagedServiceProviderList,
    Organization,
    Daemon,
    UserList,
    UserGroupList,
    UserGroup,
    Role,
    RoleBinding,
    RoleBindingList,
    RoleList,
)
from rapyuta_io_sdk_v2.utils import handle_server_errors


class AsyncClient:
    """AsyncClient class for the SDK."""

    def __init__(self, config: Configuration | None = None, **kwargs: Any):
        self.config: Configuration = config or Configuration()
        timeout: float = float(kwargs.get("timeout", 10))
        self.c: httpx.AsyncClient = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=5,
                keepalive_expiry=30,
            ),
            headers={
                "User-Agent": (
                    f"rio-sdk-v2;N/A;{platform.processor() or platform.machine()};{platform.system()};{platform.release()} {platform.version()}"
                )
            },
        )
        self.sync_client: httpx.Client = httpx.Client(
            timeout=timeout,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=5,
                keepalive_expiry=30,
            ),
            headers={
                "User-Agent": (
                    f"rio-sdk-v2;N/A;{platform.processor() or platform.machine()};{platform.system()};{platform.release()} {platform.version()}"
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
        result = self.sync_client.post(
            url=f"{self.rip_host}/user/login",
            headers={"Content-Type": "application/json"},
            json={
                "email": email,
                "password": password,
            },
        )
        handle_server_errors(result)
        return result.json()["data"].get("token")

    def login(
        self,
        email: str,
        password: str,
    ) -> None:
        """Get the authentication token for the user.

        Args:
            email (str)
            password (str)

        Returns:
            str: authentication token
        """

        token = self.get_auth_token(email, password)
        self.config.auth_token = token

    def logout(self, token: str | None = None) -> dict[str, Any]:
        """Expire the authentication token.

        Args:
            token (str): The token to expire.
        """

        if token is None:
            token = self.config.auth_token

        result = self.sync_client.post(
            url=f"{self.rip_host}/user/logout",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        handle_server_errors(result)
        return result.json()

    def refresh_token(self, token: str | None = None, set_token: bool = True) -> str:
        """Refresh the authentication token.

        Args:
            token (str): The token to refresh.
            set_token (bool): Set the refreshed token in the configuration.

        Returns:
            str: The refreshed token.
        """

        if token is None:
            token = self.config.auth_token

        result = self.sync_client.post(
            url=f"{self.rip_host}/refreshtoken",
            headers={"Content-Type": "application/json"},
            json={"token": token},
        )
        handle_server_errors(result)
        if set_token:
            self.config.auth_token = result.json()["data"].get("token")
        return result.json()["data"].get("token")

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

    # -----------------Organization----------------
    async def get_organization(
        self, organization_guid: str | None = None, **kwargs
    ) -> Organization:
        """Get an organization by its GUID.

        If organization GUID is provided, the current organization GUID will be
        picked from the current configuration.

        Args:
            organization_guid (str): user provided organization GUID.

        Returns:
            Organization: Organization details as an Organization object.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/organizations/{organization_guid}/",
            headers=self.config.get_headers(
                with_project=False, organization_guid=organization_guid, **kwargs
            ),
        )
        handle_server_errors(result)
        return Organization(**result.json())

    async def update_organization(
        self,
        body: Organization | dict[str, Any],
        organization_guid: str | None = None,
        **kwargs,
    ) -> Organization:
        """Update an organization by its GUID.

        Args:
            body (dict): Organization details
            organization_guid (str, optional): Organization GUID. Defaults to None.

        Returns:
            Organization: Organization details as an Organization object.
        """

        if isinstance(body, dict):
            body = Organization.model_validate(body)

        result = await self.c.put(
            url=f"{self.v2api_host}/v2/organizations/{organization_guid}/",
            headers=self.config.get_headers(
                with_project=False, organization_guid=organization_guid, **kwargs
            ),
            json=body.model_dump(),
        )
        handle_server_errors(result)
        return Organization(**result.json())

    # ---------------------User--------------------
    async def list_users(
        self,
        organization_guid: str | None = None,
        guid: str | None = None,
        cont: int = 0,
        limit: int = 50,
        **kwargs,
    ) -> UserList:
        parameters: dict[str, Any] = {
            "continue": cont,
            "limit": limit,
        }
        if guid:
            parameters["guid"] = guid

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/users/",
            headers=self.config.get_headers(
                with_project=False, organization_guid=organization_guid, **kwargs
            ),
            params=parameters,
        )

        handle_server_errors(result)

        return UserList(**result.json())

    async def get_myself(self, **kwargs) -> User:
        """Get User details.

        Returns:
            User: User details as a User object.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/users/me/",
            headers=self.config.get_headers(
                with_project=False, with_organization=False, **kwargs
            ),
        )
        handle_server_errors(result)
        return User(**result.json())

    # Alias for backward compatibility
    async def get_user(self, **kwargs) -> User:
        """Get User details. (Alias for get_myself)

        Returns:
            User: User details as a User object.
        """
        return await self.get_myself(**kwargs)

    async def update_user(self, body: User | dict[str, Any], **kwargs) -> User:
        """Update the user details.

        Args:
            body (dict): User details

        Returns:
            User: User details as a User object.
        """
        if isinstance(body, dict):
            body = User.model_validate(body)

        result = await self.c.put(
            url=f"{self.v2api_host}/v2/users/me/",
            headers=self.config.get_headers(
                with_project=False, with_organization=False, **kwargs
            ),
            json=body.model_dump(),
        )
        handle_server_errors(result)
        return User(**result.json())

    # ----------------- Projects -----------------
    async def list_projects(
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        status: list[str] | None = None,
        organizations: list[str] | None = None,
        name: str | None = None,
        **kwargs,
    ) -> ProjectList:
        """List all projects in an organization.

        Args:
            cont (int, optional): Start index of projects. Defaults to 0.
            limit (int, optional): Number of projects to list. Defaults to 50.
            label_selector (List[str], optional): Define labelSelector to get projects from. Defaults to None.
            status (List[str], optional): Define status to get projects from. Defaults to None.
            organizations (List[str], optional): Define organizations to get projects from. Defaults to None.
            name (str, optional): Define name to get projects from. Defaults to None.

        Returns:
            List of projects as a dictionary.
        """

        parameters: dict[str, Any] = {
            "continue": cont,
            "limit": limit,
        }
        if organizations:
            parameters["organizations"] = organizations
        if label_selector:
            parameters["labelSelector"] = label_selector
        if status:
            parameters["status"] = status
        if name:
            parameters["name"] = name

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/projects/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            params=parameters,
        )

        handle_server_errors(result)
        return ProjectList(**result.json())

    async def get_project(self, project_guid: str | None = None, **kwargs) -> Project:
        """Get a project by its GUID.

        If no project or organization GUID is provided,
        the async default project and organization GUIDs will
        be picked from the current configuration.

        Args:
            project_guid (str): user provided project GUID or config project GUID

        Raises:
            ValueError: If organization_guid or project_guid is None

        Returns:
            Project details as a dictionary.
        """
        if project_guid is None:
            project_guid = self.config.project_guid
        if not project_guid:
            raise ValueError("project_guid is required")
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)
        return Project(**result.json())

    async def create_project(self, body: Project | dict[str, Any], **kwargs) -> Project:
        """Create a new project.

        Args:
            body (dict): Project details

        Returns:
            Project details as a dictionary.
        """
        if isinstance(body, dict):
            body = Project.model_validate(body)

        org_guid = body.metadata.organizationGUID or None

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/projects/",
            headers=self.config.get_headers(
                organization_guid=org_guid, with_project=False, **kwargs
            ),
            json=body.model_dump(),
        )
        handle_server_errors(result)
        return Project(**result.json())

    async def update_project(
        self, body: Project | dict[str, Any], project_guid: str | None = None, **kwargs
    ) -> Project:
        """Update a project by its GUID.

        Args:
            body (dict): Project details
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            Project details as a dictionary.
        """
        if isinstance(body, dict):
            body = Project.model_validate(body)

        result = await self.c.put(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=body.model_dump(),
        )
        handle_server_errors(result)
        return Project(**result.json())

    async def delete_project(self, project_guid: str, **kwargs) -> None:
        """Delete a project by its GUID.

        Args:
            project_guid (str): Project GUID

        Returns:
            None if successful.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)
        return None

    async def update_project_owner(
        self, body: dict, project_guid: str = None, **kwargs
    ) -> dict[str, Any]:
        """Update the owner of a project by its GUID.

        Returns:
            Dict[str, Any]: Project owner update result.
        """
        project_guid = project_guid or self.config.project_guid

        result = await self.c.put(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/owner/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )
        handle_server_errors(result)
        return result

    # -------------------Package-------------------
    async def list_packages(
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        name: str | None = None,
        **kwargs,
    ) -> PackageList:
        """List all packages in a project.

        Args:
            cont (int, optional): Start index of packages. Defaults to 0.
            limit (int, optional): Number of packages to list. Defaults to 50.
            label_selector (List[str], optional): Define labelSelector to get packages from. Defaults to None.
            name (str, optional): Define name to get packages from. Defaults to None.

        Returns:
            List of packages as a dictionary.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/packages/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "labelSelector": label_selector,
                "name": name,
            },
        )

        handle_server_errors(response=result)
        return PackageList(**result.json())

    async def create_package(self, body: Package | dict[str, Any], **kwargs) -> Package:
        """Create a new package.

        The Payload is the JSON format of the Package Manifest.
        For a documented example, run the rio explain package command.

        Args:
            body (dict): Package details

        Returns:
            Package: Package details as a Package object.
        """
        if isinstance(body, dict):
            body = Package.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/packages/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(),
        )

        handle_server_errors(result)
        return Package(**result.json())

    async def get_package(
        self, name: str, version: str | None = None, **kwargs
    ) -> Package:
        """Get a package by its name.

        Args:
            name (str): Package name
            version (str, optional): Package version. Defaults to None.

        Returns:
            Package: Package details as a Package object.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/packages/{name}/",
            headers=self.config.get_headers(**kwargs),
            params={"version": version},
        )
        handle_server_errors(result)

        return Package(**result.json())

    async def delete_package(self, name: str, version: str, **kwargs) -> None:
        """Delete a package by its name.

        Args:
            name (str): Package name

        Returns:
            None if successful.
        """

        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/packages/{name}/",
            headers=self.config.get_headers(**kwargs),
            params={"version": version},
        )
        handle_server_errors(result)
        return None

    async def list_deployments(
        self,
        cont: int = 0,
        limit: int = 50,
        dependencies: bool = False,
        device_name: str | None = None,
        guids: list[str] | None = None,
        label_selector: list[str] | None = None,
        name: str | None = None,
        names: list[str] | None = None,
        package_name: str | None = None,
        package_version: str | None = None,
        phases: list[str] | None = None,
        regions: list[str] | None = None,
        **kwargs,
    ) -> DeploymentList:
        """List all deployments in a project.

        Args:
            cont (int, optional): Start index of deployments. Defaults to 0.
            limit (int, optional): Number of deployments to list. Defaults to 50.
            dependencies (bool, optional): Filter by dependencies. Defaults to False.
            device_name (str, optional): Filter deployments by device name. Defaults to None.
            guids (List[str], optional): Filter by GUIDs. Defaults to None.
            label_selector (List[str], optional): Define labelSelector to get deployments from. Defaults to None.
            name (str, optional): Define name to get deployments from. Defaults to None.
            names (List[str], optional): Define names to get deployments from. Defaults to None.
            package_name (str, optional): Filter by package name. Defaults to None.
            package_version (str, optional): Filter by package version. Defaults to None.
            phases (List[str], optional): Filter by phases. Available values : InProgress, Provisioning, Succeeded, FailedToUpdate, FailedToStart, Stopped. Defaults to None.
            regions (List[str], optional): Filter by regions. Defaults to None.

        Returns:
            List of deployments as a dictionary.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/deployments/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "dependencies": dependencies,
                "deviceName": device_name,
                "guids": guids,
                "labelSelector": label_selector,
                "name": name,
                "names": names,
                "packageName": package_name,
                "packageVersion": package_version,
                "phases": phases,
                "regions": regions,
            },
        )

        handle_server_errors(response=result)

        return DeploymentList(**result.json())

    # -------------------Deployment-------------------

    async def create_deployment(
        self, body: Deployment | dict[str, Any], **kwargs
    ) -> Deployment:
        """Create a new deployment.

        Args:
            body (dict): Deployment details

        Returns:
            Deployment: Deployment details as a Deployment object.
        """
        if isinstance(body, dict):
            body = Deployment.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/deployments/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(),
        )

        handle_server_errors(result)
        return Deployment(**result.json())

    async def get_deployment(
        self, name: str, guid: str | None = None, **kwargs
    ) -> Deployment:
        """Get a deployment by its name.

        Args:
            name (str): Deployment name
            guid (str, optional): Deployment GUID. Defaults to None.

        Returns:
            Deployment: Deployment details as a Deployment object.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(**kwargs),
            params={"guid": guid},
        )

        handle_server_errors(response=result)

        return Deployment(**result.json())

    async def update_deployment(
        self, name: str, body: Deployment | dict[str, Any], **kwargs
    ) -> Deployment:
        """Update a deployment by its name.

        Args:
            name (str): Deployment name
            body (dict): Deployment details

        Returns:
            Deployment: Deployment details as a Deployment object.
        """
        if isinstance(body, dict):
            body = Deployment.model_validate(body)

        result = await self.c.patch(
            url=f"{self.v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(),
        )
        handle_server_errors(result)
        return Deployment(**result.json())

    async def delete_deployment(self, name: str, **kwargs) -> None:
        """Delete a deployment by its name.

        Returns:
            None if successful.
        """

        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return None

    async def get_deployment_graph(self, name: str, **kwargs) -> dict[str, Any]:
        """Get a deployment graph by its name. [Experimental]

        Returns:
            Deployment graph as a dictionary.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/deployments/{name}/graph/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return result

    async def get_deployment_history(
        self, name: str, guid: str | None = None, **kwargs
    ) -> dict[str, Any]:
        """Get a deployment history by its name.

        Returns:
            Deployment history as a dictionary.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/deployments/{name}/history/",
            headers=self.config.get_headers(**kwargs),
            params={"guid": guid},
        )
        handle_server_errors(result)
        return result

    async def stream_deployment_logs(self, name: str, executable: str, replica: int = 0):
        """Asynchronously stream logs for a deployment executable replica."""
        url = f"{self.v2api_host}/v2/deployments/{name}/logs/?replica={replica}&executable={executable}"

        async with self.c.stream(
            "GET", url=url, headers=self.config.get_headers()
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line:
                    yield line

    # -------------------Disks-------------------

    async def list_disks(
        self,
        cont: int = 0,
        label_selector: list[str] | None = None,
        limit: int = 50,
        names: list[str] | None = None,
        regions: list[str] | None = None,
        status: list[str] | None = None,
        **kwargs,
    ) -> DiskList:
        """List all disks in a project.

        Args:
            cont (int, optional): Start index of disks. Defaults to 0.
            label_selector (List[str], optional): Define labelSelector to get disks from. Defaults to None.
            limit (int, optional): Number of disks to list. Defaults to 50.
            names (List[str], optional): Define names to get disks from. Defaults to None.
            regions (List[str], optional): Define regions to get disks from. Defaults to None.
            status (List[str], optional): Define status to get disks from. Available values : Available, Bound, Released, Failed, Pending.Defaults to None.


        Returns:
            List of disks as a dictionary.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/disks/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "labelSelector": label_selector,
                "names": names,
                "regions": regions,
                "status": status,
            },
        )

        handle_server_errors(response=result)
        return DiskList(**result.json())

    async def get_disk(self, name: str, **kwargs) -> Disk:
        """Get a disk by its name.

        Args:
            name (str): Disk name

        Returns:
            Disk: Disk details as a Disk object.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/disks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(response=result)

        return Disk(**result.json())

    async def create_disk(self, body: Disk | dict[str, Any], **kwargs) -> Disk:
        """Create a new disk.

        Args:
            body (dict): Disk details

        Returns:
            Disk: Disk details as a Disk object.
        """
        if isinstance(body, dict):
            body = Disk.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/disks/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(),
        )
        handle_server_errors(result)
        return Disk(**result.json())

    async def delete_disk(self, name: str, **kwargs) -> None:
        """Delete a disk by its name.

        Args:
            name (str): Disk name

        Returns:
            None if successful.
        """

        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/disks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return None

    # -------------------Device--------------------------

    async def get_device_daemons(self, device_guid: str):
        """
        Retrieve the list of daemons associated with a specific device.

        Args:
            device_guid (str): The unique identifier (GUID) of the device.

        Returns:
            dict: The JSON response containing information about the device's daemons.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/devices/daemons/{device_guid}/",
            headers=self.config.get_headers(),
        )

        handle_server_errors(response=result)
        return Daemon(**result.json())

    # -------------------Static Routes-------------------

    async def list_staticroutes(
        self,
        cont: int = 0,
        limit: int = 50,
        guids: list[str] | None = None,
        label_selector: list[str] | None = None,
        names: list[str] | None = None,
        regions: list[str] | None = None,
        **kwargs,
    ) -> StaticRouteList:
        """List all static routes in a project.

        Args:
            cont (int, optional): Start index of static routes. Defaults to 0.
            limit (int, optional): Number of static routes to list. Defaults to 50.
            guids (List[str], optional): Define guids to get static routes from. Defaults to None.
            label_selector (List[str], optional): Define labelSelector to get static routes from. Defaults to None.
            names (List[str], optional): Define names to get static routes from. Defaults to None.
            regions (List[str], optional): Define regions to get static routes from. Defaults to None.

        Returns:
            List of static routes as a dictionary.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/staticroutes/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "guids": guids,
                "labelSelector": label_selector,
                "names": names,
                "regions": regions,
            },
        )

        handle_server_errors(response=result)
        return StaticRouteList(**result.json())

    async def create_staticroute(
        self, body: StaticRoute | dict[str, Any], **kwargs
    ) -> StaticRoute:
        """Create a new static route.

        Args:
            body (dict): Static route details

        Returns:
            StaticRoute: Static route details as a StaticRoute object.
        """
        if isinstance(body, dict):
            body = StaticRoute.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/staticroutes/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(),
        )
        handle_server_errors(result)
        return StaticRoute(**result.json())

    async def get_staticroute(self, name: str, **kwargs) -> StaticRoute:
        """Get a static route by its name.

        Args:
            name (str): Static route name

        Returns:
            StaticRoute: Static route details as a StaticRoute object.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(response=result)

        return StaticRoute(**result.json())

    async def update_staticroute(
        self, name: str, body: StaticRoute | dict[str, Any], **kwargs
    ) -> StaticRoute:
        """Update a static route by its name.

        Args:
            name (str): Static route name
            body (dict): Update details

        Returns:
            StaticRoute: Static route details as a StaticRoute object.
        """
        if isinstance(body, dict):
            body = StaticRoute.model_validate(body)

        result = await self.c.put(
            url=f"{self.v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(),
        )
        handle_server_errors(result)
        return StaticRoute(**result.json())

    async def delete_staticroute(self, name: str, **kwargs) -> None:
        """Delete a static route by its name.

        Args:
            name (str): Static route name

        Returns:
            None if successful.
        """

        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return None

    # -------------------Networks-------------------

    async def list_networks(
        self,
        cont: int = 0,
        limit: int = 50,
        device_name: str | None = None,
        label_selector: list[str] | None = None,
        names: list[str] | None = None,
        network_type: str | None = None,
        phases: list[str] | None = None,
        regions: list[str] | None = None,
        status: list[str] | None = None,
        **kwargs,
    ) -> NetworkList:
        """List all networks in a project.

        Args:
            cont (int, optional): Start index of networks. Defaults to 0.
            limit (int, optional): Number of networks to list. Defaults to 50.
            device_name (str, optional): Filter networks by device name. Defaults to None.
            label_selector (List[str], optional): Define labelSelector to get networks from. Defaults to None.
            names (List[str], optional): Define names to get networks from. Defaults to None.
            network_type (str, optional): Define network type to get networks from. Defaults to None.
            phases (List[str], optional): Define phases to get networks from. Available values : InProgress, Provisioning, Succeeded, FailedToUpdate, FailedToStart, Stopped. Defaults to None.
            regions (List[str], optional): Define regions to get networks from. Defaults to None.
            status (List[str], optional): Define status to get networks from. Available values : Running, Pending, Error, Unknown, Stopped. Defaults to None.

        Returns:
            List of networks as a dictionary.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/networks/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
                "deviceName": device_name,
                "labelSelector": label_selector,
                "names": names,
                "networkType": network_type,
                "phases": phases,
                "regions": regions,
                "status": status,
            },
        )

        handle_server_errors(response=result)
        return NetworkList(**result.json())

    async def create_network(self, body: Network | dict[str, Any], **kwargs) -> Network:
        """Create a new network.

        Args:
            body (dict): Network details

        Returns:
            Network: Network details as a Network object.
        """
        if isinstance(body, dict):
            body = Network.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/networks/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(),
        )
        handle_server_errors(result)
        return Network(**result.json())

    async def get_network(self, name: str, **kwargs) -> Network:
        """Get a network by its name.

        Args:
            name (str): Network name

        Returns:
            Network: Network details as a Network object.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/networks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(response=result)

        return Network(**result.json())

    async def delete_network(self, name: str, **kwargs) -> None:
        """Delete a network by its name.

        Args:
            name (str): Network name

        Returns:
            None if successful.
        """

        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/networks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return None

    # -------------------Secrets-------------------

    async def list_secrets(
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        names: list[str] | None = None,
        regions: list[str] | None = None,
        **kwargs,
    ) -> SecretList:
        """List all secrets in a project.

        Args:
            cont (int, optional): Start index of secrets. Defaults to 0.
            limit (int, optional): Number of secrets to list. Defaults to 50.
            label_selector (List[str], optional): Define labelSelector to get secrets from. Defaults to None.
            names (List[str], optional): Define names to get secrets from. Defaults to None.
            regions (List[str], optional): Define regions to get secrets from. Defaults to None.

        Returns:
            List of secrets as a dictionary.
        """

        parameters: dict[str, Any] = {
            "continue": cont,
            "limit": limit,
        }
        if label_selector is not None:
            parameters["labelSelector"] = label_selector
        if names is not None:
            parameters["names"] = names
        if regions is not None:
            parameters["regions"] = regions

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/secrets/",
            headers=self.config.get_headers(**kwargs),
            params=parameters,
        )

        handle_server_errors(response=result)
        return SecretList(**result.json())

    async def create_secret(self, body: Secret | dict[str, Any], **kwargs) -> Secret:
        """Create a new secret.

        Args:
            body (dict): Secret details

        Returns:
            Secret: Secret details as a Secret object.
        """
        if isinstance(body, dict):
            body = Secret.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/secrets/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(),
        )

        handle_server_errors(result)
        return Secret(**result.json())

    async def get_secret(self, name: str, **kwargs) -> Secret:
        """Get a secret by its name.

        Args:
            name (str): Secret name

        Returns:
            Secret: Secret details as a Secret object.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(response=result)

        return Secret(**result.json())

    async def update_secret(
        self, name: str, body: Secret | dict[str, Any], **kwargs
    ) -> Secret:
        """Update a secret by its name.

        Args:
            name (str): Secret name
            body (dict): Update details

        Returns:
            Secret: Secret details as a Secret object.
        """
        if isinstance(body, dict):
            body = Secret.model_validate(body)

        result = await self.c.put(
            url=f"{self.v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(),
        )
        handle_server_errors(result)
        return Secret(**result.json())

    async def delete_secret(self, name: str, **kwargs) -> None:
        """Delete a secret by its name.

        Args:
            name (str): Secret name

        Returns:
            None if successful.
        """

        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return None

    # -------------------OAuth2 Clients-------------------
    async def list_oauth2_clients(
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] = None,
        names: list[str] = None,
        regions: list[str] = None,
        **kwargs,
    ) -> dict[str, Any]:
        """List all OAuth2 clients in a project.

        Args:
            cont (int, optional): Start index. Defaults to 0.
            limit (int, optional): Number to list. Defaults to 50.
            label_selector (List[str], optional): Label selector. Defaults to None.
            names (List[str], optional): Names filter. Defaults to None.
            regions (List[str], optional): Regions filter. Defaults to None.

        Returns:
            List of OAuth2 clients as a dictionary.
        """
        params = {
            "continue": cont,
            "limit": limit,
        }
        if label_selector is not None:
            params["labelSelector"] = label_selector
        if names is not None:
            params["names"] = names
        if regions is not None:
            params["regions"] = regions

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/oauth2clients/",
            headers=self.config.get_headers(**kwargs),
            params=params,
        )
        handle_server_errors(result)
        return result.json()

    async def get_oauth2_client(self, client_id: str, **kwargs) -> dict[str, Any]:
        """Get an OAuth2 client by its client_id.

        Args:
            client_id (str): OAuth2 client ID

        Returns:
            OAuth2 client details as a dictionary.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/oauth2clients/{client_id}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return result.json()

    async def create_oauth2_client(self, body: dict, **kwargs) -> dict[str, Any]:
        """Create a new OAuth2 client.

        Args:
            body (dict): OAuth2 client details

        Returns:
            OAuth2 client details as a dictionary.
        """
        result = await self.c.post(
            url=f"{self.v2api_host}/v2/oauth2clients/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )
        handle_server_errors(result)
        return result.json()

    async def update_oauth2_client(
        self, client_id: str, body: dict, **kwargs
    ) -> dict[str, Any]:
        """Update an OAuth2 client by its client_id.

        Args:
            client_id (str): OAuth2 client ID
            body (dict): Update details

        Returns:
            OAuth2 client details as a dictionary.
        """
        result = await self.c.put(
            url=f"{self.v2api_host}/v2/oauth2clients/{client_id}/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )
        handle_server_errors(result)
        return result.json()

    async def update_oauth2_client_uris(
        self, client_id: str, uris: dict, **kwargs
    ) -> dict[str, Any]:
        """Update OAuth2 client URIs.

        Args:
            client_id (str): OAuth2 client ID
            uris (dict): URIs update payload

        Returns:
            OAuth2 client details as a dictionary.
        """
        result = await self.c.patch(
            url=f"{self.v2api_host}/v2/oauth2clients/{client_id}/uris/",
            headers=self.config.get_headers(**kwargs),
            json=uris,
        )
        handle_server_errors(result)
        return result.json()

    async def delete_oauth2_client(self, client_id: str, **kwargs) -> None:
        """Delete an OAuth2 client by its client_id.

        Args:
            client_id (str): OAuth2 client ID

        Returns:
            None if successful.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/oauth2clients/{client_id}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return None

    # -------------------Config Trees-------------------

    async def list_configtrees(
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] = None,
        with_project: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """List all config trees in a project.

        Args:
            cont (int, optional): Start index of config trees. Defaults to 0.
            limit (int, optional): Number of config trees to list. Defaults to 50.
            label_selector (List[str], optional): Define labelSelector to get config trees from. Defaults to None.
            with_project (bool, optional): Include project details. Defaults to True.

        Returns:
            List of config trees as a dictionary.
        """

        parameters = {
            "continue": cont,
            "limit": limit,
        }
        if label_selector:
            parameters["labelSelector"] = label_selector
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/configtrees/",
            headers=self.config.get_headers(with_project=with_project, **kwargs),
            params=parameters,
        )
        handle_server_errors(result)
        return result.json()

    async def create_configtree(
        self, body: dict, with_project: bool = True, **kwargs
    ) -> dict[str, Any]:
        """Create a new config tree.

        Args:
            body (object): Config tree details
            with_project (bool, optional): Work in the project scope. Defaults to True.

        Returns:
            Config tree details as a dictionary.
        """

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/configtrees/",
            headers=self.config.get_headers(with_project=with_project, **kwargs),
            json=body,
        )
        handle_server_errors(result)
        return result.json()

    async def get_configtree(
        self,
        name: str,
        content_types: list[str] = None,
        include_data: bool = False,
        key_prefixes: list[str] = None,
        revision: str | None = None,
        with_project: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """Get a config tree by its name.

        Args:
            name (str): Config tree name
            content_types (List[str], optional): Define contentTypes to get config tree from. Defaults to None.
            include_data (bool, optional): Include data. Defaults to False.
            key_prefixes (List[str], optional): Define keyPrefixes to get config tree from. Defaults to None.
            revision (str, optional): Define revision to get config tree from. Defaults to None.
            with_project (bool, optional): Work in the project scope. Defaults to True.

        Returns:
            Config tree details as a dictionary.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(with_project=with_project, **kwargs),
            params={
                "contentTypes": content_types,
                "includeData": include_data,
                "keyPrefixes": key_prefixes,
                "revision": revision,
            },
        )
        handle_server_errors(result)
        return result.json()

    async def set_configtree_revision(
        self, name: str, configtree: object, project_guid: str | None = None, **kwargs
    ) -> dict[str, Any]:
        """Set a config tree revision.

        Args:
            name (str): Config tree name
            configtree (object): Config tree details
            project_guid (str, optional): Project GUID. async defaults to None.

        Returns:
            Config tree details as a dictionary.
        """

        result = await self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=configtree,
        )
        handle_server_errors(result)
        return result.json()

    async def update_configtree(
        self, name: str, body: dict, with_project: bool = True, **kwargs
    ) -> dict[str, Any]:
        """Update a config tree by its name.

        Args:
            name (str): Config tree name
            body (dict): Update details
            with_project (bool, optional): Work in the project scope. Defaults to True.

        Returns:
            Config tree details as a dictionary.
        """

        result = await self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(with_project=with_project, **kwargs),
            json=body,
        )

        handle_server_errors(result)

        return result.json()

    async def delete_configtree(self, name: str, **kwargs) -> None:
        """Delete a config tree by its name.

        Args:
            name (str): Config tree name

        Returns:
            None if successful.
        """

        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return None

    async def list_revisions(
        self,
        tree_name: str,
        cont: int = 0,
        limit: int = 50,
        committed: bool = False,
        label_selector: list[str] = None,
        **kwargs,
    ) -> dict[str, Any]:
        """List all revisions of a config tree.

        Args:
            tree_name (str): Config tree name
            cont (int, optional): Continue param . Defaults to 0.
            limit (int, optional): Limit param . Defaults to 50.
            committed (bool, optional): Committed. Defaults to False.
            label_selector (List[str], optional): Define labelSelector to get revisions from. Defaults to None.

        Returns:
            List of revisions as a dictionary.
        """

        parameters = {
            "continue": cont,
            "limit": limit,
            "committed": committed,
        }
        if label_selector:
            parameters["labelSelector"] = label_selector

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/",
            headers=self.config.get_headers(**kwargs),
            params=parameters,
        )

        handle_server_errors(result)
        return result.json()

    async def create_revision(
        self, name: str, body: dict, project_guid: str | None = None, **kwargs
    ) -> dict[str, Any]:
        """Create a new revision.

        Args:
            name (str): Config tree name
            body (object): Revision details
            project_guid (str): Project GUID (optional)

        Returns:
            Revision details as a dictionary.
        """

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/configtrees/{name}/revisions/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=body,
        )

        handle_server_errors(result)
        return result.json()

    async def put_keys_in_revision(
        self, name: str, revision_id: str, config_values: dict, **kwargs
    ) -> dict[str, Any]:
        """Put keys in a revision.

        Args:
            name (str): Config tree name
            revision_id (str): Config tree revision ID
            config_values (dict): Config values

        Returns:
            Revision details as a dictionary.
        """

        result = await self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/keys/",
            headers=self.config.get_headers(**kwargs),
            json=config_values,
        )

        handle_server_errors(result)
        return result.json()

    async def commit_revision(
        self,
        tree_name: str,
        revision_id: str,
        author: str | None = None,
        message: str | None = None,
        project_guid: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Commit a revision.

        Args:
            tree_name (str): Config tree name
            revision_id (str): Config tree revision ID
            author (str, optional): Revision Author. Defaults to None.
            message (str, optional): Revision Message. Defaults to None.
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            Revision details as a dictionary.
        """
        config_tree_revision = {
            "author": author,
            "message": message,
        }

        result = await self.c.patch(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=config_tree_revision,
        )

    async def get_key_in_revision(
        self,
        tree_name: str,
        revision_id: str,
        key: str,
        project_guid: str | None = None,
        **kwargs,
    ):
        """Get a key in a revision.

        Args:
            tree_name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            project_guid (str, optional): Project GUID. async defaults to None.

        Returns:
            Key details as a dictionary.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
        )
        # The data received from the API is always in string format. To use
        # appropriate data-type in Python (as well in exports), we are
        # passing it through YAML parser.
        return safe_load(result.text)

        handle_server_errors(result)
        return result.json()

    async def put_key_in_revision(
        self,
        tree_name: str,
        revision_id: str,
        key: str,
        project_guid: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Put a key in a revision.

        Args:
            tree_name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            project_guid (str, optional): Project GUID. async defaults to None.

        Returns:
            Key details as a dictionary.
        """

        result = await self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
        )
        handle_server_errors(result)
        return result.json()

    async def delete_key_in_revision(
        self,
        tree_name: str,
        revision_id: str,
        key: str,
        project_guid: str | None = None,
        **kwargs,
    ) -> None:
        """Delete a key in a revision.

        Args:
            tree_name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            project_guid (str, optional): Project GUID. async defaults to None.

        Returns:
            None if successful.
        """

        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
        )
        handle_server_errors(result)
        return None

    async def rename_key_in_revision(
        self,
        tree_name: str,
        revision_id: str,
        key: str,
        config_key_rename: dict,
        project_guid: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Rename a key in a revision.

        Args:
            tree_name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            config_key_rename (dict): Key rename details
            project_guid (str, optional): Project GUID. async defaults to None.

        Returns:
            Key details as a dictionary.
        """

        result = await self.c.patch(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=config_key_rename,
        )

        handle_server_errors(result)
        return result.json()

    # Managed Service API

    async def list_providers(self) -> ManagedServiceProviderList:
        """List all providers.

        Returns:
            List of providers as a dictionary.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/managedservices/providers/",
            headers=self.config.get_headers(with_project=False),
        )

        handle_server_errors(result)
        return ManagedServiceProviderList(**result.json())

    async def list_instances(
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] = None,
        providers: list[str] = None,
    ) -> ManagedServiceInstanceList:
        """List all instances in a project.

        Args:
            cont (int, optional): Start index of instances. Defaults to 0.
            limit (int, optional): Number of instances to list. Defaults to 50.
            label_selector (List[str], optional): Define labelSelector to get instances from. Defaults to None.
            providers (List[str], optional): Define providers to get instances from. Defaults to None.

        Returns:
            List of instances as a dictionary.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/managedservices/",
            headers=self.config.get_headers(),
            params={
                "continue": cont,
                "limit": limit,
                "labelSelector": label_selector,
                "providers": providers,
            },
        )

        handle_server_errors(result)
        return ManagedServiceInstanceList(**result.json())

    async def get_instance(self, name: str) -> ManagedServiceInstance:
        """Get an instance by its name.

        Args:
            name (str): Instance name

        Returns:
            Instance details as a dictionary.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/managedservices/{name}/",
            headers=self.config.get_headers(),
        )

        handle_server_errors(result)
        return ManagedServiceInstance(**result.json())

    async def create_instance(
        self, body: ManagedServiceInstance | dict[str, Any]
    ) -> ManagedServiceInstance:
        """Create a new instance.

        Returns:
            Instance details as a ManagedServiceInstance object.
        """
        if isinstance(body, dict):
            body = ManagedServiceInstance.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/managedservices/",
            headers=self.config.get_headers(),
            json=body.model_dump(),
        )

        handle_server_errors(result)
        return ManagedServiceInstance(**result.json())

    async def delete_instance(self, name: str) -> None:
        """Delete an instance.

        Returns:
            None if successful.
        """

        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/managedservices/{name}/",
            headers=self.config.get_headers(),
        )
        handle_server_errors(result)
        return None

    async def list_instance_bindings(
        self,
        instance_name: str,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] = None,
    ) -> ManagedServiceBindingList:
        """List all instance bindings in a project.

        Args:
            instance_name (str): Instance name.
            cont (int, optional): Start index of instance bindings. Defaults to 0.
            limit (int, optional): Number of instance bindings to list. Defaults to 50.
            label_selector (List[str], optional): Define labelSelector to get instance bindings from. Defaults to None.

        Returns:
            List of instance bindings as a dictionary.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/managedservices/{instance_name}/bindings/",
            headers=self.config.get_headers(),
            params={
                "continue": cont,
                "limit": limit,
                "labelSelector": label_selector,
            },
        )

        handle_server_errors(result)
        return ManagedServiceBindingList(**result.json())

    async def create_instance_binding(
        self, instance_name: str, body: ManagedServiceBinding | dict
    ) -> ManagedServiceBinding:
        """Create a new instance binding.

        Args:
            instance_name (str): Instance name.
            body (object): Instance binding details.

        Returns:
            Instance binding details as a dictionary.
        """

        if isinstance(body, dict):
            body = ManagedServiceBinding.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/managedservices/{instance_name}/bindings/",
            headers=self.config.get_headers(),
            json=body.model_dump(),
        )

        handle_server_errors(result)
        return ManagedServiceBinding(**result.json())

    async def get_instance_binding(
        self, instance_name: str, name: str
    ) -> ManagedServiceBinding:
        """Get an instance binding by its name.

        Args:
            instance_name (str): Instance name.
            name (str): Instance binding name.

        Returns:
            Instance binding details as a dictionary.
        """

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/managedservices/{instance_name}/bindings/{name}/",
            headers=self.config.get_headers(),
        )

        handle_server_errors(result)
        return ManagedServiceBinding(**result.json())

    async def delete_instance_binding(self, instance_name: str, name: str) -> None:
        """Delete an instance binding.

        Args:
            instance_name (str): Instance name.
            name (str): Instance binding name.

        Returns:
            None if successful.
        """

        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/managedservices/{instance_name}/bindings/{name}/",
            headers=self.config.get_headers(),
        )
        handle_server_errors(result)
        return None

    # -------------------Usergroup-------------------
    async def list_user_groups(
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        name: str | None = None,
        **kwargs,
    ) -> UserGroupList:
        parameters: dict[str, Any] = {
            "continue": cont,
            "limit": limit,
        }
        if label_selector:
            parameters["labelSelector"] = label_selector
        if name:
            parameters["name"] = name

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/usergroups/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            params=parameters,
        )

        handle_server_errors(response=result)

        return UserGroupList(**result.json())

    async def get_user_group(
        self, group_name: str, group_guid: str, **kwargs
    ) -> UserGroup:
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/usergroups/{group_name}/",
            headers=self.config.get_headers(
                with_project=False, with_group=True, group_guid=group_guid, **kwargs
            ),
        )
        handle_server_errors(result)

        return UserGroup(**result.json())

    async def create_user_group(self, user_group: UserGroup, **kwargs) -> UserGroup:
        result = await self.c.post(
            url=f"{self.v2api_host}/v2/usergroups/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=user_group.model_dump(),
        )
        handle_server_errors(result)

        return UserGroup(**result.json())

    async def update_user_group(self, user_group: UserGroup, **kwargs) -> UserGroup:
        result = await self.c.put(
            url=f"{self.v2api_host}/v2/usergroups/{user_group.metadata.name}/",
            headers=self.config.get_headers(
                with_project=False,
                with_group=True,
                group_guid=user_group.metadata.guid,
                **kwargs,
            ),
            json=user_group.model_dump(),
        )
        handle_server_errors(result)

        return UserGroup(**result.json())

    async def delete_user_group(self, group_name: str, group_guid: str, **kwargs) -> None:
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/usergroups/{group_name}/",
            headers=self.config.get_headers(
                with_project=False, with_group=True, group_guid=group_guid, **kwargs
            ),
        )
        handle_server_errors(result)

    # -------------------Roles-------------------
    async def list_roles(
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        name: str | None = None,
        **kwargs,
    ) -> RoleList:
        parameters: dict[str, Any] = {
            "continue": cont,
            "limit": limit,
        }
        if label_selector:
            parameters["labelSelector"] = label_selector
        if name:
            parameters["name"] = name

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/roles/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            params=parameters,
        )

        handle_server_errors(result)

        return RoleList(**result.json())

    async def get_role(self, role_name: str, **kwargs) -> Role:
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/roles/{role_name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)

        return Role(**result.json())

    async def create_role(self, role: Role, **kwargs) -> Role:
        result = await self.c.post(
            url=f"{self.v2api_host}/v2/roles/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=role.model_dump(),
        )
        handle_server_errors(result)

        return Role(**result.json())

    async def update_role(self, role: Role, **kwargs) -> Role:
        result = await self.c.put(
            url=f"{self.v2api_host}/v2/roles/{role.metadata.name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=role.model_dump(),
        )
        handle_server_errors(result)

        return Role(**result.json())

    async def delete_role(self, role_name: str, **kwargs) -> None:
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/roles/{role_name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)

    # -------------------RoleBindings-------------------
    async def list_role_bindings(
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        role_names: list[str] | None = None,
        subject_guids: list[str] | None = None,
        subject_names: list[str] | None = None,
        subject_kinds: list[str] | None = None,
        domain_guids: list[str] | None = None,
        domain_names: list[str] | None = None,
        domain_kinds: list[str] | None = None,
        guids: list[str] | None = None,
        **kwargs,
    ) -> RoleBindingList:
        parameters: dict[str, Any] = {
            "continue": cont,
            "limit": limit,
        }
        if label_selector:
            parameters["labelSelector"] = label_selector
        if role_names:
            parameters["roleNames"] = role_names
        if subject_guids:
            parameters["subjectGUIDS"] = subject_guids
        if subject_names:
            parameters["subjectNames"] = subject_names
        if subject_kinds:
            parameters["subjectKinds"] = subject_kinds
        if domain_guids:
            parameters["domainGUIDS"] = domain_guids
        if domain_names:
            parameters["domainNames"] = domain_names
        if domain_kinds:
            parameters["domainKinds"] = domain_kinds
        if guids:
            parameters["guids"] = guids

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/role-bindings/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            params=parameters,
        )

        handle_server_errors(result)

        return RoleBindingList(**result.json())

    async def get_role_binding(self, binding_guid: str, **kwargs) -> RoleBinding:
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/role-bindings/{binding_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)

        return RoleBinding(**result.json())

    async def create_role_binding(self, binding: RoleBinding, **kwargs) -> RoleBinding:
        result = await self.c.post(
            url=f"{self.v2api_host}/v2/role-bindings/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=binding.model_dump(),
        )
        handle_server_errors(result)

        return RoleBinding(**result.json())

    async def update_role_binding(self, binding: Role, **kwargs) -> RoleBinding:
        result = await self.c.put(
            url=f"{self.v2api_host}/v2/roles/{binding.metadata.guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=binding.model_dump(),
        )
        handle_server_errors(result)

        return RoleBinding(**result.json())

    async def delete_role_binding(self, binding_guid: str, **kwargs) -> None:
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/role-bindings/{binding_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)
