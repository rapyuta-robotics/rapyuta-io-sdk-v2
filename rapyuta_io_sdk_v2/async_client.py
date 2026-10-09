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

"""Asynchronous client for rapyuta.io v2 resource APIs."""

import platform
from typing import Any, cast

import httpx
from pydantic import ValidationError as PydanticValidationError
from yaml import safe_load

from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.models import (
    BulkRoleBindingUpdate,
    Daemon,
    Deployment,
    DeploymentList,
    Disk,
    DiskList,
    FileUpload,
    FileUploadList,
    ManagedServiceBinding,
    ManagedServiceBindingList,
    ManagedServiceInstance,
    ManagedServiceInstanceList,
    ManagedServiceProviderList,
    Network,
    NetworkList,
    OAuth2UpdateURI,
    Organization,
    Package,
    PackageList,
    Project,
    ProjectList,
    Role,
    RoleBinding,
    RoleBindingList,
    RoleList,
    Secret,
    SecretCreate,
    SecretList,
    ServiceAccount,
    ServiceAccountList,
    SharedURL,
    SharedURLList,
    StaticRoute,
    StaticRouteList,
    User,
    UserGroup,
    UserGroupList,
    UserList,
    UserPermissions,
)
from rapyuta_io_sdk_v2.models.serviceaccount import (
    ServiceAccountToken,
    ServiceAccountTokenInfo,
    ServiceAccountTokenList,
)
from rapyuta_io_sdk_v2.models.sshkey import (
    SSHKeySignRequest,
    SSHKeySignResponse,
)
from rapyuta_io_sdk_v2.utils import handle_server_errors


