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
from rapyuta_io_sdk_v2.utils import handle_server_errors, handle_and_munchify_response


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

    def get_project(self, **kwargs) -> Munch:
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
        project_guid = kwargs.get("project_guid")
        if project_guid is None:
            project_guid = self.config.project_guid

        if not project_guid:
            raise ValueError("project_guid is required")

        v2api_host = self.config.hosts.get("v2api_host")

        return handle_and_munchify_response(
            self.c.get(
                url=f"{v2api_host}/v2/projects/{project_guid}/",
                headers=self.config.get_headers(with_project=False, **kwargs),
            )
        )

    @handle_and_munchify_response
    def list_projects(self, **kwargs) -> Munch:
        """List all projects.

        Returns:
            Munch: List of projects as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/projects/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )

    @handle_and_munchify_response
    def create_project(self, **kwargs) -> Munch:
        """Create a new project.

        Returns:
            Munch: Project details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.post(
            url=f"{v2api_host}/v2/projects/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=kwargs.get("body"),
        )

    @handle_and_munchify_response
    def update_project(self, **kwargs) -> Munch:
        """Update a project by its GUID.

        Returns:
            Munch: Project details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        project_guid = kwargs.get("project_guid")
        body = kwargs.get("body")

        return self.c.put(
            url=f"{v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def delete_project(self, **kwargs) -> Munch:
        """Delete a project by its GUID.

        Returns:
            Munch: Project details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        project_guid = kwargs.get("project_guid")

        return self.c.delete(
            url=f"{v2api_host}/v2/projects/{project_guid}/",
            headers=self.config.get_headers(with_project=False, **kwargs),
        )

    @handle_and_munchify_response
    def update_project_owner(self, **kwargs) -> Munch:
        """Update the owner of a project by its GUID.

        Returns:
            Munch: Project details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        project_guid = kwargs.get("project_guid")
        body = kwargs.get("body")

        return self.c.put(
            url=f"{v2api_host}/v2/projects/{project_guid}/owner/",
            headers=self.config.get_headers(**kwargs),
            json=body,
        )

    @handle_and_munchify_response
    def list_packages(self, **kwargs) -> Munch:
        """List all packages in a project.

        Returns:
            Munch: List of packages as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)
        project_guid = kwargs.get("project_guid")

        if project_guid:
            headers["project"] = project_guid

        return self.c.get(
            url=f"{v2api_host}/v2/packages/",
            headers=headers,
        )

    @handle_and_munchify_response
    def create_package(self, **kwargs) -> Munch:
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
            json=kwargs.get("body"),
        )

    @handle_and_munchify_response
    def get_package(self, **kwargs) -> Munch:
        """Get a package by its name.

        Returns:
            Munch: Package details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        name = kwargs.get("name")

        return self.c.get(
            url=f"{v2api_host}/v2/packages/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    def delete_package(self, **kwargs) -> Munch:
        """Delete a package by its name.

        Returns:
            Munch: Package details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        name = kwargs.get("name")

        return self.c.delete(
            url=f"{v2api_host}/v2/packages/{name}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    def list_deployments(self, **kwargs) -> Munch:
        """List all deployments in a project.

        Returns:
            Munch: List of deployments as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)
        project_guid = kwargs.get("project_guid")

        if project_guid:
            headers["project"] = project_guid

        return self.c.get(
            url=f"{v2api_host}/v2/deployments/",
            headers=headers,
        )

    @handle_and_munchify_response
    def create_deployment(self, **kwargs) -> Munch:
        """Create a new deployment.

        Returns:
            Munch: Deployment details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)
        project_guid = kwargs.get("project_guid")

        if project_guid:
            headers["project"] = project_guid

        return self.c.post(
            url=f"{v2api_host}/v2/deployments/",
            headers=headers,
            json=kwargs.get("body"),
        )

    @handle_and_munchify_response
    def get_deployment(self, **kwargs) -> Munch:
        """Get a deployment by its name.

        Returns:
            Munch: Deployment details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)
        project_guid = kwargs.get("project_guid")
        name = kwargs.get("name")

        if project_guid:
            headers["project"] = project_guid

        return self.c.get(
            url=f"{v2api_host}/v2/deployments/{name}/",
            headers=headers,
        )

    @handle_and_munchify_response
    def update_deployment(self, **kwargs) -> Munch:
        """Update a deployment by its name.

        Returns:
            Munch: Deployment details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)
        project_guid = kwargs.get("project_guid")
        name = kwargs.get("name")

        if project_guid:
            headers["project"] = project_guid

        return self.c.put(
            url=f"{v2api_host}/v2/deployments/{name}/",
            headers=headers,
            json=kwargs.get("body"),
        )

    @handle_and_munchify_response
    def delete_deployment(self, **kwargs) -> Munch:
        """Delete a deployment by its name.

        Returns:
            Munch: Deployment details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)
        project_guid = kwargs.get("project_guid")
        name = kwargs.get("name")

        if project_guid:
            headers["project"] = project_guid

        return self.c.delete(
            url=f"{v2api_host}/v2/deployments/{name}/",
            headers=headers,
        )

    @handle_and_munchify_response
    def list_disks(self, **kwargs) -> Munch:
        """List all disks in a project.

        Returns:
            Munch: List of disks as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/disks/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    def get_disk(self, **kwargs) -> Munch:
        """Get a disk by its name.

        Args:
            name (str): Disk name

        Returns:
            Munch: Disk details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/disks/{kwargs.get('name')}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    def create_disk(self, **kwargs) -> Munch:
        """Create a new disk.

        Returns:
            Munch: Disk details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.post(
            url=f"{v2api_host}/v2/disks/",
            headers=self.config.get_headers(**kwargs),
            json=kwargs.get("body"),
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

    @handle_and_munchify_response
    def list_staticroutes(self, **kwargs) -> Munch:
        """List all static routes in a project.

        Returns:
            Munch: List of static routes as a Munch object.
        """
        headers = self.config.get_headers(**kwargs)
        project_guid = kwargs.get("project_guid")
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/staticroutes/",
            headers=headers,
        )

    @handle_and_munchify_response
    def create_staticroute(self, **kwargs) -> Munch:
        """Create a new static route.

        Returns:
            Munch: Static route details as a Munch object.
        """
        headers = self.config.get_headers(**kwargs)
        project_guid = kwargs.get("project_guid")
        if project_guid:
            headers["project"] = project_guid
        body = kwargs.get("body")

        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.post(
            url=f"{v2api_host}/v2/staticroutes/",
            headers=headers,
            json=body,
        )

    @handle_and_munchify_response
    def get_staticroute(self, **kwargs) -> Munch:
        """Get a static route by its name.

        Args:
            name (str): Static route name

        Returns:
            Munch: Static route details as a Munch object.
        """
        headers = self.config.get_headers(**kwargs)
        project_guid = kwargs.get("project_guid")
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/staticroutes/{kwargs.get('name')}/",
            headers=headers,
        )

    @handle_and_munchify_response
    def update_staticroute(self, **kwargs) -> Munch:
        """Update a static route by its name.

        Args:
            name (str): Static route name
            body (dict): Update details

        Returns:
            Munch: Static route details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.put(
            url=f"{v2api_host}/v2/staticroutes/{kwargs.get('name')}/",
            headers=self.config.get_headers(**kwargs),
            json=kwargs.get("body"),
        )

    @handle_and_munchify_response
    def delete_staticroute(self, **kwargs) -> Munch:
        """Delete a static route by its name.

        Args:
            name (str): Static route name

        Returns:
            Munch: Static route details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.delete(
            url=f"{v2api_host}/v2/staticroutes/{kwargs.get('name')}/",
            headers=self.config.get_headers(**kwargs),
        )

    @handle_and_munchify_response
    def list_networks(self, **kwargs) -> Munch:
        """List all networks in a project.

        Returns:
            Munch: List of networks as a Munch object.
        """
        headers = self.config.get_headers(**kwargs)
        project_guid = kwargs.get("project_guid")
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/networks/",
            headers=headers,
        )

    @handle_and_munchify_response
    def create_network(self, **kwargs) -> Munch:
        """Create a new network.

        Returns:
            Munch: Network details as a Munch object.
        """
        headers = self.config.get_headers()
        project_guid = kwargs.get("project_guid")
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.post(
            url=f"{v2api_host}/v2/networks/",
            headers=headers,
            json=kwargs.get("body"),
        )

    @handle_and_munchify_response
    def get_network(self, **kwargs) -> Munch:
        """Get a network by its name.

        Args:
            name (str): Network name

        Returns:
            Munch: Network details as a Munch object.
        """
        headers = self.config.get_headers()
        project_guid = kwargs.get("project_guid")
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.get(
            url=f"{v2api_host}/v2/networks/{kwargs.get('name')}/",
            headers=headers,
        )

    @handle_and_munchify_response
    def delete_network(self, **kwargs) -> Munch:
        """Delete a network by its name.

        Args:
            name (str): Network name

        Returns:
            Munch: Network details as a Munch object.
        """
        headers = self.config.get_headers()
        project_guid = kwargs.get("project_guid")
        if project_guid:
            headers["project"] = project_guid

        v2api_host = self.config.hosts.get("v2api_host")

        return self.c.delete(
            url=f"{v2api_host}/v2/networks/{kwargs.get('name')}/",
            headers=headers,
        )

    @handle_and_munchify_response
    def list_secrets(self, **kwargs) -> Munch:
        """List all secrets in a project.

        Returns:
            Munch: List of secrets as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)

        if kwargs.get("project_guid"):
            headers["project"] = kwargs["project_guid"]

        return self.c.get(url=f"{v2api_host}/v2/secrets/", headers=headers)

    @handle_and_munchify_response
    def create_secret(self, **kwargs) -> Munch:
        """Create a new secret.

        Returns:
            Munch: Secret details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)

        if kwargs.get("project_guid"):
            headers["project"] = kwargs["project_guid"]

        return self.c.post(
            url=f"{v2api_host}/v2/secrets/",
            headers=headers,
            json=kwargs.get("body"),
        )

    @handle_and_munchify_response
    def get_secret(self, **kwargs) -> Munch:
        """Get a secret by its name.

        Args:
            name (str): Secret name

        Returns:
            Munch: Secret details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)

        if kwargs.get("project_guid"):
            headers["project"] = kwargs["project_guid"]

        return self.c.get(
            url=f"{v2api_host}/v2/secrets/{kwargs['name']}/", headers=headers
        )

    @handle_and_munchify_response
    def update_secret(self, **kwargs) -> Munch:
        """Update a secret by its name.

        Args:
            name (str): Secret name
            body (dict): Update details

        Returns:
            Munch: Secret details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)

        if kwargs.get("project_guid"):
            headers["project"] = kwargs["project_guid"]

        return self.c.put(
            url=f"{v2api_host}/v2/secrets/{kwargs['name']}/",
            headers=headers,
            json=kwargs.get("body"),
        )

    @handle_and_munchify_response
    def delete_secret(self, **kwargs) -> Munch:
        """Delete a secret by its name.

        Args:
            name (str): Secret name

        Returns:
            Munch: Secret details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)

        if kwargs.get("project_guid"):
            headers["project"] = kwargs["project_guid"]

        return self.c.delete(
            url=f"{v2api_host}/v2/secrets/{kwargs['name']}/", headers=headers
        )

    @handle_and_munchify_response
    def list_configtrees(self, **kwargs) -> Munch:
        """List all config trees in a project.

        Returns:
            Munch: List of config trees as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)

        if kwargs.get("organization_guid"):
            headers["organizationguid"] = kwargs["organization_guid"]
        if kwargs.get("project_guid"):
            headers["project"] = kwargs["project_guid"]

        return self.c.get(url=f"{v2api_host}/v2/configtrees/", headers=headers)

    @handle_and_munchify_response
    def create_configtree(self, **kwargs) -> Munch:
        """Create a new config tree.

        Returns:
            Munch: Config tree details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)

        if kwargs.get("organization_guid"):
            headers["organizationguid"] = kwargs["organization_guid"]
        if kwargs.get("project_guid"):
            headers["project"] = kwargs["project_guid"]

        return self.c.post(
            url=f"{v2api_host}/v2/configtrees/",
            headers=headers,
            json=kwargs.get("body"),
        )

    @handle_and_munchify_response
    def get_configtree(self, **kwargs) -> Munch:
        """Get a config tree by its name.

        Args:
            name (str): Config tree name

        Returns:
            Munch: Config tree details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)

        if kwargs.get("organization_guid"):
            headers["organizationguid"] = kwargs["organization_guid"]
        if kwargs.get("project_guid"):
            headers["project"] = kwargs["project_guid"]

        return self.c.get(
            url=f"{v2api_host}/v2/configtrees/{kwargs['name']}/", headers=headers
        )

    @handle_and_munchify_response
    def update_configtree(self, **kwargs) -> Munch:
        """Update a config tree by its name.

        Args:
            name (str): Config tree name
            body (dict): Update details

        Returns:
            Munch: Config tree details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)

        if kwargs.get("organization_guid"):
            headers["organizationguid"] = kwargs["organization_guid"]
        if kwargs.get("project_guid"):
            headers["project"] = kwargs["project_guid"]

        return self.c.put(
            url=f"{v2api_host}/v2/configtrees/{kwargs['name']}/",
            headers=headers,
            json=kwargs.get("body"),
        )

    @handle_and_munchify_response
    def delete_configtree(self, **kwargs) -> Munch:
        """Delete a config tree by its name.

        Args:
            name (str): Config tree name

        Returns:
            Munch: Config tree details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)

        if kwargs.get("organization_guid"):
            headers["organizationguid"] = kwargs["organization_guid"]
        if kwargs.get("project_guid"):
            headers["project"] = kwargs["project_guid"]

        return self.c.delete(
            url=f"{v2api_host}/v2/configtrees/{kwargs['name']}/", headers=headers
        )

    @handle_and_munchify_response
    def list_revisions(self, **kwargs) -> Munch:
        """List all revisions in a project.

        Returns:
            Munch: List of revisions as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)

        if kwargs.get("organization_guid"):
            headers["organizationguid"] = kwargs["organization_guid"]
        if kwargs.get("project_guid"):
            headers["project"] = kwargs["project_guid"]
        if kwargs.get("name"):
            headers["name"] = kwargs["name"]

        return self.c.get(
            url=f"{v2api_host}/v2/configtrees/{kwargs['name']}/revisions/",
            headers=headers,
        )

    @handle_and_munchify_response
    def create_revision(self, **kwargs) -> Munch:
        """Create a new revision.

        Returns:
            Munch: Revision details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)

        if kwargs.get("organization_guid"):
            headers["organizationguid"] = kwargs["organization_guid"]
        if kwargs.get("project_guid"):
            headers["project"] = kwargs["project_guid"]
        if kwargs.get("name"):
            headers["name"] = kwargs["name"]

        return self.c.post(
            url=f"{v2api_host}/v2/configtrees/{kwargs['name']}/revisions/",
            headers=headers,
            json=kwargs.get("body"),
        )

    @handle_and_munchify_response
    def put_keys_in_revision(self, **kwargs) -> Munch:
        """Put keys in a revision.

        Returns:
            Munch: Revision details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)

        if kwargs.get("organization_guid"):
            headers["organizationguid"] = kwargs["organization_guid"]
        if kwargs.get("project_guid"):
            headers["project"] = kwargs["project_guid"]
        if kwargs.get("name"):
            headers["name"] = kwargs["name"]

        return self.c.put(
            url=f"{v2api_host}/v2/configtrees/{kwargs['name']}/revisions/{kwargs['revision_id']}/keys/",
            headers=headers,
        )

    @handle_and_munchify_response
    def commit_revision(self, **kwargs) -> Munch:
        """Commit a revision.

        Returns:
            Munch: Revision details as a Munch object.
        """
        v2api_host = self.config.hosts.get("v2api_host")
        headers = self.config.get_headers(**kwargs)

        if kwargs.get("organization_guid"):
            headers["organizationguid"] = kwargs["organization_guid"]
        if kwargs.get("project_guid"):
            headers["project"] = kwargs["project_guid"]
        if kwargs.get("name"):
            headers["name"] = kwargs["name"]

        return self.c.patch(
            url=f"{v2api_host}/v2/configtrees/{kwargs['name']}/revisions/{kwargs['revision_id']}/commit/",
            headers=headers,
        )
