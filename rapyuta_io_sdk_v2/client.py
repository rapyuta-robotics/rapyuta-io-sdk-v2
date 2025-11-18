# Copyright 2025 Rapyuta Robotics
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
    SecretCreate,
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
    BulkRoleBindingUpdate,
    RoleList,
    OAuth2UpdateURI,
    ServiceAccountList,
    ServiceAccount,
)
from rapyuta_io_sdk_v2.models.serviceaccount import (
    ServiceAccountToken,
    ServiceAccountTokenInfo,
    ServiceAccountTokenList,
)
from rapyuta_io_sdk_v2.utils import handle_server_errors


class Client:
    """Client class offers sync client for the v2 APIs.

    Args:
        config (Configuration): Configuration object.
        **kwargs: Additional keyword arguments.
    """

    def __init__(self, config: Configuration | None = None, **kwargs) -> None:
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
                    f"rio-sdk-v2;N/A;{platform.processor() or platform.machine()};{platform.system()};{platform.release()} {platform.version()}"
                )
            },
        )
        self.v2api_host = self.config.hosts.get("v2api_host")
        self.rip_host = self.config.hosts.get("rip_host")

    def get_auth_token(self, email: str, password: str) -> str:
        """Get the authentication token for the user.

        Args:
            email (str)
            password (str)

        Returns:
            str: authentication token
        """
        result = self.c.post(
            url=f"{self.rip_host}/user/login",
            headers={"Content-Type": "application/json"},
            json={
                "email": email,
                "password": password,
            },
        )
        handle_server_errors(result)
        return result.json()["data"].get("token")

    def login(self, email: str, password: str) -> None:
        """Get the authentication token for the user.

        Args:
            email (str)
            password (str)

        Returns:
            str: authentication token
        """

        token = self.get_auth_token(email, password)
        self.config.auth_token = token

    def logout(self, token: str | None = None) -> None:
        """Expire the authentication token.

        Args:
            token (str): The token to expire.
        """

        if token is None:
            token = self.config.auth_token

        result = self.c.post(
            url=f"{self.rip_host}/user/logout",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        handle_server_errors(result)

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

        result = self.c.post(
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
    def get_organization(
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
        organization_guid = organization_guid or self.config.organization_guid

        result = self.c.get(
            url=f"{self.v2api_host}/v2/organizations/{organization_guid}/",
            headers=self.config.get_headers(
                with_project=False, organization_guid=organization_guid, **kwargs
            ),
        )
        handle_server_errors(result)
        return Organization(**result.json())

    def update_organization(
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

        result = self.c.put(
            url=f"{self.v2api_host}/v2/organizations/{organization_guid}/",
            headers=self.config.get_headers(
                with_project=False, organization_guid=organization_guid, **kwargs
            ),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return Organization(**result.json())

    # ---------------------User--------------------
    def list_users(
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

        result = self.c.get(
            url=f"{self.v2api_host}/v2/users/",
            headers=self.config.get_headers(
                with_project=False, organization_guid=organization_guid, **kwargs
            ),
            params=parameters,
        )

        handle_server_errors(result)

        return UserList(**result.json())

    def get_myself(self, **kwargs) -> User:
        """Get User details.

        Returns:
            User: User details as a User object.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/users/me/",
            headers=self.config.get_headers(
                with_project=False, with_organization=False, **kwargs
            ),
        )
        handle_server_errors(result)
        return User(**result.json())

    def update_user(self, body: User | dict[str, Any], **kwargs) -> User:
        """Update the user details.

        Args:
            body (dict): User details

        Returns:
            User: User details as a User object.
        """
        if isinstance(body, dict):
            body = User.model_validate(body)

        result = self.c.put(
            url=f"{self.v2api_host}/v2/users/me/",
            headers=self.config.get_headers(
                with_project=False, with_organization=False, **kwargs
            ),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return User(**result.json())

    # -------------------Project-------------------
    def get_project(self, project_guid: str | None = None, **kwargs) -> Project:
        """Get a project by its GUID.

        If no project or organization GUID is provided,
        the default project and organization GUIDs will
        be picked from the current configuration.

        Args:
            project_guid (str): user provided project GUID or config project GUID

        Raises:
            ValueError: If organization_guid or project_guid is None

        Returns:
            Project: Project details as a Project object.
        """
        project_guid = project_guid or self.config.project_guid

        result = self.c.get(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(
                with_project=True, project_guid=project_guid, **kwargs
            ),
        )
        handle_server_errors(result)
        return Project(**result.json())

    def list_projects(
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

        Returns:
            Dict[str, Any]: List of projects with items validated as Project objects.
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

        result = self.c.get(
            url=f"{self.v2api_host}/v2/projects/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            params=parameters,
        )

        handle_server_errors(response=result)
        return ProjectList(**result.json())

    def create_project(self, body: Project | dict[str, Any], **kwargs) -> Project:
        """Create a new project.

        Args:
            body (object): Project details

        Returns:
            Project: Project creation result.
        """
        if isinstance(body, dict):
            body = Project.model_validate(body)

        result = self.c.post(
            url=f"{self.v2api_host}/v2/projects/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return Project(**result.json())

    def update_project(
        self, body: Project | dict[str, Any], project_guid: str | None = None, **kwargs
    ) -> Project:
        """Update a project by its GUID.

        Args:
            body (object): Project details
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            Project: Project update result.
        """
        if isinstance(body, dict):
            body = Project.model_validate(body)

        result = self.c.put(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return Project(**result.json())

    def delete_project(self, project_guid: str, **kwargs) -> None:
        """Delete a project by its GUID.

        Args:
            project_guid (str): Project GUID

        Returns:
            None if successful.
        """

        result = self.c.delete(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(
                with_project=True, project_guid=project_guid, **kwargs
            ),
        )
        handle_server_errors(result)
        return None

    def update_project_owner(
        self, body: dict, project_guid: str = None, **kwargs
    ) -> dict[str, Any]:
        """Update the owner of a project by its GUID.

        Returns:
            Dict[str, Any]: Project owner update result.
        """
        project_guid = project_guid or self.config.project_guid

        result = self.c.put(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/owner/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )
        handle_server_errors(result)
        return result.json()

    # -------------------Package-------------------
    def list_packages(
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
            Dict[str, Any]: List of packages with items validated as Package objects.
        """

        result = self.c.get(
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

    def create_package(self, body: Package | dict[str, Any], **kwargs) -> Package:
        """Create a new package.

        The Payload is the JSON format of the Package Manifest.
        For a documented example, run the rio explain package command.

        Returns:
            Package: Package details.
        """
        if isinstance(body, dict):
            body = Package.model_validate(body)

        result = self.c.post(
            url=f"{self.v2api_host}/v2/packages/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )

        handle_server_errors(result)
        return Package(**result.json())

    def get_package(self, name: str, version: str | None = None, **kwargs) -> Package:
        """Get a package by its name.

        Args:
            name (str): Package name
            version (str, optional): Package version. Defaults to None.

        Returns:
            Package: Package details as a Package object.
        """

        result = self.c.get(
            url=f"{self.v2api_host}/v2/packages/{name}/",
            headers=self.config.get_headers(**kwargs),
            params={"version": version},
        )

        handle_server_errors(response=result)
        return Package(**result.json())

    def delete_package(self, name: str, version: str, **kwargs) -> None:
        """Delete a package by its name.

        Args:
            name (str): Package name

        Returns:
            None if successful.
        """

        result = self.c.delete(
            url=f"{self.v2api_host}/v2/packages/{name}/",
            headers=self.config.get_headers(**kwargs),
            params={"version": version},
        )
        handle_server_errors(result)

    # -------------------Deployment-------------------
    def list_deployments(
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
            Dict[str, Any]: List of deployments with items validated as Deployment objects.
        """

        result = self.c.get(
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

    def create_deployment(
        self, body: Deployment | dict[str, Any], **kwargs
    ) -> Deployment:
        """Create a new deployment.

        Args:
            body (object): Deployment details

        Returns:
            Deployment: Deployment details.
        """
        if isinstance(body, dict):
            body = Deployment.model_validate(body)

        result = self.c.post(
            url=f"{self.v2api_host}/v2/deployments/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )

        handle_server_errors(result)
        return Deployment(**result.json())

    def get_deployment(self, name: str, guid: str | None = None, **kwargs) -> Deployment:
        """Get a deployment by its name.

        Returns:
            Deployment details as a dictionary.
        """

        result = self.c.get(
            url=f"{self.v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(**kwargs),
            params={"guid": guid},
        )

        handle_server_errors(result)
        return Deployment(**result.json())

    def update_deployment(
        self, body: Deployment | dict[str, Any], **kwargs
    ) -> Deployment:
        """Update a deployment by its name.

        Returns:
            Deployment: Deployment details.
        """
        if isinstance(body, dict):
            body = Deployment.model_validate(body)

        result = self.c.patch(
            url=f"{self.v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return Deployment(**result.json())

    def delete_deployment(self, name: str, **kwargs) -> None:
        """Delete a deployment by its name.

        Returns:
            None if successful.
        """

        result = self.c.delete(
            url=f"{self.v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    def get_deployment_graph(self, name: str, **kwargs) -> dict[str, Any]:
        """Get a deployment graph by its name. [Experimental]

        Returns:
            Deployment graph as a dictionary.
        """

        result = self.c.get(
            url=f"{self.v2api_host}/v2/deployments/{name}/graph/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return result.json()

    def get_deployment_history(
        self, name: str, guid: str | None = None, **kwargs
    ) -> dict[str, Any]:
        """Get a deployment history by its name.

        Returns:
            Deployment history as a dictionary.
        """

        result = self.c.get(
            url=f"{self.v2api_host}/v2/deployments/{name}/history/",
            headers=self.config.get_headers(**kwargs),
            params={"guid": guid},
        )
        handle_server_errors(result)
        return result.json()

    def stream_deployment_logs(self, name: str, executable: str, replica: int = 0):
        url = f"{self.v2api_host}/v2/deployments/{name}/logs/?replica={replica}&executable={executable}"

        with self.c.stream("GET", url=url, headers=self.config.get_headers()) as response:
            # check status without reading the streaming content
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    yield line

    # -------------------Disks-------------------
    def list_disks(
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

        result = self.c.get(
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
        handle_server_errors(result)
        return DiskList(**result.json())

    def get_disk(self, name: str, **kwargs) -> Disk:
        """Get a disk by its name.

        Args:
            name (str): Disk name

        Returns:
            Disk details as a dictionary.
        """

        result = self.c.get(
            url=f"{self.v2api_host}/v2/disks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return Disk(**result.json())

    def create_disk(self, body: Disk | dict[str, Any], **kwargs) -> Disk:
        """Create a new disk.

        Returns:
            Disk: Disk details.
        """
        if isinstance(body, dict):
            body = Disk.model_validate(body)

        result = self.c.post(
            url=f"{self.v2api_host}/v2/disks/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return Disk(**result.json())

    def delete_disk(self, name: str, **kwargs) -> None:
        """Delete a disk by its name.

        Args:
            name (str): Disk name

        Returns:
            None if successful.
        """

        result = self.c.delete(
            url=f"{self.v2api_host}/v2/disks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    # -------------------Device--------------------------

    def get_device_daemons(self, device_guid: str):
        """
        Retrieve the list of daemons associated with a specific device.

        Args:
            device_guid (str): The unique identifier (GUID) of the device.

        Returns:
            dict: The JSON response containing information about the device's daemons.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/devices/daemons/{device_guid}/",
            headers=self.config.get_headers(),
        )

        handle_server_errors(response=result)
        return Daemon(**result.json())

    # -------------------Static Routes-------------------
    def list_staticroutes(
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

        result = self.c.get(
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
        handle_server_errors(result)
        return StaticRouteList(**result.json())

    def create_staticroute(
        self, body: StaticRoute | dict[str, Any], **kwargs
    ) -> StaticRoute:
        """Create a new static route.

        Returns:
            StaticRoute: Static route details.
        """
        if isinstance(body, dict):
            body = StaticRoute.model_validate(body)

        result = self.c.post(
            url=f"{self.v2api_host}/v2/staticroutes/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )

        handle_server_errors(result)
        return StaticRoute(**result.json())

    def get_staticroute(self, name: str, **kwargs) -> StaticRoute:
        """Get a static route by its name.

        Args:
            name (str): Static route name

        Returns:
            Static route details as a dictionary.
        """

        result = self.c.get(
            url=f"{self.v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return StaticRoute(**result.json())

    def update_staticroute(
        self, name: str, body: StaticRoute | dict[str, Any], **kwargs
    ) -> StaticRoute:
        """Update a static route by its name.

        Args:
            name (str): Static route name
            body (dict): Update details

        Returns:
            StaticRoute: Static route details.
        """
        if isinstance(body, dict):
            body = StaticRoute.model_validate(body)

        result = self.c.put(
            url=f"{self.v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )

        handle_server_errors(result)
        return StaticRoute(**result.json())

    def delete_staticroute(self, name: str, **kwargs) -> None:
        """Delete a static route by its name.

        Args:
            name (str): Static route name

        Returns:
            None if successful.
        """

        result = self.c.delete(
            url=f"{self.v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    # -------------------Networks-------------------
    def list_networks(
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

        result = self.c.get(
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

        handle_server_errors(result)
        return NetworkList(**result.json())

    def create_network(self, body: Network | dict[str, Any], **kwargs) -> Network:
        """Create a new network.

        Returns:
            Network: Network details.
        """
        if isinstance(body, dict):
            body = Network.model_validate(body)

        result = self.c.post(
            url=f"{self.v2api_host}/v2/networks/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return Network(**result.json())

    def get_network(self, name: str, **kwargs) -> Network:
        """Get a network by its name.

        Args:
            name (str): Network name

        Returns:
            Network details as a Network class object.
        """

        result = self.c.get(
            url=f"{self.v2api_host}/v2/networks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return Network(**result.json())

    def delete_network(self, name: str, **kwargs) -> None:
        """Delete a network by its name.

        Args:
            name (str): Network name

        Returns:
            None if successful.
        """

        result = self.c.delete(
            url=f"{self.v2api_host}/v2/networks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    # -------------------Secrets-------------------

    def list_secrets(
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

        result = self.c.get(
            url=f"{self.v2api_host}/v2/secrets/",
            headers=self.config.get_headers(**kwargs),
            params=parameters,
        )

        handle_server_errors(result)
        return SecretList(**result.json())

    def create_secret(self, body: SecretCreate | dict[str, Any], **kwargs) -> Secret:
        """Create a new secret.

        Returns:
            Secret: Secret details.
        """
        if isinstance(body, dict):
            body = SecretCreate.model_validate(body)

        result = self.c.post(
            url=f"{self.v2api_host}/v2/secrets/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )

        handle_server_errors(result)
        return Secret(**result.json())

    def get_secret(self, name: str, **kwargs) -> Secret:
        """Get a secret by its name.

        Args:
            name (str): Secret name

        Returns:
            Secret details as a dictionary.
        """

        result = self.c.get(
            url=f"{self.v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(response=result)
        return Secret(**result.json())

    def update_secret(
        self, name: str, body: SecretCreate | dict[str, Any], **kwargs
    ) -> Secret:
        """Update a secret by its name.

        Args:
            name (str): Secret name
            body (dict): Update details

        Returns:
            Secret: Secret details.
        """
        if isinstance(body, dict):
            body = SecretCreate.model_validate(body)

        result = self.c.put(
            url=f"{self.v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )

        handle_server_errors(response=result)
        return Secret(**result.json())

    def delete_secret(self, name: str, **kwargs) -> None:
        """Delete a secret by its name.

        Args:
            name (str): Secret name

        Returns:
            None if successful.
        """

        result = self.c.delete(
            url=f"{self.v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    # -------------------OAuth2 Clients-------------------
    def list_oauth2_clients(
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        names: list[str] | None = None,
        regions: list[str] | None = None,
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
        params: dict[str, Any] = {
            "continue": cont,
            "limit": limit,
        }
        if label_selector is not None:
            params["labelSelector"] = label_selector
        if names is not None:
            params["names"] = names
        if regions is not None:
            params["regions"] = regions

        result = self.c.get(
            url=f"{self.v2api_host}/v2/oauth2clients/",
            headers=self.config.get_headers(**kwargs),
            params=params,
        )
        handle_server_errors(result)
        return result.json()

    def get_oauth2_client(self, client_id: str, **kwargs) -> dict[str, Any]:
        """Get an OAuth2 client by its client_id.

        Args:
            client_id (str): OAuth2 client ID

        Returns:
            OAuth2 client details as a dictionary.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/oauth2clients/{client_id}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return result.json()

    def create_oauth2_client(self, body: dict[str, Any], **kwargs) -> dict[str, Any]:
        """Create a new OAuth2 client.

        Args:
            body (dict): OAuth2 client details

        Returns:
            OAuth2 client details as a dictionary.
        """
        result = self.c.post(
            url=f"{self.v2api_host}/v2/oauth2/clients/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )
        handle_server_errors(result)
        return result.json()

    def update_oauth2_client(
        self, client_id: str, body: dict[str, Any], **kwargs
    ) -> dict[str, Any]:
        """Update an OAuth2 client by its client_id.

        Args:
            client_id (str): OAuth2 client ID
            body (dict): Update details

        Returns:
            OAuth2 client details as a dictionary.
        """
        result = self.c.put(
            url=f"{self.v2api_host}/v2/oauth2/clients/{client_id}/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )
        handle_server_errors(result)
        return result.json()

    def update_oauth2_client_uris(
        self, client_id: str, update: OAuth2UpdateURI, **kwargs
    ) -> dict[str, Any]:
        """Update OAuth2 client URIs.

        Args:
            client_id (str): OAuth2 client ID
            uris (dict): URIs update payload

        Returns:
            OAuth2 client details as a dictionary.
        """
        result = self.c.patch(
            url=f"{self.v2api_host}/v2/oauth2/clients/{client_id}/uris/",
            headers=self.config.get_headers(**kwargs),
            json=update.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return result.json()

    def delete_oauth2_client(self, client_id: str, **kwargs) -> None:
        """Delete an OAuth2 client by its client_id.

        Args:
            client_id (str): OAuth2 client ID

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/oauth2/clients/{client_id}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    # -------------------Config Trees-------------------

    def list_configtrees(
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        with_project: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """List all config trees in a project.

        Args:
            cont (int, optional): Start index of config trees. Defaults to 0.
            limit (int, optional): Number of config trees to list. Defaults to 50.
            label_selector (List[str], optional): Define labelSelector to get config trees from. Defaults to None.
            with_project (bool, optional): Include project. Defaults to True.

        Returns:
            List of config trees as a dictionary.
        """
        parameters: dict[str, Any] = {
            "continue": cont,
            "limit": limit,
        }
        if label_selector:
            parameters["labelSelector"] = label_selector
        result = self.c.get(
            url=f"{self.v2api_host}/v2/configtrees/",
            headers=self.config.get_headers(with_project=with_project, **kwargs),
            params=parameters,
        )
        handle_server_errors(result)
        return result.json()

    def create_configtree(
        self, body: dict[str, Any], with_project: bool = True, **kwargs
    ) -> dict[str, Any]:
        """Create a new config tree.

        Args:
            body (object): Config tree details
            with_project (bool, optional): Work in the project scope. Defaults to True.

        Returns:
            Config tree details as a dictionary.
        """
        result = self.c.post(
            url=f"{self.v2api_host}/v2/configtrees/",
            headers=self.config.get_headers(with_project=with_project, **kwargs),
            json=body,
        )
        handle_server_errors(result)
        return result.json()

    def get_configtree(
        self,
        name: str,
        content_types: list[str] | None = None,
        include_data: bool = False,
        key_prefixes: list[str] | None = None,
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
        parameters = {}
        if content_types:
            parameters["contentTypes"] = content_types
        if include_data:
            parameters["includeData"] = include_data
        if key_prefixes:
            parameters["keyPrefixes"] = key_prefixes
        if revision:
            parameters["revision"] = revision
        result = self.c.get(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(with_project=with_project, **kwargs),
            params=parameters,
        )
        handle_server_errors(result)
        return result.json()

    def set_configtree_revision(
        self,
        name: str,
        configtree: dict[str, Any],
        project_guid: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Set a config tree revision.

        Args:
            name (str): Config tree name
            configtree (object): Config tree details
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            Config tree details as a dictionary.
        """
        result = self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=configtree,
        )
        handle_server_errors(result)
        return result.json()

    def update_configtree(
        self, name: str, body: dict[str, Any], with_project: bool = True, **kwargs
    ) -> dict[str, Any]:
        """Update a config tree by its name.

        Args:
            name (str): Config tree name
            body (dict): Update details
            with_project (bool, optional): Work in the project scope. Defaults to True.

        Returns:
            Config tree details as a dictionary.
        """
        result = self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(with_project=with_project, **kwargs),
            json=body,
        )
        handle_server_errors(result)
        return result.json()

    def delete_configtree(self, name: str, **kwargs) -> None:
        """Delete a config tree by its name.

        Args:
            name (str): Config tree name

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    def list_revisions(
        self,
        tree_name: str,
        cont: int = 0,
        limit: int = 50,
        committed: bool = False,
        label_selector: list[str] | None = None,
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
        parameters: dict[str, Any] = {
            "continue": cont,
            "limit": limit,
            "committed": committed,
        }
        if label_selector:
            parameters["labelSelector"] = label_selector
        result = self.c.get(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/",
            headers=self.config.get_headers(**kwargs),
            params=parameters,
        )
        handle_server_errors(result)
        return result.json()

    def create_revision(
        self,
        name: str,
        body: dict[str, Any] | None = None,
        project_guid: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a new revision.

        Args:
            name (str): Config tree name
            body (object): Revision details
            project_guid (str): Project GUID (optional)

        Returns:
            Revision details as a dictionary.
        """
        result = self.c.post(
            url=f"{self.v2api_host}/v2/configtrees/{name}/revisions/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=body,
        )
        handle_server_errors(result)
        return result.json()

    def put_keys_in_revision(
        self, name: str, revision_id: str, config_values: dict[str, Any], **kwargs
    ) -> dict[str, Any]:
        """Put keys in a revision.

        Args:
            name (str): Config tree name
            revision_id (str): Config tree revision ID
            config_values (dict): Config values

        Returns:
            Revision details as a dictionary.
        """
        result = self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/",
            headers=self.config.get_headers(**kwargs),
            json=config_values,
        )
        handle_server_errors(result)
        return result.json()

    def commit_revision(
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
        result = self.c.patch(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=config_tree_revision,
        )
        handle_server_errors(result)
        return result.json()

    def get_key_in_revision(
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
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            Key details as a dictionary.
        """

        result = self.c.get(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/{key}",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
        )
        # The data received from the API is always in string format. To use
        # appropriate data-type in Python (as well in exports), we are
        # passing it through YAML parser.
        return safe_load(result.text)

    def put_key_in_revision(
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
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            Key details as a dictionary.
        """
        result = self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
        )
        handle_server_errors(result)
        return result.json()

    def delete_key_in_revision(
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
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
        )
        handle_server_errors(result)

    def rename_key_in_revision(
        self,
        tree_name: str,
        revision_id: str,
        key: str,
        config_key_rename: dict[str, Any],
        project_guid: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Rename a key in a revision.

        Args:
            tree_name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            config_key_rename (object): Key rename details
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            Key details as a dictionary.
        """
        result = self.c.patch(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=config_key_rename,
        )
        handle_server_errors(result)
        return result.json()

    # Managed Service API

    def list_providers(self) -> ManagedServiceProviderList:
        """List all providers.

        Returns:
            List of providers as a dictionary.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/managedservices/providers/",
            headers=self.config.get_headers(with_project=False),
        )
        handle_server_errors(result)
        return ManagedServiceProviderList(**result.json())

    def list_instances(
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
        result = self.c.get(
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

    def get_instance(self, name: str) -> ManagedServiceInstance:
        """Get an instance by its name.

        Args:
            name (str): Instance name

        Returns:
            Instance details as a dictionary.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/managedservices/{name}/",
            headers=self.config.get_headers(),
        )
        handle_server_errors(result)
        return ManagedServiceInstance(**result.json())

    def create_instance(
        self, body: ManagedServiceInstance | dict[str, Any]
    ) -> ManagedServiceInstance:
        """Create a new instance.

        Returns:
            Instance details as a ManagedServiceInstance object.
        """
        if isinstance(body, dict):
            body = ManagedServiceInstance.model_validate(body)

        result = self.c.post(
            url=f"{self.v2api_host}/v2/managedservices/",
            headers=self.config.get_headers(),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return ManagedServiceInstance(**result.json())

    def delete_instance(self, name: str) -> None:
        """Delete an instance.

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/managedservices/{name}/",
            headers=self.config.get_headers(),
        )
        handle_server_errors(result)

    def list_instance_bindings(
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
        result = self.c.get(
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

    def create_instance_binding(
        self, instance_name: str, body: ManagedServiceBinding | dict[str, Any]
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

        result = self.c.post(
            url=f"{self.v2api_host}/v2/managedservices/{instance_name}/bindings/",
            headers=self.config.get_headers(),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return ManagedServiceBinding(**result.json())

    def get_instance_binding(
        self, instance_name: str, name: str
    ) -> ManagedServiceBinding:
        """Get an instance binding by its name.

        Args:
            instance_name (str): Instance name.
            name (str): Instance binding name.

        Returns:
            Instance binding details as a dictionary.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/managedservices/{instance_name}/bindings/{name}/",
            headers=self.config.get_headers(),
        )
        handle_server_errors(result)
        return ManagedServiceBinding(**result.json())

    def delete_instance_binding(self, instance_name: str, name: str) -> None:
        """Delete an instance binding.

        Args:
            instance_name (str): Instance name.
            name (str): Instance binding name.

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/managedservices/{instance_name}/bindings/{name}/",
            headers=self.config.get_headers(),
        )
        handle_server_errors(result)

    # -------------------Usergroup-------------------
    def list_user_groups(
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

        result = self.c.get(
            url=f"{self.v2api_host}/v2/usergroups/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            params=parameters,
        )

        handle_server_errors(response=result)

        return UserGroupList(**result.json())

    def get_user_group(self, group_name: str, group_guid: str, **kwargs) -> UserGroup:
        result = self.c.get(
            url=f"{self.v2api_host}/v2/usergroups/{group_name}/",
            headers=self.config.get_headers(
                with_project=False, with_group=True, group_guid=group_guid, **kwargs
            ),
        )
        handle_server_errors(result)

        return UserGroup(**result.json())

    def create_user_group(self, user_group: UserGroup | dict, **kwargs) -> UserGroup:
        if isinstance(user_group, dict):
            user_group = UserGroup.model_validate(user_group)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/usergroups/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=user_group.model_dump(by_alias=True),
        )
        handle_server_errors(result)

        return UserGroup(**result.json())

    def update_user_group(self, user_group: UserGroup | dict, **kwargs) -> UserGroup:
        if isinstance(user_group, dict):
            user_group = UserGroup.model_validate(user_group)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/usergroups/{user_group.metadata.name}/",
            headers=self.config.get_headers(
                with_project=False,
                with_group=True,
                group_guid=user_group.metadata.guid,
                **kwargs,
            ),
            json=user_group.model_dump(by_alias=True),
        )
        handle_server_errors(result)

        return UserGroup(**result.json())

    def delete_user_group(self, group_name: str, group_guid: str, **kwargs) -> None:
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/usergroups/{group_name}/",
            headers=self.config.get_headers(
                with_project=False, with_group=True, group_guid=group_guid, **kwargs
            ),
        )
        handle_server_errors(result)

    # -------------------Roles-------------------
    def list_roles(
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

        result = self.c.get(
            url=f"{self.v2api_host}/v2/roles/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            params=parameters,
        )

        handle_server_errors(result)

        return RoleList(**result.json())

    def get_role(self, role_name: str, **kwargs) -> Role:
        result = self.c.get(
            url=f"{self.v2api_host}/v2/roles/{role_name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)

        return Role(**result.json())

    def create_role(self, role: Role | dict, **kwargs) -> Role:
        if isinstance(role, dict):
            role = Role.model_validate(role)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/roles/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=role.model_dump(by_alias=True),
        )
        handle_server_errors(result)

        return Role(**result.json())

    def update_role(self, role: Role, **kwargs) -> Role:
        if isinstance(role, dict):
            role = Role.model_validate(role)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/roles/{role.metadata.name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=role.model_dump(by_alias=True),
        )
        handle_server_errors(result)

        return Role(**result.json())

    def delete_role(self, role_name: str, **kwargs) -> None:
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/roles/{role_name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)

    # -------------------RoleBindings-------------------
    def list_role_bindings(
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

        result = self.c.get(
            url=f"{self.v2api_host}/v2/role-bindings/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            params=parameters,
        )

        handle_server_errors(result)

        return RoleBindingList(**result.json())

    def get_role_binding(self, binding_guid: str, **kwargs) -> RoleBinding:
        result = self.c.get(
            url=f"{self.v2api_host}/v2/role-bindings/{binding_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)

        return RoleBinding(**result.json())

    def update_role_binding(
        self, binding: BulkRoleBindingUpdate | dict, **kwargs
    ) -> RoleBinding:
        if isinstance(binding, dict):
            binding = BulkRoleBindingUpdate.model_validate(binding)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/role-bindings/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=binding.model_dump(by_alias=True),
        )
        handle_server_errors(result)

        try:
            return RoleBinding(**result.json())
        except Exception:
            return result.json()

    # -------------------ServiceAccount-------------------

    def list_service_accounts(
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        name: str | None = None,
        regions: list[str] | None = None,
        **kwargs,
    ) -> ServiceAccountList:
        parameters: dict[str, Any] = {
            "continue": cont,
            "limit": limit,
        }
        if label_selector:
            parameters["labelSelector"] = label_selector
        if name:
            parameters["name"] = name
        if regions:
            parameters["regions"] = regions

        result = self.c.get(
            url=f"{self.v2api_host}/v2/serviceaccounts/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            params=parameters,
        )

        handle_server_errors(result)

        return ServiceAccountList(**result.json())

    def get_service_account(
        self,
        name: str,
        **kwargs,
    ) -> ServiceAccount:
        result = self.c.get(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )

        handle_server_errors(result)
        return ServiceAccount(**result.json())

    def create_service_account(
        self,
        service_account: ServiceAccount | dict,
        **kwargs,
    ) -> ServiceAccount:
        if isinstance(service_account, dict):
            service_account = ServiceAccount.model_validate(service_account)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/serviceaccounts/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=service_account.model_dump(by_alias=True),
        )

        handle_server_errors(result)
        return ServiceAccount(**result.json())

    def update_service_account(
        self,
        service_account: ServiceAccount | dict,
        name: str | None,
        **kwargs,
    ) -> ServiceAccount:
        if isinstance(service_account, dict):
            service_account = ServiceAccount.model_validate(service_account)
        if not name:
            name = service_account.metadata.name
        result = self.c.put(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=service_account.model_dump(by_alias=True),
        )

        handle_server_errors(result)
        return ServiceAccount(**result.json())

    def delete_service_account(
        self,
        name: str,
        **kwargs,
    ) -> None:
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )

        handle_server_errors(result)
        return None

    def list_service_account_tokens(
        self, name: str, cont: int = 0, limit: int = 50, **kwargs
    ) -> ServiceAccountTokenList:

        result = self.c.get(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/token/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )

        handle_server_errors(result)

        return ServiceAccountTokenList(**result.json())

    def create_service_account_token(
        self, name: str, expiry_at: ServiceAccountToken | dict, **kwargs
    ) -> ServiceAccountTokenInfo:
        if isinstance(expiry_at, dict):
            expiry_at = ServiceAccountToken.model_validate(expiry_at)

        result = self.c.post(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/token/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=expiry_at.model_dump(by_alias=True, mode="json"),
        )

        handle_server_errors(result)

        return ServiceAccountTokenInfo(**result.json())

    def refresh_service_account_token(
        self, name: str, token_id: str, expiry_at: ServiceAccountToken | dict, **kwargs
    ) -> ServiceAccountTokenInfo:
        if isinstance(expiry_at, dict):
            expiry_at = ServiceAccountToken.model_validate(expiry_at)

        result = self.c.patch(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/token/{token_id}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=expiry_at.model_dump(by_alias=True, mode="json"),
        )

        handle_server_errors(result)

        return ServiceAccountTokenInfo(**result.json())

    def delete_service_account_token(self, name: str, token_id: str, **kwargs) -> None:
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/token/{token_id}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )

        handle_server_errors(result)

        return None