class AsyncClient:
    """Make asynchronous requests to rapyuta.io v2 resource APIs."""

    def __init__(self, config: Configuration | None = None, **kwargs: object) -> None:
        """Initialize the instance with the supplied configuration.

        Args:
            config: SDK authentication and environment configuration.
            **kwargs: Client options; timeout sets the HTTP request timeout.
        """
        self.config: Configuration = config or Configuration()
        timeout: float = float(cast("float", kwargs.get("timeout", 10)))
        self.c: httpx.AsyncClient = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=5,
                keepalive_expiry=30,
            ),
            headers={
                "User-Agent": (
                    f"rio-sdk-v2;N/A;{platform.processor() or platform.machine()};"
                    f"{platform.system()};{platform.release()};{platform.version()}".rstrip()
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
                    f"rio-sdk-v2;N/A;{platform.processor() or platform.machine()};"
                    f"{platform.system()};{platform.release()} {platform.version()}"
                )
            },
        )
        self.rip_host = self.config.hosts.get("rip_host")
        self.v2api_host = self.config.hosts.get("v2api_host")

    def get_auth_token(self, email: str, password: str) -> str:
        """Get the authentication token for the user.

        Args:
            email: Email address used to authenticate the user.
            password: Password used to authenticate the user.

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
            email: Email address used to authenticate the user.
            password: Password used to authenticate the user.

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

        result = self.sync_client.post(
            url=f"{self.rip_host}/user/logout",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        handle_server_errors(result)

    # Keep the positional signature accepted by existing SDK callers.
    def refresh_token(self, token: str | None = None, set_token: bool = True) -> str:  # noqa: FBT001, FBT002
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
        self, organization_guid: str | None = None, **kwargs: object
    ) -> Organization:
        """Get an organization by its GUID.

        If organization GUID is provided, the current organization GUID will be
        picked from the current configuration.

        Args:
            organization_guid (str): user provided organization GUID.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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
        **kwargs: object,
    ) -> Organization:
        """Update an organization by its GUID.

        Args:
            body (dict): Organization details
            organization_guid (str, optional): Organization GUID. Defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return Organization(**result.json())

    # ---------------------User--------------------
    # Keep the positional signature accepted by existing SDK callers.
    async def list_users(  # noqa: PLR0917
        self,
        cont: int = 0,
        limit: int = 50,
        organization_guid: str | None = None,
        guid: str | None = None,
        **kwargs: object,
    ) -> UserList:
        """List users.

        Args:
            cont: Pagination continuation token.
            limit: Maximum number of resources per page.
            organization_guid: Organization guid.
            guid: Guid.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
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

    async def add_user(self, user: User | dict, **kwargs: object) -> User:
        """Add a User in Organization.

        Args:
            user: User.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            User: User details as a user object.
        """
        if isinstance(user, dict):
            user = User.model_validate(user)
        result = await self.c.post(
            url=f"{self.v2api_host}/v2/users/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            body=user.model_dump(by_alias=True),
        )

        handle_server_errors(result)

        return UserList(**result.json())

    async def get_myself(self, **kwargs: object) -> User:
        """Get my User details.

        Args:
            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    async def update_myself(
        self, body: User | dict[str, Any], **kwargs: object
    ) -> User:
        """Update my user details.

        Args:
            body (dict): User details

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return User(**result.json())

    async def get_user(self, email_id: str, **kwargs: object) -> User:
        """Get User details.

        Args:
            email_id: Email address identifying the user.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            User: User details as a User object.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/users/{email_id}",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)
        return User(**result.json())

    async def update_user(
        self, email_id: str, body: User | dict[str, Any], **kwargs: object
    ) -> User:
        """Update the user details.

        Args:
            body (dict): User details

            email_id: Email address identifying the user.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            User: User details as a User object.
        """
        if isinstance(body, dict):
            body = User.model_validate(body)

        result = await self.c.put(
            url=f"{self.v2api_host}/v2/users/{email_id}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return User(**result.json())

    async def delete_user(self, email_id: str, **kwargs: object) -> None:
        """Delete the User.

        Args:
            email_id: Email address identifying the user.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/users/{email_id}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)

    async def get_user_permissions(
        self,
        user_guid: str,
        organization_guid: str | None = None,
        **kwargs: object,
    ) -> UserPermissions:
        """Get user permissions for an organization.

        Args:
            user_guid (str): User GUID
            organization_guid (str, optional): Organization GUID. Defaults to None.
            **kwargs: Additional keyword arguments

        Returns:
            UserPermissions: User permissions object containing organization,
                projects, and groups permissions
        """
        organization_guid = organization_guid or self.config.organization_guid

        headers = self.config.get_headers(
            with_project=False,
            organization_guid=organization_guid,
            **kwargs,
        )
        headers["userguid"] = user_guid

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/users/permissions/",
            headers=headers,
        )
        handle_server_errors(result)
        return UserPermissions(**result.json())

    # ----------------- Projects -----------------
    # Keep the positional signature accepted by existing SDK callers.
    async def list_projects(  # noqa: PLR0913, PLR0917
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        status: list[str] | None = None,
        organizations: list[str] | None = None,
        name: str | None = None,
        **kwargs: object,
    ) -> ProjectList:
        """List all projects in an organization.

        Args:
            cont (int, optional): Start index of projects. Defaults to 0.
            limit (int, optional): Number of projects to list. Defaults to 50.
            label_selector (list[str], optional): Define labelSelector to get
                projects from. Defaults to None.
            status (list[str], optional): Define status to get projects from.
                Defaults to None.
            organizations (list[str], optional): Define organizations to get
                projects from. Defaults to None.
            name (str, optional): Define name to get projects from. Defaults to
                None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    async def get_project(
        self, project_guid: str | None = None, **kwargs: object
    ) -> Project:
        """Get a project by its GUID.

        If no project or organization GUID is provided,
        the async default project and organization GUIDs will
        be picked from the current configuration.

        Args:
            project_guid (str): user provided project GUID or config project GUID

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Raises:
            ValueError: If organization_guid or project_guid is None

        Returns:
            Project details as a dictionary.
        """
        if project_guid is None:
            project_guid = self.config.project_guid
        if not project_guid:
            message = "project_guid is required"
            raise ValueError(message)
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)
        return Project(**result.json())

    async def create_project(
        self, body: Project | dict[str, Any], **kwargs: object
    ) -> Project:
        """Create a new project.

        Args:
            body (dict): Project details

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return Project(**result.json())

    async def update_project(
        self,
        body: Project | dict[str, Any],
        project_guid: str | None = None,
        **kwargs: object,
    ) -> Project:
        """Update a project by its GUID.

        Args:
            body (dict): Project details
            project_guid (str, optional): Project GUID. Defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            Project details as a dictionary.
        """
        if isinstance(body, dict):
            body = Project.model_validate(body)

        result = await self.c.put(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return Project(**result.json())

    async def delete_project(self, project_guid: str, **kwargs: object) -> None:
        """Delete a project by its GUID.

        Args:
            project_guid (str): Project GUID

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            None if successful.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)

    async def update_project_owner(
        self, body: dict, project_guid: str | None = None, **kwargs: object
    ) -> dict[str, Any]:
        """Update the owner of a project by its GUID.

        Args:
            body: Resource manifest or request payload.
            project_guid: Project guid.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            dict[str, Any]: Project owner update result.
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
    # Keep the positional signature accepted by existing SDK callers.
    async def list_packages(  # noqa: PLR0917
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        name: str | None = None,
        **kwargs: object,
    ) -> PackageList:
        """List all packages in a project.

        Args:
            cont (int, optional): Start index of packages. Defaults to 0.
            limit (int, optional): Number of packages to list. Defaults to 50.
            label_selector (list[str], optional): Define labelSelector to get
                packages from. Defaults to None.
            name (str, optional): Define name to get packages from. Defaults to
                None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    async def create_package(
        self, body: Package | dict[str, Any], **kwargs: object
    ) -> Package:
        """Create a new package.

        The Payload is the JSON format of the Package Manifest.
        For a documented example, run the rio explain package command.

        Args:
            body (dict): Package details

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            Package: Package details as a Package object.
        """
        if isinstance(body, dict):
            body = Package.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/packages/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )

        handle_server_errors(result)
        return Package(**result.json())

    async def get_package(
        self, name: str, version: str | None = None, **kwargs: object
    ) -> Package:
        """Get a package by its name.

        Args:
            name (str): Package name
            version (str, optional): Package version. Defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    async def delete_package(self, name: str, version: str, **kwargs: object) -> None:
        """Delete a package by its name.

        Args:
            name (str): Package name

            version: Package version identifying the resource.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            None if successful.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/packages/{name}/",
            headers=self.config.get_headers(**kwargs),
            params={"version": version},
        )
        handle_server_errors(result)

    # Keep the positional signature accepted by existing SDK callers.
    async def list_deployments(  # noqa: PLR0913, PLR0917
        self,
        cont: int = 0,
        limit: int = 50,
        dependencies: bool = False,  # noqa: FBT001, FBT002
        device_name: str | None = None,
        guids: list[str] | None = None,
        label_selector: list[str] | None = None,
        name: str | None = None,
        names: list[str] | None = None,
        package_name: str | None = None,
        package_version: str | None = None,
        phases: list[str] | None = None,
        regions: list[str] | None = None,
        **kwargs: object,
    ) -> DeploymentList:
        """List all deployments in a project.

        Args:
            cont (int, optional): Start index of deployments. Defaults to 0.
            limit (int, optional): Number of deployments to list. Defaults to 50.
            dependencies (bool, optional): Filter by dependencies. Defaults to
                False.
            device_name (str, optional): Filter deployments by device name. Defaults
                to None.
            guids (list[str], optional): Filter by GUIDs. Defaults to None.
            label_selector (list[str], optional): Define labelSelector to get
                deployments from. Defaults to None.
            name (str, optional): Define name to get deployments from. Defaults to
                None.
            names (list[str], optional): Define names to get deployments from.
                Defaults to None.
            package_name (str, optional): Filter by package name. Defaults to None.
            package_version (str, optional): Filter by package version. Defaults to
                None.
            phases (list[str], optional): Filter by phases. Available values :
                InProgress, Provisioning, Succeeded, FailedToUpdate,
                FailedToStart,
                Stopped. Defaults to None.
            regions (list[str], optional): Filter by regions. Defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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
        self, body: Deployment | dict[str, Any], **kwargs: object
    ) -> Deployment:
        """Create a new deployment.

        Args:
            body (dict): Deployment details

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            Deployment: Deployment details as a Deployment object.
        """
        if isinstance(body, dict):
            body = Deployment.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/deployments/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )

        handle_server_errors(result)
        return Deployment(**result.json())

    async def get_deployment(
        self, name: str, guid: str | None = None, **kwargs: object
    ) -> Deployment:
        """Get a deployment by its name.

        Args:
            name (str): Deployment name
            guid (str, optional): Deployment GUID. Defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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
        self, name: str, body: Deployment | dict[str, Any], **kwargs: object
    ) -> Deployment:
        """Update a deployment by its name.

        Args:
            name (str): Deployment name
            body (dict): Deployment details

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            Deployment: Deployment details as a Deployment object.
        """
        if isinstance(body, dict):
            body = Deployment.model_validate(body)

        result = await self.c.patch(
            url=f"{self.v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return Deployment(**result.json())

    async def delete_deployment(self, name: str, **kwargs: object) -> None:
        """Delete a deployment by its name.

        Args:
            name: Name identifying the resource.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            None if successful.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    async def get_deployment_graph(self, name: str, **kwargs: object) -> dict[str, Any]:
        """Get a deployment graph by its name. [Experimental].

        Args:
            name: Name identifying the resource.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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
        self, name: str, guid: str | None = None, **kwargs: object
    ) -> dict[str, Any]:
        """Get a deployment history by its name.

        Args:
            name: Name identifying the resource.
            guid: Guid.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    async def stream_deployment_logs(
        self, name: str, executable: str, replica: int = 0
    ) -> None:
        """Asynchronously stream logs for a deployment executable replica.

        Args:
            name: Name identifying the resource.
            executable: Executable.
            replica: Replica.
        """
        url = (
            f"{self.v2api_host}/v2/deployments/{name}/logs/"
            f"?replica={replica}&executable={executable}"
        )

        async with self.c.stream(
            "GET", url=url, headers=self.config.get_headers()
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line:
                    yield line

    # -------------------Disks-------------------

    # Keep the positional signature accepted by existing SDK callers.
    async def list_disks(  # noqa: PLR0913, PLR0917
        self,
        cont: int = 0,
        label_selector: list[str] | None = None,
        limit: int = 50,
        names: list[str] | None = None,
        regions: list[str] | None = None,
        status: list[str] | None = None,
        **kwargs: object,
    ) -> DiskList:
        """List all disks in a project.

        Args:
            cont (int, optional): Start index of disks. Defaults to 0.
            label_selector (list[str], optional): Define labelSelector to get disks
                from. Defaults to None.
            limit (int, optional): Number of disks to list. Defaults to 50.
            names (list[str], optional): Define names to get disks from. Defaults to
                None.
            regions (list[str], optional): Define regions to get disks from.
                Defaults to None.
            status (list[str], optional): Define status to get disks from. Available
                values : Available, Bound, Released, Failed, Pending.Defaults to
                None.


            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    async def get_disk(self, name: str, **kwargs: object) -> Disk:
        """Get a disk by its name.

        Args:
            name (str): Disk name

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            Disk: Disk details as a Disk object.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/disks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(response=result)

        return Disk(**result.json())

    async def create_disk(self, body: Disk | dict[str, Any], **kwargs: object) -> Disk:
        """Create a new disk.

        Args:
            body (dict): Disk details

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            Disk: Disk details as a Disk object.
        """
        if isinstance(body, dict):
            body = Disk.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/disks/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return Disk(**result.json())

    async def delete_disk(self, name: str, **kwargs: object) -> None:
        """Delete a disk by its name.

        Args:
            name (str): Disk name

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            None if successful.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/disks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    # -------------------Device--------------------------

    async def get_device_daemons(self, device_guid: str) -> Daemon:
        """Retrieve the list of daemons associated with a specific device.

        Args:
            device_guid (str): The unique identifier (GUID) of the device.

        Returns:
            dict: The JSON response containing information about the device's
                daemons.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/devices/daemons/{device_guid}/",
            headers=self.config.get_headers(),
        )

        handle_server_errors(response=result)
        return Daemon(**result.json())

    # -------------------Static Routes-------------------

    # Keep the positional signature accepted by existing SDK callers.
    async def list_staticroutes(  # noqa: PLR0913, PLR0917
        self,
        cont: int = 0,
        limit: int = 50,
        guids: list[str] | None = None,
        label_selector: list[str] | None = None,
        names: list[str] | None = None,
        regions: list[str] | None = None,
        **kwargs: object,
    ) -> StaticRouteList:
        """List all static routes in a project.

        Args:
            cont (int, optional): Start index of static routes. Defaults to 0.
            limit (int, optional): Number of static routes to list. Defaults to 50.
            guids (list[str], optional): Define guids to get static routes from.
                Defaults to None.
            label_selector (list[str], optional): Define labelSelector to get static
                routes from. Defaults to None.
            names (list[str], optional): Define names to get static routes from.
                Defaults to None.
            regions (list[str], optional): Define regions to get static routes from.
                Defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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
        self, body: StaticRoute | dict[str, Any], **kwargs: object
    ) -> StaticRoute:
        """Create a new static route.

        Args:
            body (dict): Static route details

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            StaticRoute: Static route details as a StaticRoute object.
        """
        if isinstance(body, dict):
            body = StaticRoute.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/staticroutes/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return StaticRoute(**result.json())

    async def get_staticroute(self, name: str, **kwargs: object) -> StaticRoute:
        """Get a static route by its name.

        Args:
            name (str): Static route name

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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
        self, name: str, body: StaticRoute | dict[str, Any], **kwargs: object
    ) -> StaticRoute:
        """Update a static route by its name.

        Args:
            name (str): Static route name
            body (dict): Update details

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            StaticRoute: Static route details as a StaticRoute object.
        """
        if isinstance(body, dict):
            body = StaticRoute.model_validate(body)

        result = await self.c.put(
            url=f"{self.v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return StaticRoute(**result.json())

    async def delete_staticroute(self, name: str, **kwargs: object) -> None:
        """Delete a static route by its name.

        Args:
            name (str): Static route name

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            None if successful.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    # -------------------Networks-------------------

    # Keep the positional signature accepted by existing SDK callers.
    async def list_networks(  # noqa: PLR0913, PLR0917
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
        **kwargs: object,
    ) -> NetworkList:
        """List all networks in a project.

        Args:
            cont (int, optional): Start index of networks. Defaults to 0.
            limit (int, optional): Number of networks to list. Defaults to 50.
            device_name (str, optional): Filter networks by device name. Defaults to
                None.
            label_selector (list[str], optional): Define labelSelector to get
                networks from. Defaults to None.
            names (list[str], optional): Define names to get networks from. Defaults
                to None.
            network_type (str, optional): Define network type to get networks from.
                Defaults to None.
            phases (list[str], optional): Define phases to get networks from.
                Available values : InProgress, Provisioning, Succeeded,
                FailedToUpdate, FailedToStart, Stopped. Defaults to None.
            regions (list[str], optional): Define regions to get networks from.
                Defaults to None.
            status (list[str], optional): Define status to get networks from.
                Available values : Running, Pending, Error, Unknown, Stopped.
                Defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    async def create_network(
        self, body: Network | dict[str, Any], **kwargs: object
    ) -> Network:
        """Create a new network.

        Args:
            body (dict): Network details

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            Network: Network details as a Network object.
        """
        if isinstance(body, dict):
            body = Network.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/networks/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return Network(**result.json())

    async def get_network(self, name: str, **kwargs: object) -> Network:
        """Get a network by its name.

        Args:
            name (str): Network name

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            Network: Network details as a Network object.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/networks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(response=result)

        return Network(**result.json())

    async def delete_network(self, name: str, **kwargs: object) -> None:
        """Delete a network by its name.

        Args:
            name (str): Network name

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            None if successful.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/networks/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    # -------------------Secrets-------------------

    # Keep the positional signature accepted by existing SDK callers.
    async def list_secrets(  # noqa: PLR0917
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        names: list[str] | None = None,
        regions: list[str] | None = None,
        **kwargs: object,
    ) -> SecretList:
        """List all secrets in a project.

        Args:
            cont (int, optional): Start index of secrets. Defaults to 0.
            limit (int, optional): Number of secrets to list. Defaults to 50.
            label_selector (list[str], optional): Define labelSelector to get
                secrets from. Defaults to None.
            names (list[str], optional): Define names to get secrets from. Defaults
                to None.
            regions (list[str], optional): Define regions to get secrets from.
                Defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    async def create_secret(
        self, body: SecretCreate | dict[str, Any], **kwargs: object
    ) -> Secret:
        """Create a new secret.

        Args:
            body (dict): Secret details

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            Secret: Secret details as a Secret object.
        """
        if isinstance(body, dict):
            body = SecretCreate.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/secrets/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )

        handle_server_errors(result)
        return Secret(**result.json())

    async def get_secret(self, name: str, **kwargs: object) -> Secret:
        """Get a secret by its name.

        Args:
            name (str): Secret name

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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
        self, name: str, body: Secret | dict[str, Any], **kwargs: object
    ) -> Secret:
        """Update a secret by its name.

        Args:
            name (str): Secret name
            body (dict): Update details

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            Secret: Secret details as a Secret object.
        """
        if isinstance(body, dict):
            body = Secret.model_validate(body)

        result = await self.c.put(
            url=f"{self.v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return Secret(**result.json())

    async def delete_secret(self, name: str, **kwargs: object) -> None:
        """Delete a secret by its name.

        Args:
            name (str): Secret name

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            None if successful.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    # -------------------OAuth2 Clients-------------------
    # Keep the positional signature accepted by existing SDK callers.
    async def list_oauth2_clients(  # noqa: PLR0917
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        names: list[str] | None = None,
        regions: list[str] | None = None,
        **kwargs: object,
    ) -> dict[str, Any]:
        """List all OAuth2 clients in a project.

        Args:
            cont (int, optional): Start index. Defaults to 0.
            limit (int, optional): Number to list. Defaults to 50.
            label_selector (list[str], optional): Label selector. Defaults to None.
            names (list[str], optional): Names filter. Defaults to None.
            regions (list[str], optional): Regions filter. Defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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
            url=f"{self.v2api_host}/v2/oauth2/clients/",
            headers=self.config.get_headers(**kwargs),
            params=params,
        )
        handle_server_errors(result)
        return result.json()

    async def get_oauth2_client(
        self, client_id: str, **kwargs: object
    ) -> dict[str, Any]:
        """Get an OAuth2 client by its client_id.

        Args:
            client_id (str): OAuth2 client ID

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            OAuth2 client details as a dictionary.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/oauth2/clients/{client_id}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return result.json()

    async def create_oauth2_client(
        self, body: dict, **kwargs: object
    ) -> dict[str, Any]:
        """Create a new OAuth2 client.

        Args:
            body (dict): OAuth2 client details

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            OAuth2 client details as a dictionary.
        """
        result = await self.c.post(
            url=f"{self.v2api_host}/v2/oauth2/clients/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )
        handle_server_errors(result)
        return result.json()

    async def update_oauth2_client(
        self, client_id: str, body: dict, **kwargs: object
    ) -> dict[str, Any]:
        """Update an OAuth2 client by its client_id.

        Args:
            client_id (str): OAuth2 client ID
            body (dict): Update details

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            OAuth2 client details as a dictionary.
        """
        result = await self.c.put(
            url=f"{self.v2api_host}/v2/oauth2/clients/{client_id}/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )
        handle_server_errors(result)
        return result.json()

    async def update_oauth2_client_uris(
        self, client_id: str, update: OAuth2UpdateURI, **kwargs: object
    ) -> dict[str, Any]:
        """Update OAuth2 client URIs.

        Args:
            client_id (str): OAuth2 client ID
            update (OAuth2UpdateURI): URIs update payload

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            OAuth2 client details as a dictionary.
        """
        result = await self.c.put(
            url=f"{self.v2api_host}/v2/oauth2/clients/{client_id}/uris/",
            headers=self.config.get_headers(**kwargs),
            json=update.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return result.json()

    async def delete_oauth2_client(self, client_id: str, **kwargs: object) -> None:
        """Delete an OAuth2 client by its client_id.

        Args:
            client_id (str): OAuth2 client ID

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            None if successful.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/oauth2/clients/{client_id}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    # -------------------Config Trees-------------------

    # Keep the positional signature accepted by existing SDK callers.
    async def list_configtrees(  # noqa: PLR0917
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        with_project: bool = True,  # noqa: FBT001, FBT002
        **kwargs: object,
    ) -> dict[str, Any]:
        """List all config trees in a project.

        Args:
            cont (int, optional): Start index of config trees. Defaults to 0.
            limit (int, optional): Number of config trees to list. Defaults to 50.
            label_selector (list[str], optional): Define labelSelector to get config
                trees from. Defaults to None.
            with_project (bool, optional): Include project details. Defaults to
                True.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    # Keep the positional signature accepted by existing SDK callers.
    async def create_configtree(
        self,
        body: dict,
        with_project: bool = True,  # noqa: FBT001, FBT002
        **kwargs: object,
    ) -> dict[str, Any]:
        """Create a new config tree.

        Args:
            body (object): Config tree details
            with_project (bool, optional): Work in the project scope. Defaults to
                True.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    # Keep the positional signature accepted by existing SDK callers.
    async def get_configtree(  # noqa: PLR0913, PLR0917
        self,
        name: str,
        content_types: list[str] | None = None,
        include_data: bool = False,  # noqa: FBT001, FBT002
        key_prefixes: list[str] | None = None,
        revision: str | None = None,
        with_project: bool = True,  # noqa: FBT001, FBT002
        **kwargs: object,
    ) -> dict[str, Any]:
        """Get a config tree by its name.

        Args:
            name (str): Config tree name
            content_types (list[str], optional): Define contentTypes to get config
                tree from. Defaults to None.
            include_data (bool, optional): Include data. Defaults to False.
            key_prefixes (list[str], optional): Define keyPrefixes to get config
                tree from. Defaults to None.
            revision (str, optional): Define revision to get config tree from.
                Defaults to None.
            with_project (bool, optional): Work in the project scope. Defaults to
                True.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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
        self,
        name: str,
        configtree: object,
        project_guid: str | None = None,
        **kwargs: object,
    ) -> dict[str, Any]:
        """Set a config tree revision.

        Args:
            name (str): Config tree name
            configtree (object): Config tree details
            project_guid (str, optional): Project GUID. async defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    # Keep the positional signature accepted by existing SDK callers.
    async def update_configtree(
        self,
        name: str,
        body: dict,
        with_project: bool = True,  # noqa: FBT001, FBT002
        **kwargs: object,
    ) -> dict[str, Any]:
        """Update a config tree by its name.

        Args:
            name (str): Config tree name
            body (dict): Update details
            with_project (bool, optional): Work in the project scope. Defaults to
                True.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    async def delete_configtree(self, name: str, **kwargs: object) -> None:
        """Delete a config tree by its name.

        Args:
            name (str): Config tree name

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            None if successful.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    # Keep the positional signature accepted by existing SDK callers.
    async def list_revisions(  # noqa: PLR0917
        self,
        tree_name: str,
        cont: int = 0,
        limit: int = 50,
        committed: bool = False,  # noqa: FBT001, FBT002
        label_selector: list[str] | None = None,
        **kwargs: object,
    ) -> dict[str, Any]:
        """List all revisions of a config tree.

        Args:
            tree_name (str): Config tree name
            cont (int, optional): Continue param . Defaults to 0.
            limit (int, optional): Limit param . Defaults to 50.
            committed (bool, optional): Committed. Defaults to False.
            label_selector (list[str], optional): Define labelSelector to get
                revisions from. Defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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
        self, name: str, body: dict, project_guid: str | None = None, **kwargs: object
    ) -> dict[str, Any]:
        """Create a new revision.

        Args:
            name (str): Config tree name
            body (object): Revision details
            project_guid (str): Project GUID (optional)

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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
        self, name: str, revision_id: str, config_values: dict, **kwargs: object
    ) -> dict[str, Any]:
        """Put keys in a revision.

        Args:
            name (str): Config tree name
            revision_id (str): Config tree revision ID
            config_values (dict): Config values

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    # Keep the positional signature accepted by existing SDK callers.
    async def commit_revision(  # noqa: PLR0913, PLR0917
        self,
        tree_name: str,
        revision_id: str,
        author: str | None = None,
        message: str | None = None,
        project_guid: str | None = None,
        labels: dict[str, str] | None = None,
        **kwargs: object,
    ) -> dict[str, Any]:
        """Commit a revision.

        Args:
            tree_name (str): Config tree name
            revision_id (str): Config tree revision ID
            author (str, optional): Revision Author. Defaults to None.
            message (str, optional): Revision Message. Defaults to None.
            project_guid (str, optional): Project GUID. Defaults to None.
            labels (dict, optional): Labels to set on the revision. Defaults to
                None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            Revision details as a dictionary.
        """
        config_tree_revision = {
            "author": author,
            "message": message,
        }

        if labels:
            config_tree_revision["metadata"] = {"labels": labels}

        result = await self.c.patch(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            json=config_tree_revision,
        )

        handle_server_errors(result)
        return result.json()

    # Keep the positional signature accepted by existing SDK callers.
    async def get_key_in_revision(  # noqa: PLR0917
        self,
        tree_name: str,
        revision_id: str,
        key: str,
        project_guid: str | None = None,
        **kwargs: object,
    ) -> object:
        """Get a key in a revision.

        Args:
            tree_name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            project_guid (str, optional): Project GUID. async defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    # Keep the positional signature accepted by existing SDK callers.
    async def put_key_in_revision(  # noqa: PLR0917
        self,
        tree_name: str,
        revision_id: str,
        key: str,
        body: object,
        project_guid: str | None = None,
        **kwargs: object,
    ) -> dict[str, Any]:
        """Put a key in a revision.

        Args:
            tree_name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            project_guid (str, optional): Project GUID. async defaults to None.

            body: Resource manifest or request payload.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            Key details as a dictionary.
        """
        result = await self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
            content=body,
        )
        handle_server_errors(result)
        return result.json()

    # Keep the positional signature accepted by existing SDK callers.
    async def delete_key_in_revision(  # noqa: PLR0917
        self,
        tree_name: str,
        revision_id: str,
        key: str,
        project_guid: str | None = None,
        **kwargs: object,
    ) -> None:
        """Delete a key in a revision.

        Args:
            tree_name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            project_guid (str, optional): Project GUID. async defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            None if successful.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/{key}/",
            headers=self.config.get_headers(project_guid=project_guid, **kwargs),
        )
        handle_server_errors(result)

    # Keep the positional signature accepted by existing SDK callers.
    async def rename_key_in_revision(  # noqa: PLR0917
        self,
        tree_name: str,
        revision_id: str,
        key: str,
        config_key_rename: dict,
        project_guid: str | None = None,
        **kwargs: object,
    ) -> dict[str, Any]:
        """Rename a key in a revision.

        Args:
            tree_name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            config_key_rename (dict): Key rename details
            project_guid (str, optional): Project GUID. async defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

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

    # Keep the positional signature accepted by existing SDK callers.
    async def list_instances(  # noqa: PLR0917
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        providers: list[str] | None = None,
    ) -> ManagedServiceInstanceList:
        """List all instances in a project.

        Args:
            cont (int, optional): Start index of instances. Defaults to 0.
            limit (int, optional): Number of instances to list. Defaults to 50.
            label_selector (list[str], optional): Define labelSelector to get
                instances from. Defaults to None.
            providers (list[str], optional): Define providers to get instances from.
                Defaults to None.

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

        Args:
            body: Resource manifest or request payload.

        Returns:
            Instance details as a ManagedServiceInstance object.
        """
        if isinstance(body, dict):
            body = ManagedServiceInstance.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/managedservices/",
            headers=self.config.get_headers(),
            json=body.model_dump(by_alias=True),
        )

        handle_server_errors(result)
        return ManagedServiceInstance(**result.json())

    async def delete_instance(self, name: str) -> None:
        """Delete an instance.

        Args:
            name: Name identifying the resource.

        Returns:
            None if successful.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/managedservices/{name}/",
            headers=self.config.get_headers(),
        )
        handle_server_errors(result)

    # Keep the positional signature accepted by existing SDK callers.
    async def list_instance_bindings(  # noqa: PLR0917
        self,
        instance_name: str,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
    ) -> ManagedServiceBindingList:
        """List all instance bindings in a project.

        Args:
            instance_name (str): Instance name.
            cont (int, optional): Start index of instance bindings. Defaults to 0.
            limit (int, optional): Number of instance bindings to list. Defaults to
                50.
            label_selector (list[str], optional): Define labelSelector to get
                instance bindings from. Defaults to None.

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
            json=body.model_dump(by_alias=True),
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

    # -------------------Usergroup-------------------
    # Keep the positional signature accepted by existing SDK callers.
    async def list_user_groups(  # noqa: PLR0917
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        name: str | None = None,
        guid: str | None = None,
        **kwargs: object,
    ) -> UserGroupList:
        """List user groups.

        Args:
            cont: Pagination continuation token.
            limit: Maximum number of resources per page.
            label_selector: Label expressions used to filter resources.
            name: Name identifying the resource.
            guid: Guid.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        parameters: dict[str, Any] = {
            "continue": cont,
            "limit": limit,
        }
        if label_selector:
            parameters["labelSelector"] = label_selector
        if name:
            parameters["name"] = name
        if guid:
            parameters["guid"] = guid

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/usergroups/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            params=parameters,
        )

        handle_server_errors(response=result)

        return UserGroupList(**result.json())

    async def get_user_group(
        self, group_name: str, group_guid: str, **kwargs: object
    ) -> UserGroup:
        """Get user group.

        Args:
            group_name: Name identifying the user group.
            group_guid: Group guid.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/usergroups/{group_name}/",
            headers=self.config.get_headers(
                with_project=False, with_group=True, group_guid=group_guid, **kwargs
            ),
        )
        handle_server_errors(result)

        return UserGroup(**result.json())

    async def create_user_group(
        self, user_group: UserGroup, **kwargs: object
    ) -> UserGroup:
        """Create user group.

        Args:
            user_group: User group.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        result = await self.c.post(
            url=f"{self.v2api_host}/v2/usergroups/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=user_group.model_dump(by_alias=True),
        )
        handle_server_errors(result)

        return UserGroup(**result.json())

    async def update_user_group(
        self, user_group: UserGroup, **kwargs: object
    ) -> UserGroup:
        """Update user group.

        Args:
            user_group: User group.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        result = await self.c.put(
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

    async def delete_user_group(
        self, group_name: str, group_guid: str, **kwargs: object
    ) -> None:
        """Delete user group.

        Args:
            group_name: Name identifying the user group.
            group_guid: Group guid.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/usergroups/{group_name}/",
            headers=self.config.get_headers(
                with_project=False, with_group=True, group_guid=group_guid, **kwargs
            ),
        )
        handle_server_errors(result)

    # -------------------Roles-------------------
    # Keep the positional signature accepted by existing SDK callers.
    async def list_roles(  # noqa: PLR0917
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        name: str | None = None,
        **kwargs: object,
    ) -> RoleList:
        """List roles.

        Args:
            cont: Pagination continuation token.
            limit: Maximum number of resources per page.
            label_selector: Label expressions used to filter resources.
            name: Name identifying the resource.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
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

    async def get_role(self, role_name: str, **kwargs: object) -> Role:
        """Get role.

        Args:
            role_name: Name identifying the role.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/roles/{role_name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)

        return Role(**result.json())

    async def create_role(self, role: Role | dict, **kwargs: object) -> Role:
        """Create role.

        Args:
            role: Role manifest to create or update.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        if isinstance(role, dict):
            role = Role.model_validate(role)
        result = await self.c.post(
            url=f"{self.v2api_host}/v2/roles/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=role.model_dump(by_alias=True),
        )
        handle_server_errors(result)

        return Role(**result.json())

    async def update_role(self, role: Role, **kwargs: object) -> Role:
        """Update role.

        Args:
            role: Role manifest to create or update.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        if isinstance(role, dict):
            role = Role.model_validate(role)
        result = await self.c.put(
            url=f"{self.v2api_host}/v2/roles/{role.metadata.name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=role.model_dump(by_alias=True),
        )
        handle_server_errors(result)

        return Role(**result.json())

    async def delete_role(self, role_name: str, **kwargs: object) -> None:
        """Delete role.

        Args:
            role_name: Name identifying the role.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/roles/{role_name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)

    # -------------------RoleBindings-------------------
    # Keep the positional signature accepted by existing SDK callers.
    async def list_role_bindings(  # noqa: PLR0913, PLR0917
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
        **kwargs: object,
    ) -> RoleBindingList:
        """List role bindings.

        Args:
            cont: Pagination continuation token.
            limit: Maximum number of resources per page.
            label_selector: Label expressions used to filter resources.
            role_names: Role names used to filter bindings.
            subject_guids: Subject guids.
            subject_names: Subject names.
            subject_kinds: Subject kinds.
            domain_guids: Domain guids.
            domain_names: Domain names.
            domain_kinds: Domain kinds.
            guids: Resource GUIDs used to filter results.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        parameters: dict[str, Any] = {
            "continue": cont,
            "limit": limit,
        }
        filters = {
            "labelSelector": label_selector,
            "roleNames": role_names,
            "subjectGUIDS": subject_guids,
            "subjectNames": subject_names,
            "subjectKinds": subject_kinds,
            "domainGUIDS": domain_guids,
            "domainNames": domain_names,
            "domainKinds": domain_kinds,
            "guids": guids,
        }
        parameters.update({key: value for key, value in filters.items() if value})

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/role-bindings/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            params=parameters,
        )

        handle_server_errors(result)

        return RoleBindingList(**result.json())

    async def get_role_binding(
        self, binding_guid: str, **kwargs: object
    ) -> RoleBinding:
        """Get role binding.

        Args:
            binding_guid: GUID identifying the role binding.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/role-bindings/{binding_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )
        handle_server_errors(result)

        return RoleBinding(**result.json())

    async def update_role_binding(
        self, binding: BulkRoleBindingUpdate | dict, **kwargs: object
    ) -> RoleBinding | dict[str, Any]:
        """Update role binding.

        Args:
            binding: Role bindings to add and remove.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        if isinstance(binding, dict):
            binding = BulkRoleBindingUpdate.model_validate(binding)
        result = await self.c.put(
            url=f"{self.v2api_host}/v2/role-bindings/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=binding.model_dump(by_alias=True),
        )
        handle_server_errors(result)

        try:
            return RoleBinding(**result.json())
        except (PydanticValidationError, TypeError):
            return result.json()

    # -------------------ServiceAccount-------------------

    # Keep the positional signature accepted by existing SDK callers.
    async def list_service_accounts(  # noqa: PLR0917
        self,
        cont: int = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        name: str | None = None,
        regions: list[str] | None = None,
        **kwargs: object,
    ) -> ServiceAccountList:
        """List service accounts.

        Args:
            cont: Pagination continuation token.
            limit: Maximum number of resources per page.
            label_selector: Label expressions used to filter resources.
            name: Name identifying the resource.
            regions: Regions used to filter resources.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
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

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/serviceaccounts/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            params=parameters,
        )

        handle_server_errors(result)

        return ServiceAccountList(**result.json())

    async def get_service_account(
        self,
        name: str,
        **kwargs: object,
    ) -> ServiceAccount:
        """Get service account.

        Args:
            name: Name identifying the resource.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )

        handle_server_errors(result)
        return ServiceAccount(**result.json())

    async def create_service_account(
        self,
        service_account: ServiceAccount | dict,
        **kwargs: object,
    ) -> ServiceAccount:
        """Create service account.

        Args:
            service_account: Service account manifest to create or update.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        if isinstance(service_account, dict):
            service_account = ServiceAccount.model_validate(service_account)
        result = await self.c.post(
            url=f"{self.v2api_host}/v2/serviceaccounts/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=service_account.model_dump(by_alias=True),
        )

        handle_server_errors(result)
        return ServiceAccount(**result.json())

    async def update_service_account(
        self,
        service_account: ServiceAccount | dict,
        name: str | None,
        **kwargs: object,
    ) -> ServiceAccount:
        """Update service account.

        Args:
            service_account: Service account manifest to create or update.
            name: Name identifying the resource.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        if isinstance(service_account, dict):
            service_account = ServiceAccount.model_validate(service_account)
        if not name:
            name = service_account.metadata.name
        result = await self.c.put(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=service_account.model_dump(by_alias=True),
        )

        handle_server_errors(result)
        return ServiceAccount(**result.json())

    async def delete_service_account(
        self,
        name: str,
        **kwargs: object,
    ) -> None:
        """Delete service account.

        Args:
            name: Name identifying the resource.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )

        handle_server_errors(result)

    # Keep legacy positional arguments on this unpaginated endpoint.
    async def list_service_account_tokens(
        self,
        name: str,
        cont: int = 0,  # noqa: ARG002
        limit: int = 50,  # noqa: ARG002
        **kwargs: object,
    ) -> ServiceAccountTokenList:
        """List service account tokens.

        Args:
            name: Name identifying the resource.
            cont: Retained for compatibility; currently ignored.
            limit: Retained for compatibility; currently ignored.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/tokens/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )

        handle_server_errors(result)

        return ServiceAccountTokenList(**result.json())

    async def create_service_account_token(
        self, name: str, expiry_at: ServiceAccountToken | dict, **kwargs: object
    ) -> ServiceAccountTokenInfo:
        """Create service account token.

        Args:
            name: Name identifying the resource.
            expiry_at: Token owner and expiration settings.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        if isinstance(expiry_at, dict):
            expiry_at = ServiceAccountToken.model_validate(expiry_at)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/tokens/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=expiry_at.model_dump(by_alias=True, mode="json"),
        )

        handle_server_errors(result)

        return ServiceAccountTokenInfo(**result.json())

    async def refresh_service_account_token(
        self,
        name: str,
        token_id: str,
        expiry_at: ServiceAccountToken | dict,
        **kwargs: object,
    ) -> ServiceAccountTokenInfo:
        """Refresh service account token.

        Args:
            name: Name identifying the resource.
            token_id: Identifier of the service account token.
            expiry_at: Token owner and expiration settings.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        if isinstance(expiry_at, dict):
            expiry_at = ServiceAccountToken.model_validate(expiry_at)

        result = await self.c.patch(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/tokens/{token_id}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=expiry_at.model_dump(by_alias=True, mode="json"),
        )

        handle_server_errors(result)

        return ServiceAccountTokenInfo(**result.json())

    async def delete_service_account_token(
        self, name: str, token_id: str, **kwargs: object
    ) -> None:
        """Delete service account token.

        Args:
            name: Name identifying the resource.
            token_id: Identifier of the service account token.
            **kwargs: Additional request header options passed to
                Configuration.get_headers.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/tokens/{token_id}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )

        handle_server_errors(result)

    # -------------------FileUpload-------------------
    # Keep the positional signature accepted by existing SDK callers.
    async def list_fileuploads(  # noqa: PLR0917
        self,
        device_guid: str,
        cont: int = 0,
        limit: int = 50,
        guids: list[str] | None = None,
        status: list[str] | None = None,
        **kwargs: object,
    ) -> FileUploadList:
        """List all file uploads for a device.

        Args:
            device_guid (str): Device GUID.
            cont (int, optional): Start index of file uploads. Defaults to 0.
            limit (int, optional): Number of file uploads to list. Defaults to 50.
            guids (list[str], optional): Filter by file upload GUIDs. Defaults to
                None.
            status (list[str], optional): Filter by upload status.
                Available values: PENDING, IN PROGRESS, FAILED, COMPLETED,
                    CANCELLED.
                Defaults to None.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            FileUploadList: List of file uploads.
        """
        params: dict[str, Any] = {
            "continue": cont,
            "limit": limit,
        }
        if guids:
            params["guids"] = guids
        if status:
            params["status"] = status

        result = await self.c.get(
            url=f"{self.v2api_host}/v2/devices/{device_guid}/fileuploads/",
            headers=self.config.get_headers(**kwargs),
            params=params,
        )
        handle_server_errors(result)
        return FileUploadList(**result.json())

    async def get_fileupload(
        self,
        device_guid: str,
        guid: str,
        **kwargs: object,
    ) -> FileUpload:
        """Get a file upload by its GUID.

        Args:
            device_guid (str): Device GUID.
            guid (str): File upload GUID.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            FileUpload: File upload details.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/devices/{device_guid}/fileuploads/{guid}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return FileUpload(**result.json())

    async def create_fileupload(
        self,
        device_guid: str,
        body: FileUpload | dict[str, Any],
        **kwargs: object,
    ) -> FileUpload:
        """Create a new file upload for a device.

        Args:
            device_guid (str): Device GUID.
            body (FileUpload | dict): File upload specification.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            FileUpload: Created file upload details.
        """
        if isinstance(body, dict):
            body = FileUpload.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/devices/{device_guid}/fileuploads/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True, exclude_none=True, mode="json"),
        )
        handle_server_errors(result)
        return FileUpload(**result.json())

    async def delete_fileupload(
        self,
        device_guid: str,
        guid: str,
        **kwargs: object,
    ) -> None:
        """Delete a file upload by its GUID.

        Args:
            device_guid (str): Device GUID.
            guid (str): File upload GUID.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Note:
            Cannot delete files with PENDING or IN PROGRESS status.
        """
        result = await self.c.delete(
            url=f"{self.v2api_host}/v2/devices/{device_guid}/fileuploads/{guid}/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    async def cancel_fileupload(
        self,
        device_guid: str,
        guid: str,
        **kwargs: object,
    ) -> None:
        """Cancel a file upload.

        Args:
            device_guid (str): Device GUID.
            guid (str): File upload GUID.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            None if successful.
        """
        result = await self.c.post(
            url=f"{self.v2api_host}/v2/devices/{device_guid}/fileuploads/{guid}/cancel/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)

    async def download_fileupload(
        self,
        device_guid: str,
        guid: str,
        **kwargs: object,
    ) -> dict[str, Any]:
        """Get the download URL for a file upload.

        Args:
            device_guid (str): Device GUID.
            guid (str): File upload GUID.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            dict[str, Any]: Dictionary containing the signed download URL.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/devices/{device_guid}/fileuploads/{guid}/download/",
            headers=self.config.get_headers(**kwargs),
        )
        handle_server_errors(result)
        return result.json()

    # -------------------SharedURL-------------------
    async def list_sharedurls(
        self,
        fileupload_guid: str,
        cont: int = 0,
        limit: int = 50,
        **kwargs: object,
    ) -> SharedURLList:
        """List all shared URLs for a file upload.

        Args:
            fileupload_guid (str): File upload GUID.
            cont (int, optional): Start index of shared URLs. Defaults to 0.
            limit (int, optional): Number of shared URLs to list. Defaults to 50.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            SharedURLList: List of shared URLs.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/devices/fileuploads/{fileupload_guid}/sharedurls/",
            headers=self.config.get_headers(**kwargs),
            params={
                "continue": cont,
                "limit": limit,
            },
        )
        handle_server_errors(result)
        return SharedURLList(**result.json())

    async def get_sharedurl(
        self,
        url_guid: str,
        **kwargs: object,
    ) -> httpx.Response:
        """Get a shared URL and redirect to the signed download URL.

        Args:
            url_guid (str): Shared URL GUID.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            httpx.Response: Response with redirect to signed download URL.
        """
        result = await self.c.get(
            url=f"{self.v2api_host}/v2/devices/fileuploads/sharedurls/{url_guid}/",
            headers=self.config.get_headers(**kwargs),
            follow_redirects=False,
        )
        handle_server_errors(result)
        return result

    async def create_sharedurl(
        self,
        fileupload_guid: str,
        body: SharedURL | dict[str, Any],
        **kwargs: object,
    ) -> SharedURL:
        """Create a shared URL for a file upload.

        Args:
            fileupload_guid (str): File upload GUID.
            body (SharedURL | dict): Shared URL specification with expiry time.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            SharedURL: Created shared URL details.

        Note:
            File upload must be in PENDING, IN PROGRESS, or COMPLETED status.
        """
        if isinstance(body, dict):
            body = SharedURL.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/devices/fileuploads/{fileupload_guid}/sharedurls/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True, exclude_none=True, mode="json"),
        )
        handle_server_errors(result)
        return SharedURL(**result.json())

    # -------------------SSH Certificates-------------------
    async def sign_ssh_public_key(
        self,
        body: SSHKeySignRequest | dict[str, Any],
        **kwargs: object,
    ) -> SSHKeySignResponse:
        """Sign an SSH public key.

        Sends the provided SSH public key to the server for signing
        and returns a signed SSH certificate.

        Args:
            body (SSHKeySignRequest | dict): The SSH public key to sign.

            **kwargs: Additional request header options passed to
                Configuration.get_headers.

        Returns:
            SSHKeySignResponse: The signed SSH certificate.
        """
        if isinstance(body, dict):
            body = SSHKeySignRequest.model_validate(body)

        result = await self.c.post(
            url=f"{self.v2api_host}/v2/certs/ssh/sign/",
            headers=self.config.get_headers(**kwargs),
            json=body.model_dump(by_alias=True),
        )
        handle_server_errors(result)
        return SSHKeySignResponse(**result.json())
