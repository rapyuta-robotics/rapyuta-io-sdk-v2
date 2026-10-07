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

from __future__ import annotations
from rapyuta_io_sdk_v2.context import RequestContext
from rapyuta_io_sdk_v2.transport import (
    serialize_model,
    require_model,
    authorization_header,
)
from rapyuta_io_sdk_v2.pagination import Paginator
import platform
from collections.abc import Callable
from typing import Any
import httpx
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
    UserPermissions,
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
    FileUpload,
    FileUploadList,
    SharedURL,
    SharedURLList,
    AuthSubject,
    BulkRoleBindingResponse,
    ConfigTree,
    ConfigTreeActionResponse,
    ConfigTreeKeyRename,
    ConfigTreeKeyUpdate,
    ConfigTreeList,
    ConfigTreeRevision,
    ConfigTreeRevisionCommit,
    ConfigTreeRevisionList,
    DeploymentGraph,
    DeploymentHistory,
    FileDownloadMetadata,
    OAuth2Client,
    OAuth2ClientCreate,
    OAuth2ClientList,
    ProjectOwnership,
)
from rapyuta_io_sdk_v2.models.serviceaccount import (
    ServiceAccountToken,
    ServiceAccountTokenInfo,
    ServiceAccountTokenList,
)
from rapyuta_io_sdk_v2.models.sshkey import SSHKeySignRequest, SSHKeySignResponse
from rapyuta_io_sdk_v2.utils import handle_server_errors

from rapyuta_io_sdk_v2.models.utils import BaseList


