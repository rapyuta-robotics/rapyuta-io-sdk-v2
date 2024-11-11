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
from munch import Munch, munchify
import platform
from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.utils import handle_server_errors


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

        payload = {
            "email": email or self.config.email,
            "password": password or self.config.password,
        }

        rip_host = self.config.hosts.get("rip_host")
        url = f"{rip_host}/user/login"
        headers = {"Content-Type": "application/json"}

        response = self.c.post(url=url, headers=headers, json=payload)

        handle_server_errors(response)

        self.config.auth_token = response.json()["data"].get("token")

        return self.config.auth_token

    def logout(self, token: str = None) -> None:
        """Expire the authentication token.

        Args:
            token (str): The token to expire.
        """
        rip_host = self.config.hosts.get("rip_host")
        url = f"{rip_host}/user/logout"
        headers = {"Content-Type": "application/json"}

        if token is None:
            token = self.config.auth_token

        response = self.c.post(url=url, headers=headers, json={"token": token})

        handle_server_errors(response)

        return

    def refresh_token(self, token: str = None) -> str:
        """Refresh the authentication token.

        Args:
            token (str): The token to refresh.

        Returns:
            str: The refreshed token.
        """
        rip_host = self.config.hosts.get("rip_host")
        url = f"{rip_host}/refreshtoken"
        headers = {"Content-Type": "application/json"}

        if token is None:
            token = self.config.auth_token

        response = self.c.post(url=url, headers=headers, json={"token": token})

        handle_server_errors(response)

        data = response.json()["data"]
        self.config.auth_token = data["Token"]

        return self.config.auth_token

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

    def get_project(self, project_guid: str = None) -> Munch:
        """Get a project by its GUID.

        If no project or organization GUID is provided,
        the default project and organization GUIDs will
        be picked from the current configuration.

        Args:
            project_guid (str): Project GUID

        Raises:
            ValueError: If organization_guid or project_guid is None

        Returns:
            Munch: Project details as a Munch object.
        """
        headers = self.config.get_headers(with_project=False)

        if project_guid is None:
            project_guid = self.config.project_guid

        if not project_guid:
            raise ValueError("project_guid is required")

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/projects/{project_guid}/",
            headers=headers,
        )

        handle_server_errors(response)

        print(response.headers)

        return munchify(response.json())

    def list_projects(self) -> Munch:
        """List all projects.

        Returns:
            Munch: List of projects as a Munch object.
        """
        headers = self.config.get_headers(with_project=False)

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/projects/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def create_project(self, body: dict) -> Munch:
        """Create a new project.

        Returns:
            Munch: Project details as a Munch object.
        """
        headers = self.config.get_headers(with_project=False)

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.post(
            url=f"{v2api_host}/v2/projects/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def update_project(self, project_guid: str, body: dict) -> Munch:
        """Update a project by its GUID.

        Args:
            project_guid (str): Project GUID
            body (dict): Project details

        Returns:
            Munch: Project details as a Munch object.
        """
        headers = self.config.get_headers(with_project=False)

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.put(
            url=f"{v2api_host}/v2/projects/{project_guid}/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def delete_project(self, project_guid: str) -> Munch:
        """Delete a project by its GUID.

        Args:
            project_guid (str): Project GUID

        Returns:
            Munch: Project details as a Munch object.
        """
        headers = self.config.get_headers(with_project=False)

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.delete(
            url=f"{v2api_host}/v2/projects/{project_guid}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def update_project_owner(self, project_guid: str, body: dict) -> Munch:
        """Update the owner of a project by its GUID.

        Args:
            project_guid (str): Project GUID
            body (dict): Owner details

        Returns:
            Munch: Project details as a Munch object.
        """
        headers = self.config.get_headers(with_project=False)

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.put(
            url=f"{v2api_host}/v2/projects/{project_guid}/owner/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def list_packages(self, project_guid: str = None) -> Munch:
        """List all packages in a project.

        Returns:
            Munch: List of packages as a Munch object.
        """
        headers = self.config.get_headers(with_project=True)
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/packages/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def create_package(self, body: dict) -> Munch:
        """Create a new package.

        The Payload is the JSON Format of the Package Manifest.
        For a documented example, run the rio explain package command.

        Returns:
            Munch: Package details as a Munch object.
        """
        headers = self.config.get_headers()

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.post(
            url=f"{v2api_host}/v2/packages/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def get_package(self, name: str) -> Munch:
        """Get a package by its name.

        Args:
            name (str): Package name

        Returns:
            Munch: Package details as a Munch object.
        """
        headers = self.config.get_headers()

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/packages/{name}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def delete_package(self, name: str) -> Munch:
        """Delete a package by its name.

        Args:
            name (str): Package name

        Returns:
            Munch: Package details as a Munch object.
        """
        headers = self.config.get_headers()

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.delete(
            url=f"{v2api_host}/v2/packages/{name}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def list_deployments(self, project_guid: str = None) -> Munch:
        """List all deployments in a project.

        Returns:
            Munch: List of deployments as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/deployments/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def create_deployment(self, project_guid: str, body: dict) -> Munch:
        """Create a new deployment.

        Returns:
            Munch: Deployment details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.post(
            url=f"{v2api_host}/v2/deployments/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def get_deployment(self, project_guid: str, name: str) -> Munch:
        """Get a deployment by its name.

        Args:
            name (str): Deployment name

        Returns:
            Munch: Deployment details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/deployments/{name}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def update_deployment(self, project_guid: str, name: str, body: dict) -> Munch:
        """Update a deployment by its name.

        Args:
            name (str): Deployment name
            body (dict): Update details

        Returns:
            Munch: Deployment details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.put(
            url=f"{v2api_host}/v2/deployments/{name}/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def delete_deployment(self, project_guid: str, name: str) -> Munch:
        """Delete a deployment by its name.

        Args:
            name (str): Deployment name

        Returns:
            Munch: Deployment details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.delete(
            url=f"{v2api_host}/v2/deployments/{name}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def poll_deployment(
        self,
        project_guid: str,
        name: str,
        retry_count: int = 50,
        sleep_interval: int = 6,
        ready_phases: list[str] = None,
    ) -> Munch:
        """Poll a deployment by its name.

        Args:
            name (str): Deployment name
            retry_count (int): Number of retries
            sleep_interval (int): Sleep interval in seconds
            ready_phases (list[str]): List of ready phases

        Returns:
            Munch: Deployment details as a Munch object.
        """
        pass

    def stream_depolyment_logs(
        self, project_guid: str, name: str, executable: str, replica: int = 0
    ):
        """Stream deployment logs.

        Args:
            name (str): Deployment name
            executable (str): Executable name
            replica (int): Replica number
        """
        pass

    def list_disks(self, project_guid: str = None) -> Munch:
        """List all disks in a project.

        Returns:
            Munch: List of disks as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/disks/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def get_disk(self, project_guid: str, name: str) -> Munch:
        """Get a disk by its name.

        Args:
            name (str): Disk name

        Returns:
            Munch: Disk details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/disks/{name}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def create_disk(self, project_guid: str, body: dict) -> Munch:
        """Create a new disk.

        Returns:
            Munch: Disk details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.post(
            url=f"{v2api_host}/v2/disks/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def delete_disk(self, project_guid: str, name: str) -> Munch:
        """Delete a disk by its name.

        Args:
            name (str): Disk name

        Returns:
            Munch: Disk details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.delete(
            url=f"{v2api_host}/v2/disks/{name}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def list_staticroutes(self, project_guid: str = None) -> Munch:
        """List all static routes in a project.

        Returns:
            Munch: List of static routes as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/staticroutes/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def create_staticroute(self, project_guid: str, body: dict) -> Munch:
        """Create a new static route.

        Returns:
            Munch: Static route details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.post(
            url=f"{v2api_host}/v2/staticroutes/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def get_staticroute(self, project_guid: str, name: str) -> Munch:
        """Get a static route by its name.

        Args:
            name (str): Static route name

        Returns:
            Munch: Static route details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/staticroutes/{name}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def update_staticroute(self, project_guid: str, name: str, body: dict) -> Munch:
        """Update a static route by its name.

        Args:
            name (str): Static route name
            body (dict): Update details

        Returns:
            Munch: Static route details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.put(
            url=f"{v2api_host}/v2/staticroutes/{name}/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def delete_staticroute(self, project_guid: str, name: str) -> Munch:
        """Delete a static route by its name.

        Args:
            name (str): Static route name

        Returns:
            Munch: Static route details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.delete(
            url=f"{v2api_host}/v2/staticroutes/{name}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def list_secrets(self, project_guid: str = None) -> Munch:
        """List all secrets in a project.

        Returns:
            Munch: List of secrets as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/secrets/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def create_secret(self, project_guid: str, body: dict) -> Munch:
        """Create a new secret.

        Returns:
            Munch: Secret details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.post(
            url=f"{v2api_host}/v2/secrets/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def get_secret(self, project_guid: str, name: str) -> Munch:
        """Get a secret by its name.

        Args:
            name (str): Secret name

        Returns:
            Munch: Secret details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/secrets/{name}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def update_secret(self, project_guid: str, name: str, body: dict) -> Munch:
        """Update a secret by its name.

        Args:
            name (str): Secret name
            body (dict): Update details

        Returns:
            Munch: Secret details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.put(
            url=f"{v2api_host}/v2/secrets/{name}/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def delete_secret(self, project_guid: str, name: str) -> Munch:
        """Delete a secret by its name.

        Args:
            name (str): Secret name

        Returns:
            Munch: Secret details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.delete(
            url=f"{v2api_host}/v2/secrets/{name}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def list_configtrees(
        self, organization_guid: str = None, project_guid: str = None
    ) -> Munch:
        """List all config trees in a project.

        Returns:
            Munch: List of config trees as a Munch object.
        """
        headers = self.config.get_headers()
        if organization_guid:
            headers["organizationguid"] = organization_guid
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/configtrees/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def create_configtree(
        self, organization_guid: str, project_guid: str, body: dict
    ) -> Munch:
        """Create a new config tree.

        Returns:
            Munch: Config tree details as a Munch object.
        """
        headers = self.config.get_headers()
        if organization_guid:
            headers["organizationguid"] = organization_guid
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.post(
            url=f"{v2api_host}/v2/configtrees/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def get_configtree(
        self, organization_guid: str, project_guid: str, name: str
    ) -> Munch:
        """Get a config tree by its name.

        Args:
            name (str): Config tree name

        Returns:
            Munch: Config tree details as a Munch object.
        """
        headers = self.config.get_headers()
        if organization_guid:
            headers["organizationguid"] = organization_guid
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/configtrees/{name}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def update_configtree(
        self, organization_guid: str, project_guid: str, name: str, body: dict
    ) -> Munch:
        """Update a config tree by its name.

        Args:
            name (str): Config tree name
            body (dict): Update details

        Returns:
            Munch: Config tree details as a Munch object.
        """
        headers = self.config.get_headers()
        if organization_guid:
            headers["organizationguid"] = organization_guid
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.put(
            url=f"{v2api_host}/v2/configtrees/{name}/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def delete_configtree(
        self, organization_guid: str, project_guid: str, name: str
    ) -> Munch:
        """Delete a config tree by its name.

        Args:
            name (str): Config tree name

        Returns:
            Munch: Config tree details as a Munch object.
        """
        headers = self.config.get_headers()
        if organization_guid:
            headers["organizationguid"] = organization_guid
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.delete(
            url=f"{v2api_host}/v2/configtrees/{name}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def list_revisions(
        self, organization_guid: str = None, project_guid: str = None, name: str = None
    ) -> Munch:
        """List all revisions in a project.

        Returns:
            Munch: List of revisions as a Munch object.
        """
        headers = self.config.get_headers()
        if organization_guid:
            headers["organizationguid"] = organization_guid
        if project_guid:
            headers["project"] = project_guid
        if name:
            headers["name"] = name

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/configtrees/{name}/revisions/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def create_revision(
        self, organization_guid: str, project_guid: str, name: str, body: dict
    ) -> Munch:
        """Create a new revision.

        Returns:
            Munch: Revision details as a Munch object.
        """
        headers = self.config.get_headers()
        if organization_guid:
            headers["organizationguid"] = organization_guid
        if project_guid:
            headers["project"] = project_guid
        if name:
            headers["name"] = name

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.post(
            url=f"{v2api_host}/v2/configtrees/{name}/revisions/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def put_keys_in_revision(
        self, organization_guid: str, project_guid: str, name: str, revision_id: str
    ) -> Munch:
        """Put keys in a revision.

        Returns:
            Munch: Revision details as a Munch object.
        """
        headers = self.config.get_headers()
        if organization_guid:
            headers["organizationguid"] = organization_guid
        if project_guid:
            headers["project"] = project_guid
        if name:
            headers["name"] = name

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.put(
            url=f"{v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/keys/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())

    def commit_revision(
        self, organization_guid: str, project_guid: str, name: str, revision_id: str
    ) -> Munch:
        """Commit a revision.

        Returns:
            Munch: Revision details as a Munch object.
        """
        headers = self.config.get_headers()
        if organization_guid:
            headers["organizationguid"] = organization_guid
        if project_guid:
            headers["project"] = project_guid
        if name:
            headers["name"] = name

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.patch(
            url=f"{v2api_host}/v2/configtrees/{name}/revisions/{revision_id}/commit/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())
    
    def list_networks(self, project_guid: str = None) -> Munch:
        """List all networks in a project.

        Returns:
            Munch: List of networks as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/networks/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())
    
    def create_network(self, project_guid: str, body: dict) -> Munch:
        """Create a new network.

        Returns:
            Munch: Network details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.post(
            url=f"{v2api_host}/v2/networks/",
            headers=headers,
            json=body,
        )

        handle_server_errors(response)

        return munchify(response.json())
    
    def get_network(self, project_guid: str, name: str) -> Munch:
        """Get a network by its name.

        Args:
            name (str): Network name

        Returns:
            Munch: Network details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.get(
            url=f"{v2api_host}/v2/networks/{name}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())
    
    def delete_network(self, project_guid: str, name: str) -> Munch:
        """Delete a network by its name.

        Args:
            name (str): Network name

        Returns:
            Munch: Network details as a Munch object.
        """
        headers = self.config.get_headers()
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        response = self.c.delete(
            url=f"{v2api_host}/v2/networks/{name}/",
            headers=headers,
        )

        handle_server_errors(response)

        return munchify(response.json())
