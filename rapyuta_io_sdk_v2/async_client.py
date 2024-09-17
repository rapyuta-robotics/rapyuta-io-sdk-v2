from rapyuta_io_sdk_v2.client import Client
from typing import Optional, override
import httpx

class AsyncClient(Client):
    def __init__(self, auth_token, project, organization: Optional[str] = None):
        # super().__init__(auth_token=auth_token,project=project,organization=organization)

        self._host = "https://pr1056api.apps.okd4v2.okd4beta.rapyuta.io"
        self._project = project
        self._token = "Bearer "+auth_token
        self._organization = organization

    async def async_init(self):
        if not self._organization:
            await self._set_organization(self._project)

    def _get_auth_header(self, with_project: bool = True) -> dict:
        headers = dict(Authorization=self._token)
        return headers

    @override
    async def list_projects(self, organization_guid: str = None):
        url = "{}/v2/projects/".format(self._host)
        headers = self._get_auth_header(with_project=False)
        params = {}
        if organization_guid:
            params.update({
                "organizations": organization_guid,
            })
        async with httpx.AsyncClient() as client:
            response = await client.get(url=url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()

    @override
    async def get_project(self, project_guid: str):
        url = "{}/v2/projects/{}/".format(self._host, project_guid)
        headers = self._get_auth_header()
        async with httpx.AsyncClient() as client:
            response = await client.get(url=url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def _set_organization(self,project):
        project_info= await self.get_project(project_guid=project)
        self._organization = project_info['metadata']['organizationGUID']