class Client:
    """Synchronous API client with typed request and response models.

    Args:
        config (Configuration): Configuration object.
    """

    def __init__(
        self,
        config: Configuration | None = None,
        *,
        transport: httpx.Client | None = None,
        timeout: float | httpx.Timeout = 60,
        limits: httpx.Limits | None = None,
    ) -> None:
        self.config = config or Configuration()
        self._owns_transport = transport is None
        self.c = (
            transport
            if transport is not None
            else httpx.Client(
                timeout=timeout,
                limits=limits
                or httpx.Limits(
                    max_keepalive_connections=5, max_connections=5, keepalive_expiry=30
                ),
                headers={
                    "User-Agent": f"rio-sdk-v2;N/A;{platform.processor() or platform.machine()};{platform.system()};{platform.release()};{platform.version()}"
                },
            )
        )

    @property
    def v2api_host(self) -> str:
        return self.config.resolved_v2_api_host

    @property
    def rip_host(self) -> str:
        return self.config.resolved_rip_host

    def close(self) -> None:
        if self._owns_transport:
            self.c.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def paginate[T](
        self,
        method: Callable[..., BaseList[T]],
        *args: Any,
        limit: int = 50,
        cont: int | str = 0,
        **kwargs: Any,
    ) -> Paginator[T]:
        return Paginator(method, *args, limit=limit, cont=cont, **kwargs)

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
            json={"email": email, "password": password},
        )
        handle_server_errors(result)
        return result.json()["data"].get("token")

    def get_subject(self, auth_token: str) -> AuthSubject:
        """Get subject(user or service account) from auth token.

        Args:
            auth_token (str): Authentication token
        """
        result = self.c.get(
            url=f"{self.rip_host}/user/info",
            headers={"Authorization": authorization_header(auth_token)},
        )
        handle_server_errors(result)
        return AuthSubject.model_validate(result.json())

    def login(self, email: str, password: str) -> None:
        """Get the authentication token for the user.

        Args:
            email (str)
            password (str)

        Updates the configured authentication token.
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
                "Authorization": authorization_header(token),
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
        self.config.organization_guid = organization_guid

    def set_project(self, project_guid: str) -> None:
        """Set the project GUID.

        Args:
            project_guid (str): Project GUID
        """
        self.config.project_guid = project_guid

    def get_organization(
        self, organization_guid: str, *, context: RequestContext | None = None
    ) -> Organization:
        """Get an organization by its GUID.

        The organization GUID identifies the resource path explicitly.

        Args:
            organization_guid (str): user provided organization GUID.

        Returns:
            Organization: Organization details as an Organization object.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/organizations/{organization_guid}/",
            headers=self.config.get_headers(
                with_project=False, organization_guid=organization_guid, context=context
            ),
        )
        handle_server_errors(result)
        return Organization(**result.json())

    def update_organization(
        self,
        body: Organization,
        organization_guid: str,
        *,
        context: RequestContext | None = None,
    ) -> Organization:
        """Update an organization by its GUID.

        Args:
            body (Organization): Organization details
            organization_guid (str): Organization GUID used in the request path.

        Returns:
            Organization: Organization details as an Organization object.
        """
        require_model(body, Organization)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/organizations/{organization_guid}/",
            headers=self.config.get_headers(
                with_project=False, organization_guid=organization_guid, context=context
            ),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return Organization(**result.json())

    def list_users(
        self,
        cont: int | str = 0,
        limit: int = 50,
        organization_guid: str | None = None,
        guid: str | None = None,
        *,
        context: RequestContext | None = None,
    ) -> UserList:
        parameters: dict[str, Any] = {"continue": cont, "limit": limit}
        if guid:
            parameters["guid"] = guid
        result = self.c.get(
            url=f"{self.v2api_host}/v2/users/",
            headers=self.config.get_headers(
                with_project=False, organization_guid=organization_guid, context=context
            ),
            params=parameters,
        )
        handle_server_errors(result)
        return UserList(**result.json())

    def add_user(self, user: User, *, context: RequestContext | None = None) -> User:
        """Add a User in Organization.

        Returns:
            User: User details as a user object.
        """
        require_model(user, User)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/users/",
            headers=self.config.get_headers(with_project=False, context=context),
            json=serialize_model(user),
        )
        handle_server_errors(result)
        return UserList(**result.json())

    def get_myself(self, *, context: RequestContext | None = None) -> User:
        """Get my User details.

        Returns:
            User: User details as a User object.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/users/me/",
            headers=self.config.get_headers(
                with_project=False, with_organization=False, context=context
            ),
        )
        handle_server_errors(result)
        return User(**result.json())

    def update_myself(self, body: User, *, context: RequestContext | None = None) -> User:
        """Update my user details.

        Args:
            body (User): User details

        Returns:
            User: User details as a User object.
        """
        require_model(body, User)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/users/me/",
            headers=self.config.get_headers(
                with_project=False, with_organization=False, context=context
            ),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return User(**result.json())

    def get_user(self, email_id: str, *, context: RequestContext | None = None) -> User:
        """Get User details.

        Returns:
            User: User details as a User object.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/users/{email_id}",
            headers=self.config.get_headers(with_project=False, context=context),
        )
        handle_server_errors(result)
        return User(**result.json())

    def update_user(
        self, email_id: str, body: User, *, context: RequestContext | None = None
    ) -> User:
        """Update the user details.

        Args:
            body (User): User details

        Returns:
            User: User details as a User object.
        """
        require_model(body, User)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/users/{email_id}/",
            headers=self.config.get_headers(with_project=False, context=context),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return User(**result.json())

    def delete_user(
        self, email_id: str, *, context: RequestContext | None = None
    ) -> None:
        """
        Delete the User
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/users/{email_id}/",
            headers=self.config.get_headers(with_project=False, context=context),
        )
        handle_server_errors(result)
        return None

    def get_user_permissions(
        self,
        user_guid: str,
        organization_guid: str | None = None,
        *,
        context: RequestContext | None = None,
    ) -> UserPermissions:
        """Get user permissions for an organization.

        Args:
            user_guid (str): User GUID
            organization_guid (str, optional): Organization GUID. Defaults to None.
            context (RequestContext, optional): Scope and header overrides for this request.

        Returns:
            UserPermissions: User permissions object containing organization, projects, and groups permissions
        """
        organization_guid = organization_guid or self.config.organization_guid
        headers = self.config.get_headers(
            with_project=False, organization_guid=organization_guid, context=context
        )
        headers["userguid"] = user_guid
        result = self.c.get(
            url=f"{self.v2api_host}/v2/users/permissions/", headers=headers
        )
        handle_server_errors(result)
        return UserPermissions(**result.json())

    def get_project(
        self, project_guid: str, *, context: RequestContext | None = None
    ) -> Project:
        """Get a project by its GUID.

        Args:
            project_guid (str): Project GUID used in the request path.

        Returns:
            Project: Project details as a Project object.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(
                with_project=True, project_guid=project_guid, context=context
            ),
        )
        handle_server_errors(result)
        return Project(**result.json())

    def list_projects(
        self,
        cont: int | str = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        status: list[str] | None = None,
        organizations: list[str] | None = None,
        name: str | None = None,
        *,
        context: RequestContext | None = None,
    ) -> ProjectList:
        """List all projects in an organization.

        Args:
            cont (int, optional): Start index of projects. Defaults to 0.
            limit (int, optional): Number of projects to list. Defaults to 50.
            label_selector (List[str], optional): Define labelSelector to get projects from. Defaults to None.
            status (List[str], optional): Define status to get projects from. Defaults to None.
            organizations (List[str], optional): Define organizations to get projects from. Defaults to None.

        Returns:
            ProjectList: List of projects.
        """
        parameters: dict[str, Any] = {"continue": cont, "limit": limit}
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
            headers=self.config.get_headers(with_project=False, context=context),
            params=parameters,
        )
        handle_server_errors(response=result)
        return ProjectList(**result.json())

    def create_project(
        self, body: Project, *, context: RequestContext | None = None
    ) -> Project:
        """Create a new project.

        Args:
            body (Project): Project details

        Returns:
            Project: Project creation result.
        """
        require_model(body, Project)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/projects/",
            headers=self.config.get_headers(with_project=False, context=context),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return Project(**result.json())

    def update_project(
        self, body: Project, project_guid: str, *, context: RequestContext | None = None
    ) -> Project:
        """Update a project by its GUID.

        Args:
            body (Project): Project details
            project_guid (str): Project GUID used in the request path.

        Returns:
            Project: Project update result.
        """
        require_model(body, Project)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(project_guid=project_guid, context=context),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return Project(**result.json())

    def delete_project(
        self, project_guid: str, *, context: RequestContext | None = None
    ) -> None:
        """Delete a project by its GUID.

        Args:
            project_guid (str): Project GUID

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(
                with_project=True, project_guid=project_guid, context=context
            ),
        )
        handle_server_errors(result)
        return None

    def update_project_owner(
        self,
        body: ProjectOwnership,
        project_guid: str,
        *,
        context: RequestContext | None = None,
    ) -> ProjectOwnership:
        """Update the owner of a project by its GUID.

        Returns:
            ProjectOwnership: Root model preserving the project owner response.
        """
        require_model(body, ProjectOwnership)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/projects/{project_guid}/owner/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body, exclude_unset=True),
        )
        handle_server_errors(result)
        return ProjectOwnership.model_validate(result.json())

    def list_packages(
        self,
        cont: int | str = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        name: str | None = None,
        *,
        context: RequestContext | None = None,
    ) -> PackageList:
        """List all packages in a project.

        Args:
            cont (int, optional): Start index of packages. Defaults to 0.
            limit (int, optional): Number of packages to list. Defaults to 50.
            label_selector (List[str], optional): Define labelSelector to get packages from. Defaults to None.
            name (str, optional): Define name to get packages from. Defaults to None.

        Returns:
            PackageList: List of packages.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/packages/",
            headers=self.config.get_headers(context=context),
            params={
                "continue": cont,
                "limit": limit,
                "labelSelector": label_selector,
                "name": name,
            },
        )
        handle_server_errors(response=result)
        return PackageList(**result.json())

    def create_package(
        self, body: Package, *, context: RequestContext | None = None
    ) -> Package:
        """Create a new package.

        The Payload is the JSON format of the Package Manifest.
        For a documented example, run the rio explain package command.

        Returns:
            Package: Package details.
        """
        require_model(body, Package)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/packages/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return Package(**result.json())

    def get_package(
        self,
        name: str,
        version: str | None = None,
        *,
        context: RequestContext | None = None,
    ) -> Package:
        """Get a package by its name.

        Args:
            name (str): Package name
            version (str, optional): Package version. Defaults to None.

        Returns:
            Package: Package details as a Package object.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/packages/{name}/",
            headers=self.config.get_headers(context=context),
            params={"version": version},
        )
        handle_server_errors(response=result)
        return Package(**result.json())

    def delete_package(
        self, name: str, version: str, *, context: RequestContext | None = None
    ) -> None:
        """Delete a package by its name.

        Args:
            name (str): Package name

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/packages/{name}/",
            headers=self.config.get_headers(context=context),
            params={"version": version},
        )
        handle_server_errors(result)

    def list_deployments(
        self,
        cont: int | str = 0,
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
        *,
        context: RequestContext | None = None,
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
            DeploymentList: List of deployments.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/deployments/",
            headers=self.config.get_headers(context=context),
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
        self, body: Deployment, *, context: RequestContext | None = None
    ) -> Deployment:
        """Create a new deployment.

        Args:
            body (Deployment): Deployment details

        Returns:
            Deployment: Deployment details.
        """
        require_model(body, Deployment)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/deployments/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return Deployment(**result.json())

    def get_deployment(
        self, name: str, guid: str | None = None, *, context: RequestContext | None = None
    ) -> Deployment:
        """Get a deployment by its name.

        Returns:
            Deployment: Deployment details.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(context=context),
            params={"guid": guid},
        )
        handle_server_errors(result)
        return Deployment(**result.json())

    def update_deployment(
        self, name: str, body: Deployment, *, context: RequestContext | None = None
    ) -> Deployment:
        """Update a deployment by its name.

        Returns:
            Deployment: Deployment details.
        """
        require_model(body, Deployment)
        result = self.c.patch(
            url=f"{self.v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return Deployment(**result.json())

    def delete_deployment(
        self, name: str, *, context: RequestContext | None = None
    ) -> None:
        """Delete a deployment by its name.

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/deployments/{name}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)

    def get_deployment_graph(
        self, name: str, *, context: RequestContext | None = None
    ) -> DeploymentGraph:
        """Get a deployment graph by its name. [Experimental]

        Returns:
            DeploymentGraph: Root model preserving the deployment graph response.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/deployments/{name}/graph/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)
        return DeploymentGraph.model_validate(result.json())

    def get_deployment_history(
        self, name: str, guid: str | None = None, *, context: RequestContext | None = None
    ) -> DeploymentHistory:
        """Get a deployment history by its name.

        Returns:
            DeploymentHistory: Root model preserving the deployment history response.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/deployments/{name}/history/",
            headers=self.config.get_headers(context=context),
            params={"guid": guid},
        )
        handle_server_errors(result)
        return DeploymentHistory.model_validate(result.json())

    def stream_deployment_logs(
        self,
        name: str,
        executable: str,
        replica: int = 0,
        *,
        context: RequestContext | None = None,
    ):
        url = f"{self.v2api_host}/v2/deployments/{name}/logs/?replica={replica}&executable={executable}"
        with self.c.stream(
            "GET", url=url, headers=self.config.get_headers(context=context)
        ) as response:
            if response.status_code >= 400:
                response.read()
                handle_server_errors(response)
            for line in response.iter_lines():
                if line:
                    yield line

    def list_disks(
        self,
        cont: int | str = 0,
        label_selector: list[str] | None = None,
        limit: int = 50,
        names: list[str] | None = None,
        regions: list[str] | None = None,
        status: list[str] | None = None,
        *,
        context: RequestContext | None = None,
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
            DiskList: List of disks.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/disks/",
            headers=self.config.get_headers(context=context),
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

    def get_disk(self, name: str, *, context: RequestContext | None = None) -> Disk:
        """Get a disk by its name.

        Args:
            name (str): Disk name

        Returns:
            Disk: Disk details.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/disks/{name}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)
        return Disk(**result.json())

    def create_disk(self, body: Disk, *, context: RequestContext | None = None) -> Disk:
        """Create a new disk.

        Returns:
            Disk: Disk details.
        """
        require_model(body, Disk)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/disks/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return Disk(**result.json())

    def delete_disk(self, name: str, *, context: RequestContext | None = None) -> None:
        """Delete a disk by its name.

        Args:
            name (str): Disk name

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/disks/{name}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)

    def get_device_daemons(
        self, device_guid: str, *, context: RequestContext | None = None
    ) -> Daemon:
        """
        Retrieve the list of daemons associated with a specific device.

        Args:
            device_guid (str): The unique identifier (GUID) of the device.

        Returns:
            Daemon: Daemon information for the requested device.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/devices/daemons/{device_guid}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(response=result)
        return Daemon(**result.json())

    def list_staticroutes(
        self,
        cont: int | str = 0,
        limit: int = 50,
        guids: list[str] | None = None,
        label_selector: list[str] | None = None,
        names: list[str] | None = None,
        regions: list[str] | None = None,
        *,
        context: RequestContext | None = None,
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
            StaticRouteList: List of static routes.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/staticroutes/",
            headers=self.config.get_headers(context=context),
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
        self, body: StaticRoute, *, context: RequestContext | None = None
    ) -> StaticRoute:
        """Create a new static route.

        Returns:
            StaticRoute: Static route details.
        """
        require_model(body, StaticRoute)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/staticroutes/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return StaticRoute(**result.json())

    def get_staticroute(
        self, name: str, *, context: RequestContext | None = None
    ) -> StaticRoute:
        """Get a static route by its name.

        Args:
            name (str): Static route name

        Returns:
            StaticRoute: Static route details.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)
        return StaticRoute(**result.json())

    def update_staticroute(
        self, name: str, body: StaticRoute, *, context: RequestContext | None = None
    ) -> StaticRoute:
        """Update a static route by its name.

        Args:
            name (str): Static route name
            body (StaticRoute): Update details

        Returns:
            StaticRoute: Static route details.
        """
        require_model(body, StaticRoute)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return StaticRoute(**result.json())

    def delete_staticroute(
        self, name: str, *, context: RequestContext | None = None
    ) -> None:
        """Delete a static route by its name.

        Args:
            name (str): Static route name

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/staticroutes/{name}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)

    def list_networks(
        self,
        cont: int | str = 0,
        limit: int = 50,
        device_name: str | None = None,
        label_selector: list[str] | None = None,
        names: list[str] | None = None,
        network_type: str | None = None,
        phases: list[str] | None = None,
        regions: list[str] | None = None,
        status: list[str] | None = None,
        *,
        context: RequestContext | None = None,
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
            NetworkList: List of networks.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/networks/",
            headers=self.config.get_headers(context=context),
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

    def create_network(
        self, body: Network, *, context: RequestContext | None = None
    ) -> Network:
        """Create a new network.

        Returns:
            Network: Network details.
        """
        require_model(body, Network)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/networks/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return Network(**result.json())

    def get_network(self, name: str, *, context: RequestContext | None = None) -> Network:
        """Get a network by its name.

        Args:
            name (str): Network name

        Returns:
            Network details as a Network class object.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/networks/{name}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)
        return Network(**result.json())

    def delete_network(self, name: str, *, context: RequestContext | None = None) -> None:
        """Delete a network by its name.

        Args:
            name (str): Network name

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/networks/{name}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)

    def list_secrets(
        self,
        cont: int | str = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        names: list[str] | None = None,
        regions: list[str] | None = None,
        *,
        context: RequestContext | None = None,
    ) -> SecretList:
        """List all secrets in a project.

        Args:
            cont (int, optional): Start index of secrets. Defaults to 0.
            limit (int, optional): Number of secrets to list. Defaults to 50.
            label_selector (List[str], optional): Define labelSelector to get secrets from. Defaults to None.
            names (List[str], optional): Define names to get secrets from. Defaults to None.
            regions (List[str], optional): Define regions to get secrets from. Defaults to None.

        Returns:
            SecretList: List of secrets.
        """
        parameters: dict[str, Any] = {"continue": cont, "limit": limit}
        if label_selector is not None:
            parameters["labelSelector"] = label_selector
        if names is not None:
            parameters["names"] = names
        if regions is not None:
            parameters["regions"] = regions
        result = self.c.get(
            url=f"{self.v2api_host}/v2/secrets/",
            headers=self.config.get_headers(context=context),
            params=parameters,
        )
        handle_server_errors(result)
        return SecretList(**result.json())

    def create_secret(
        self, body: SecretCreate, *, context: RequestContext | None = None
    ) -> Secret:
        """Create a new secret.

        Returns:
            Secret: Secret details.
        """
        require_model(body, SecretCreate)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/secrets/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return Secret(**result.json())

    def get_secret(self, name: str, *, context: RequestContext | None = None) -> Secret:
        """Get a secret by its name.

        Args:
            name (str): Secret name

        Returns:
            Secret: Secret details.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(response=result)
        return Secret(**result.json())

    def update_secret(
        self, name: str, body: SecretCreate, *, context: RequestContext | None = None
    ) -> Secret:
        """Update a secret by its name.

        Args:
            name (str): Secret name
            body (SecretCreate): Update details

        Returns:
            Secret: Secret details.
        """
        require_model(body, SecretCreate)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body),
        )
        handle_server_errors(response=result)
        return Secret(**result.json())

    def delete_secret(self, name: str, *, context: RequestContext | None = None) -> None:
        """Delete a secret by its name.

        Args:
            name (str): Secret name

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/secrets/{name}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)

    def list_oauth2_clients(
        self,
        cont: int | str = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        names: list[str] | None = None,
        regions: list[str] | None = None,
        *,
        context: RequestContext | None = None,
    ) -> OAuth2ClientList:
        """List all OAuth2 clients in a project.

        Args:
            cont (int, optional): Start index. Defaults to 0.
            limit (int, optional): Number to list. Defaults to 50.
            label_selector (List[str], optional): Label selector. Defaults to None.
            names (List[str], optional): Names filter. Defaults to None.
            regions (List[str], optional): Regions filter. Defaults to None.

        Returns:
            OAuth2ClientList: List of OAuth2 clients.
        """
        params: dict[str, Any] = {"continue": cont, "limit": limit}
        if label_selector is not None:
            params["labelSelector"] = label_selector
        if names is not None:
            params["names"] = names
        if regions is not None:
            params["regions"] = regions
        result = self.c.get(
            url=f"{self.v2api_host}/v2/oauth2/clients/",
            headers=self.config.get_headers(context=context),
            params=params,
        )
        handle_server_errors(result)
        return OAuth2ClientList.model_validate(result.json())

    def get_oauth2_client(
        self, client_id: str, *, context: RequestContext | None = None
    ) -> OAuth2Client:
        """Get an OAuth2 client by its client_id.

        Args:
            client_id (str): OAuth2 client ID

        Returns:
            Typed OAuth2 client details.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/oauth2/clients/{client_id}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)
        return OAuth2Client.model_validate(result.json())

    def create_oauth2_client(
        self, body: OAuth2ClientCreate, *, context: RequestContext | None = None
    ) -> OAuth2Client:
        """Create a new OAuth2 client.

        Args:
            body (OAuth2ClientCreate): OAuth2 client details

        Returns:
            Typed OAuth2 client details.
        """
        require_model(body, OAuth2ClientCreate)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/oauth2/clients/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body, exclude_unset=True),
        )
        handle_server_errors(result)
        return OAuth2Client.model_validate(result.json())

    def update_oauth2_client(
        self,
        client_id: str,
        body: OAuth2ClientCreate,
        *,
        context: RequestContext | None = None,
    ) -> OAuth2Client:
        """Update an OAuth2 client by its client_id.

        Args:
            client_id (str): OAuth2 client ID
            body (OAuth2ClientCreate): Update details

        Returns:
            Typed OAuth2 client details.
        """
        require_model(body, OAuth2ClientCreate)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/oauth2/clients/{client_id}/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body, exclude_unset=True),
        )
        handle_server_errors(result)
        return OAuth2Client.model_validate(result.json())

    def update_oauth2_client_uris(
        self,
        client_id: str,
        update: OAuth2UpdateURI,
        *,
        context: RequestContext | None = None,
    ) -> OAuth2Client:
        """Update OAuth2 client URIs.

        Args:
            client_id (str): OAuth2 client ID
            update (OAuth2UpdateURI): URIs update payload.

        Returns:
            Typed OAuth2 client details.
        """
        require_model(update, OAuth2UpdateURI)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/oauth2/clients/{client_id}/uris/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(update),
        )
        handle_server_errors(result)
        return OAuth2Client.model_validate(result.json())

    def delete_oauth2_client(
        self, client_id: str, *, context: RequestContext | None = None
    ) -> None:
        """Delete an OAuth2 client by its client_id.

        Args:
            client_id (str): OAuth2 client ID

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/oauth2/clients/{client_id}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)

    def list_configtrees(
        self,
        cont: int | str = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        with_project: bool = True,
        *,
        context: RequestContext | None = None,
    ) -> ConfigTreeList:
        """List all config trees in a project.

        Args:
            cont (int, optional): Start index of config trees. Defaults to 0.
            limit (int, optional): Number of config trees to list. Defaults to 50.
            label_selector (List[str], optional): Define labelSelector to get config trees from. Defaults to None.
            with_project (bool, optional): Include project. Defaults to True.

        Returns:
            Typed list of config trees.
        """
        parameters: dict[str, Any] = {"continue": cont, "limit": limit}
        if label_selector:
            parameters["labelSelector"] = label_selector
        result = self.c.get(
            url=f"{self.v2api_host}/v2/configtrees/",
            headers=self.config.get_headers(with_project=with_project, context=context),
            params=parameters,
        )
        handle_server_errors(result)
        return ConfigTreeList.model_validate(result.json())

    def create_configtree(
        self,
        body: ConfigTree,
        with_project: bool = True,
        *,
        context: RequestContext | None = None,
    ) -> ConfigTree:
        """Create a new config tree.

        Args:
            body (ConfigTree): Config tree details
            with_project (bool, optional): Work in the project scope. Defaults to True.

        Returns:
            ConfigTree: Config tree details.
        """
        require_model(body, ConfigTree)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/configtrees/",
            headers=self.config.get_headers(with_project=with_project, context=context),
            json=serialize_model(body, exclude_unset=True),
        )
        handle_server_errors(result)
        return ConfigTree.model_validate(result.json())

    def get_configtree(
        self,
        name: str,
        content_types: list[str] | None = None,
        include_data: bool = False,
        key_prefixes: list[str] | None = None,
        revision: str | None = None,
        with_project: bool = True,
        *,
        context: RequestContext | None = None,
    ) -> ConfigTree:
        """Get a config tree by its name.

        Args:
            name (str): Config tree name
            content_types (List[str], optional): Define contentTypes to get config tree from. Defaults to None.
            include_data (bool, optional): Include data. Defaults to False.
            key_prefixes (List[str], optional): Define keyPrefixes to get config tree from. Defaults to None.
            revision (str, optional): Define revision to get config tree from. Defaults to None.
            with_project (bool, optional): Work in the project scope. Defaults to True.

        Returns:
            ConfigTree: Config tree details.
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
            headers=self.config.get_headers(with_project=with_project, context=context),
            params=parameters,
        )
        handle_server_errors(result)
        return ConfigTree.model_validate(result.json())

    def set_configtree_revision(
        self,
        name: str,
        configtree: ConfigTree,
        project_guid: str | None = None,
        *,
        context: RequestContext | None = None,
    ) -> ConfigTree:
        """Set a config tree revision.

        Args:
            name (str): Config tree name
            configtree (ConfigTree): Config tree details
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            ConfigTree: Config tree details.
        """
        require_model(configtree, ConfigTree)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(project_guid=project_guid, context=context),
            json=serialize_model(configtree, exclude_unset=True),
        )
        handle_server_errors(result)
        return ConfigTree.model_validate(result.json())

    def update_configtree(
        self,
        name: str,
        body: ConfigTree,
        with_project: bool = True,
        *,
        context: RequestContext | None = None,
    ) -> ConfigTree:
        """Update a config tree by its name.

        Args:
            name (str): Config tree name
            body (ConfigTree): Update details
            with_project (bool, optional): Work in the project scope. Defaults to True.

        Returns:
            ConfigTree: Config tree details.
        """
        require_model(body, ConfigTree)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(with_project=with_project, context=context),
            json=serialize_model(body, exclude_unset=True),
        )
        handle_server_errors(result)
        return ConfigTree.model_validate(result.json())

    def delete_configtree(
        self, name: str, *, context: RequestContext | None = None
    ) -> None:
        """Delete a config tree by its name.

        Args:
            name (str): Config tree name

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/configtrees/{name}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)

    def list_revisions(
        self,
        tree_name: str,
        cont: int | str = 0,
        limit: int = 50,
        committed: bool = False,
        label_selector: list[str] | None = None,
        *,
        context: RequestContext | None = None,
    ) -> ConfigTreeRevisionList:
        """List all revisions of a config tree.

        Args:
            tree_name (str): Config tree name
            cont (int, optional): Continue param . Defaults to 0.
            limit (int, optional): Limit param . Defaults to 50.
            committed (bool, optional): Committed. Defaults to False.
            label_selector (List[str], optional): Define labelSelector to get revisions from. Defaults to None.

        Returns:
            Typed list of revisions.
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
            headers=self.config.get_headers(context=context),
            params=parameters,
        )
        handle_server_errors(result)
        return ConfigTreeRevisionList.model_validate(result.json())

    def create_revision(
        self,
        name: str,
        body: ConfigTreeRevision | None = None,
        project_guid: str | None = None,
        *,
        context: RequestContext | None = None,
    ) -> ConfigTreeRevision:
        """Create a new revision.

        Args:
            name (str): Config tree name
            body (ConfigTreeRevision | None): Revision details
            project_guid (str): Project GUID (optional)

        Returns:
            ConfigTreeRevision: Revision details.
        """
        if body is not None:
            require_model(body, ConfigTreeRevision)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/configtrees/{name}/revisions/",
            headers=self.config.get_headers(project_guid=project_guid, context=context),
            json=serialize_model(body, exclude_unset=True),
        )
        handle_server_errors(result)
        return ConfigTreeRevision.model_validate(result.json())

    def put_keys_in_revision(
        self,
        name: str,
        revision_id: str,
        config_values: ConfigTreeKeyUpdate,
        *,
        context: RequestContext | None = None,
    ) -> ConfigTreeRevision:
        """Put keys in a revision.

        Args:
            name (str): Config tree name
            revision_id (str): Config tree revision ID
            config_values (ConfigTreeKeyUpdate): Config values

        Returns:
            ConfigTreeRevision: Revision details.
        """
        require_model(config_values, ConfigTreeKeyUpdate)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(config_values, exclude_unset=True),
        )
        handle_server_errors(result)
        return ConfigTreeRevision.model_validate(result.json())

    def commit_revision(
        self,
        tree_name: str,
        revision_id: str,
        body: ConfigTreeRevisionCommit,
        *,
        context: RequestContext | None = None,
    ) -> ConfigTreeRevision:
        """Commit a revision.

        Args:
            tree_name (str): Config tree name.
            revision_id (str): Config tree revision ID.
            body (ConfigTreeRevisionCommit): Author, message, and optional revision metadata.
            context (RequestContext, optional): Scope and header overrides for this request.

        Returns:
            ConfigTreeRevision: Committed revision details.
        """
        require_model(body, ConfigTreeRevisionCommit)
        result = self.c.patch(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body, exclude_unset=True),
        )
        handle_server_errors(result)
        return ConfigTreeRevision.model_validate(result.json())

    def get_key_in_revision(
        self,
        tree_name: str,
        revision_id: str,
        key: str,
        project_guid: str | None = None,
        *,
        context: RequestContext | None = None,
    ) -> str:
        """Get a key in a revision.

        Args:
            tree_name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            str: Stored key content as raw text, without parsing or conversion.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/{key}",
            headers=self.config.get_headers(project_guid=project_guid, context=context),
        )
        handle_server_errors(result)
        return result.text

    def put_key_in_revision(
        self,
        tree_name: str,
        revision_id: str,
        key: str,
        body: str | bytes,
        project_guid: str | None = None,
        *,
        context: RequestContext | None = None,
    ) -> ConfigTreeActionResponse:
        """Put a key in a revision.

        Args:
            tree_name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            body (str | bytes): Raw key content.
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            ConfigTreeActionResponse: Root model preserving the key action response.
        """
        result = self.c.put(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/{key}",
            headers=self.config.get_headers(project_guid=project_guid, context=context),
            content=body,
        )
        handle_server_errors(result)
        return ConfigTreeActionResponse.model_validate(result.json())

    def delete_key_in_revision(
        self,
        tree_name: str,
        revision_id: str,
        key: str,
        project_guid: str | None = None,
        *,
        context: RequestContext | None = None,
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
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/{key}",
            headers=self.config.get_headers(project_guid=project_guid, context=context),
        )
        handle_server_errors(result)

    def rename_key_in_revision(
        self,
        tree_name: str,
        revision_id: str,
        key: str,
        config_key_rename: ConfigTreeKeyRename,
        project_guid: str | None = None,
        *,
        context: RequestContext | None = None,
    ) -> ConfigTreeActionResponse:
        """Rename a key in a revision.

        Args:
            tree_name (str): Config tree name
            revision_id (str): Config tree revision ID
            key (str): Key
            config_key_rename (ConfigTreeKeyRename): Key rename details
            project_guid (str, optional): Project GUID. Defaults to None.

        Returns:
            ConfigTreeActionResponse: Root model preserving the key action response.
        """
        require_model(config_key_rename, ConfigTreeKeyRename)
        result = self.c.patch(
            url=f"{self.v2api_host}/v2/configtrees/{tree_name}/revisions/{revision_id}/{key}",
            headers=self.config.get_headers(project_guid=project_guid, context=context),
            json=serialize_model(config_key_rename, exclude_unset=True),
        )
        handle_server_errors(result)
        return ConfigTreeActionResponse.model_validate(result.json())

    def list_providers(
        self, *, context: RequestContext | None = None
    ) -> ManagedServiceProviderList:
        """List all providers.

        Returns:
            ManagedServiceProviderList: List of providers.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/managedservices/providers/",
            headers=self.config.get_headers(with_project=False, context=context),
        )
        handle_server_errors(result)
        return ManagedServiceProviderList(**result.json())

    def list_instances(
        self,
        cont: int | str = 0,
        limit: int = 50,
        label_selector: list[str] = None,
        providers: list[str] = None,
        *,
        context: RequestContext | None = None,
    ) -> ManagedServiceInstanceList:
        """List all instances in a project.

        Args:
            cont (int, optional): Start index of instances. Defaults to 0.
            limit (int, optional): Number of instances to list. Defaults to 50.
            label_selector (List[str], optional): Define labelSelector to get instances from. Defaults to None.
            providers (List[str], optional): Define providers to get instances from. Defaults to None.

        Returns:
            ManagedServiceInstanceList: List of instances.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/managedservices/",
            headers=self.config.get_headers(context=context),
            params={
                "continue": cont,
                "limit": limit,
                "labelSelector": label_selector,
                "providers": providers,
            },
        )
        handle_server_errors(result)
        return ManagedServiceInstanceList(**result.json())

    def get_instance(
        self, name: str, *, context: RequestContext | None = None
    ) -> ManagedServiceInstance:
        """Get an instance by its name.

        Args:
            name (str): Instance name

        Returns:
            ManagedServiceInstance: Instance details.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/managedservices/{name}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)
        return ManagedServiceInstance(**result.json())

    def create_instance(
        self, body: ManagedServiceInstance, *, context: RequestContext | None = None
    ) -> ManagedServiceInstance:
        """Create a new instance.

        Returns:
            Instance details as a ManagedServiceInstance object.
        """
        require_model(body, ManagedServiceInstance)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/managedservices/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return ManagedServiceInstance(**result.json())

    def delete_instance(
        self, name: str, *, context: RequestContext | None = None
    ) -> None:
        """Delete an instance.

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/managedservices/{name}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)

    def list_instance_bindings(
        self,
        instance_name: str,
        cont: int | str = 0,
        limit: int = 50,
        label_selector: list[str] = None,
        *,
        context: RequestContext | None = None,
    ) -> ManagedServiceBindingList:
        """List all instance bindings in a project.

        Args:
            instance_name (str): Instance name.
            cont (int, optional): Start index of instance bindings. Defaults to 0.
            limit (int, optional): Number of instance bindings to list. Defaults to 50.
            label_selector (List[str], optional): Define labelSelector to get instance bindings from. Defaults to None.

        Returns:
            ManagedServiceBindingList: List of instance bindings.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/managedservices/{instance_name}/bindings/",
            headers=self.config.get_headers(context=context),
            params={"continue": cont, "limit": limit, "labelSelector": label_selector},
        )
        handle_server_errors(result)
        return ManagedServiceBindingList(**result.json())

    def create_instance_binding(
        self,
        instance_name: str,
        body: ManagedServiceBinding,
        *,
        context: RequestContext | None = None,
    ) -> ManagedServiceBinding:
        """Create a new instance binding.

        Args:
            instance_name (str): Instance name.
            body (ManagedServiceBinding): Instance binding details.

        Returns:
            ManagedServiceBinding: Instance binding details.
        """
        require_model(body, ManagedServiceBinding)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/managedservices/{instance_name}/bindings/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return ManagedServiceBinding(**result.json())

    def get_instance_binding(
        self, instance_name: str, name: str, *, context: RequestContext | None = None
    ) -> ManagedServiceBinding:
        """Get an instance binding by its name.

        Args:
            instance_name (str): Instance name.
            name (str): Instance binding name.

        Returns:
            ManagedServiceBinding: Instance binding details.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/managedservices/{instance_name}/bindings/{name}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)
        return ManagedServiceBinding(**result.json())

    def delete_instance_binding(
        self, instance_name: str, name: str, *, context: RequestContext | None = None
    ) -> None:
        """Delete an instance binding.

        Args:
            instance_name (str): Instance name.
            name (str): Instance binding name.

        Returns:
            None if successful.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/managedservices/{instance_name}/bindings/{name}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)

    def list_user_groups(
        self,
        cont: int | str = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        name: str | None = None,
        guid: str | None = None,
        *,
        context: RequestContext | None = None,
    ) -> UserGroupList:
        parameters: dict[str, Any] = {"continue": cont, "limit": limit}
        if label_selector:
            parameters["labelSelector"] = label_selector
        if name:
            parameters["name"] = name
        if guid:
            parameters["guid"] = guid
        result = self.c.get(
            url=f"{self.v2api_host}/v2/usergroups/",
            headers=self.config.get_headers(with_project=False, context=context),
            params=parameters,
        )
        handle_server_errors(response=result)
        return UserGroupList(**result.json())

    def get_user_group(
        self, group_name: str, group_guid: str, *, context: RequestContext | None = None
    ) -> UserGroup:
        result = self.c.get(
            url=f"{self.v2api_host}/v2/usergroups/{group_name}/",
            headers=self.config.get_headers(
                with_project=False,
                with_group=True,
                group_guid=group_guid,
                context=context,
            ),
        )
        handle_server_errors(result)
        return UserGroup(**result.json())

    def create_user_group(
        self, user_group: UserGroup, *, context: RequestContext | None = None
    ) -> UserGroup:
        require_model(user_group, UserGroup)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/usergroups/",
            headers=self.config.get_headers(with_project=False, context=context),
            json=serialize_model(user_group),
        )
        handle_server_errors(result)
        return UserGroup(**result.json())

    def update_user_group(
        self,
        group_name: str,
        group_guid: str,
        user_group: UserGroup,
        *,
        context: RequestContext | None = None,
    ) -> UserGroup:
        require_model(user_group, UserGroup)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/usergroups/{group_name}/",
            headers=self.config.get_headers(
                with_project=False,
                with_group=True,
                group_guid=group_guid,
                context=context,
            ),
            json=serialize_model(user_group),
        )
        handle_server_errors(result)
        return UserGroup(**result.json())

    def delete_user_group(
        self, group_name: str, group_guid: str, *, context: RequestContext | None = None
    ) -> None:
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/usergroups/{group_name}/",
            headers=self.config.get_headers(
                with_project=False,
                with_group=True,
                group_guid=group_guid,
                context=context,
            ),
        )
        handle_server_errors(result)

    def list_roles(
        self,
        cont: int | str = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        name: str | None = None,
        *,
        context: RequestContext | None = None,
    ) -> RoleList:
        parameters: dict[str, Any] = {"continue": cont, "limit": limit}
        if label_selector:
            parameters["labelSelector"] = label_selector
        if name:
            parameters["name"] = name
        result = self.c.get(
            url=f"{self.v2api_host}/v2/roles/",
            headers=self.config.get_headers(with_project=False, context=context),
            params=parameters,
        )
        handle_server_errors(result)
        return RoleList(**result.json())

    def get_role(self, role_name: str, *, context: RequestContext | None = None) -> Role:
        result = self.c.get(
            url=f"{self.v2api_host}/v2/roles/{role_name}/",
            headers=self.config.get_headers(with_project=False, context=context),
        )
        handle_server_errors(result)
        return Role(**result.json())

    def create_role(self, role: Role, *, context: RequestContext | None = None) -> Role:
        require_model(role, Role)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/roles/",
            headers=self.config.get_headers(with_project=False, context=context),
            json=serialize_model(role),
        )
        handle_server_errors(result)
        return Role(**result.json())

    def update_role(
        self, role_name: str, role: Role, *, context: RequestContext | None = None
    ) -> Role:
        require_model(role, Role)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/roles/{role_name}/",
            headers=self.config.get_headers(with_project=False, context=context),
            json=serialize_model(role),
        )
        handle_server_errors(result)
        return Role(**result.json())

    def delete_role(
        self, role_name: str, *, context: RequestContext | None = None
    ) -> None:
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/roles/{role_name}/",
            headers=self.config.get_headers(with_project=False, context=context),
        )
        handle_server_errors(result)

    def list_role_bindings(
        self,
        cont: int | str = 0,
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
        *,
        context: RequestContext | None = None,
    ) -> RoleBindingList:
        parameters: dict[str, Any] = {"continue": cont, "limit": limit}
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
            headers=self.config.get_headers(with_project=False, context=context),
            params=parameters,
        )
        handle_server_errors(result)
        return RoleBindingList(**result.json())

    def get_role_binding(
        self, binding_guid: str, *, context: RequestContext | None = None
    ) -> RoleBinding:
        result = self.c.get(
            url=f"{self.v2api_host}/v2/role-bindings/{binding_guid}/",
            headers=self.config.get_headers(with_project=False, context=context),
        )
        handle_server_errors(result)
        return RoleBinding(**result.json())

    def update_role_binding(
        self, binding: BulkRoleBindingUpdate, *, context: RequestContext | None = None
    ) -> BulkRoleBindingResponse:
        require_model(binding, BulkRoleBindingUpdate)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/role-bindings/",
            headers=self.config.get_headers(with_project=False, context=context),
            json=serialize_model(binding),
        )
        handle_server_errors(result)
        return BulkRoleBindingResponse.model_validate(result.json())

    def list_service_accounts(
        self,
        cont: int | str = 0,
        limit: int = 50,
        label_selector: list[str] | None = None,
        name: str | None = None,
        regions: list[str] | None = None,
        *,
        context: RequestContext | None = None,
    ) -> ServiceAccountList:
        parameters: dict[str, Any] = {"continue": cont, "limit": limit}
        if label_selector:
            parameters["labelSelector"] = label_selector
        if name:
            parameters["name"] = name
        if regions:
            parameters["regions"] = regions
        result = self.c.get(
            url=f"{self.v2api_host}/v2/serviceaccounts/",
            headers=self.config.get_headers(with_project=False, context=context),
            params=parameters,
        )
        handle_server_errors(result)
        return ServiceAccountList(**result.json())

    def get_service_account(
        self, name: str, *, context: RequestContext | None = None
    ) -> ServiceAccount:
        result = self.c.get(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/",
            headers=self.config.get_headers(with_project=False, context=context),
        )
        handle_server_errors(result)
        return ServiceAccount(**result.json())

    def create_service_account(
        self, service_account: ServiceAccount, *, context: RequestContext | None = None
    ) -> ServiceAccount:
        require_model(service_account, ServiceAccount)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/serviceaccounts/",
            headers=self.config.get_headers(with_project=False, context=context),
            json=serialize_model(service_account),
        )
        handle_server_errors(result)
        return ServiceAccount(**result.json())

    def update_service_account(
        self,
        service_account: ServiceAccount,
        name: str,
        *,
        context: RequestContext | None = None,
    ) -> ServiceAccount:
        require_model(service_account, ServiceAccount)
        result = self.c.put(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/",
            headers=self.config.get_headers(with_project=False, context=context),
            json=serialize_model(service_account),
        )
        handle_server_errors(result)
        return ServiceAccount(**result.json())

    def delete_service_account(
        self, name: str, *, context: RequestContext | None = None
    ) -> None:
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/",
            headers=self.config.get_headers(with_project=False, context=context),
        )
        handle_server_errors(result)
        return None

    def list_service_account_tokens(
        self,
        name: str,
        cont: int | str = 0,
        limit: int = 50,
        *,
        context: RequestContext | None = None,
    ) -> ServiceAccountTokenList:
        result = self.c.get(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/tokens/",
            headers=self.config.get_headers(with_project=False, context=context),
            params={"continue": cont, "limit": limit},
        )
        handle_server_errors(result)
        return ServiceAccountTokenList(**result.json())

    def create_service_account_token(
        self,
        name: str,
        expiry_at: ServiceAccountToken,
        *,
        context: RequestContext | None = None,
    ) -> ServiceAccountTokenInfo:
        require_model(expiry_at, ServiceAccountToken)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/tokens/",
            headers=self.config.get_headers(with_project=False, context=context),
            json=serialize_model(expiry_at),
        )
        handle_server_errors(result)
        return ServiceAccountTokenInfo(**result.json())

    def refresh_service_account_token(
        self,
        name: str,
        token_id: str,
        expiry_at: ServiceAccountToken,
        *,
        context: RequestContext | None = None,
    ) -> ServiceAccountTokenInfo:
        require_model(expiry_at, ServiceAccountToken)
        result = self.c.patch(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/tokens/{token_id}/",
            headers=self.config.get_headers(with_project=False, context=context),
            json=serialize_model(expiry_at),
        )
        handle_server_errors(result)
        return ServiceAccountTokenInfo(**result.json())

    def delete_service_account_token(
        self, name: str, token_id: str, *, context: RequestContext | None = None
    ) -> None:
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/serviceaccounts/{name}/tokens/{token_id}/",
            headers=self.config.get_headers(with_project=False, context=context),
        )
        handle_server_errors(result)
        return None

    def list_fileuploads(
        self,
        device_guid: str,
        cont: int | str = 0,
        limit: int = 50,
        guids: list[str] | None = None,
        status: list[str] | None = None,
        *,
        context: RequestContext | None = None,
    ) -> FileUploadList:
        """List all file uploads for a device.

        Args:
            device_guid (str): Device GUID.
            cont (int, optional): Start index of file uploads. Defaults to 0.
            limit (int, optional): Number of file uploads to list. Defaults to 50.
            guids (List[str], optional): Filter by file upload GUIDs. Defaults to None.
            status (List[str], optional): Filter by upload status.
                Available values: PENDING, IN PROGRESS, FAILED, COMPLETED, CANCELLED.
                Defaults to None.

        Returns:
            FileUploadList: List of file uploads.
        """
        params: dict[str, Any] = {"continue": cont, "limit": limit}
        if guids:
            params["guids"] = guids
        if status:
            params["status"] = status
        result = self.c.get(
            url=f"{self.v2api_host}/v2/devices/{device_guid}/fileuploads/",
            headers=self.config.get_headers(context=context),
            params=params,
        )
        handle_server_errors(result)
        return FileUploadList(**result.json())

    def get_fileupload(
        self, device_guid: str, guid: str, *, context: RequestContext | None = None
    ) -> FileUpload:
        """Get a file upload by its GUID.

        Args:
            device_guid (str): Device GUID.
            guid (str): File upload GUID.

        Returns:
            FileUpload: File upload details.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/devices/{device_guid}/fileuploads/{guid}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)
        return FileUpload(**result.json())

    def create_fileupload(
        self, device_guid: str, body: FileUpload, *, context: RequestContext | None = None
    ) -> FileUpload:
        """Create a new file upload for a device.

        Args:
            device_guid (str): Device GUID.
            body (FileUpload): File upload specification.

        Returns:
            FileUpload: Created file upload details.
        """
        require_model(body, FileUpload)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/devices/{device_guid}/fileuploads/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body, exclude_none=True),
        )
        handle_server_errors(result)
        return FileUpload(**result.json())

    def delete_fileupload(
        self, device_guid: str, guid: str, *, context: RequestContext | None = None
    ) -> None:
        """Delete a file upload by its GUID.

        Args:
            device_guid (str): Device GUID.
            guid (str): File upload GUID.

        Note:
            Cannot delete files with PENDING or IN PROGRESS status.
        """
        result = self.c.delete(
            url=f"{self.v2api_host}/v2/devices/{device_guid}/fileuploads/{guid}/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)

    def cancel_fileupload(
        self, device_guid: str, guid: str, *, context: RequestContext | None = None
    ) -> None:
        """Cancel a file upload.

        Args:
            device_guid (str): Device GUID.
            guid (str): File upload GUID.

        Returns:
            None if successful.
        """
        result = self.c.post(
            url=f"{self.v2api_host}/v2/devices/{device_guid}/fileuploads/{guid}/cancel/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)

    def download_fileupload(
        self, device_guid: str, guid: str, *, context: RequestContext | None = None
    ) -> FileDownloadMetadata:
        """Get the download URL for a file upload.

        Args:
            device_guid (str): Device GUID.
            guid (str): File upload GUID.

        Returns:
            FileDownloadMetadata: Signed download URL and response metadata.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/devices/{device_guid}/fileuploads/{guid}/download/",
            headers=self.config.get_headers(context=context),
        )
        handle_server_errors(result)
        return FileDownloadMetadata.model_validate(result.json())

    def list_sharedurls(
        self,
        fileupload_guid: str,
        cont: int | str = 0,
        limit: int = 50,
        *,
        context: RequestContext | None = None,
    ) -> SharedURLList:
        """List all shared URLs for a file upload.

        Args:
            fileupload_guid (str): File upload GUID.
            cont (int, optional): Start index of shared URLs. Defaults to 0.
            limit (int, optional): Number of shared URLs to list. Defaults to 50.

        Returns:
            SharedURLList: List of shared URLs.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/devices/fileuploads/{fileupload_guid}/sharedurls/",
            headers=self.config.get_headers(context=context),
            params={"continue": cont, "limit": limit},
        )
        handle_server_errors(result)
        return SharedURLList(**result.json())

    def get_sharedurl(
        self, url_guid: str, *, context: RequestContext | None = None
    ) -> httpx.Response:
        """Get a shared URL and redirect to the signed download URL.

        Args:
            url_guid (str): Shared URL GUID.

        Returns:
            httpx.Response: Response with redirect to signed download URL.
        """
        result = self.c.get(
            url=f"{self.v2api_host}/v2/devices/fileuploads/sharedurls/{url_guid}/",
            headers=self.config.get_headers(context=context),
            follow_redirects=False,
        )
        handle_server_errors(result)
        return result

    def create_sharedurl(
        self,
        fileupload_guid: str,
        body: SharedURL,
        *,
        context: RequestContext | None = None,
    ) -> SharedURL:
        """Create a shared URL for a file upload.

        Args:
            fileupload_guid (str): File upload GUID.
            body (SharedURL): Shared URL specification with expiry time.

        Returns:
            SharedURL: Created shared URL details.

        Note:
            File upload must be in PENDING, IN PROGRESS, or COMPLETED status.
        """
        require_model(body, SharedURL)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/devices/fileuploads/{fileupload_guid}/sharedurls/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body, exclude_none=True),
        )
        handle_server_errors(result)
        return SharedURL(**result.json())

    def sign_ssh_public_key(
        self, body: SSHKeySignRequest, *, context: RequestContext | None = None
    ) -> SSHKeySignResponse:
        """Sign an SSH public key.

        Sends the provided SSH public key to the server for signing
        and returns a signed SSH certificate.

        Args:
            body (SSHKeySignRequest): The SSH public key to sign.

        Returns:
            SSHKeySignResponse: The signed SSH certificate.
        """
        require_model(body, SSHKeySignRequest)
        result = self.c.post(
            url=f"{self.v2api_host}/v2/certs/ssh/sign/",
            headers=self.config.get_headers(context=context),
            json=serialize_model(body),
        )
        handle_server_errors(result)
        return SSHKeySignResponse(**result.json())
