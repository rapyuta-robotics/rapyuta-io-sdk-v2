from typing import Optional
import httpx

class Client(object):
    def __init__(self,auth_token,project,organization:Optional[str] = None):
        self._host = "https://pr1056api.apps.okd4v2.okd4beta.rapyuta.io"
        self._project = project
        self._token = "Bearer "+auth_token
        if organization is not None:
            self._organization = organization
            return
        self._organization = self.organization

    def _get_auth_header(self, with_project: bool = True) -> dict:
        headers = dict(Authorization=self._token)
        return headers

    def list_projects(self,organization_guid: str = None):
        url = "{}/v2/projects/".format(self._host)
        headers = self._get_auth_header(with_project=False)
        params = {}
        if organization_guid:
            params.update({
                "organizations": organization_guid,
            })
        response = httpx.get(url=url,headers=headers,params=params).json()
        return response

    def get_project(self, project_guid: str):
        url = "{}/v2/projects/{}/".format(self._host, project_guid)
        headers = self._get_auth_header()
        response = httpx.get(url=url,headers=headers).json()
        return response

    @property
    def organization(self) -> Optional[str]:
        _organization = self.get_project(project_guid=self._project)['metadata']['organizationGUID']
        return _organization
