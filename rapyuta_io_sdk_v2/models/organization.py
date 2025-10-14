from pydantic import BaseModel, Field
from typing import Literal
from .utils import BaseMetadata

# Define allowed roles
RoleType = Literal["admin", "viewer"]


class OrganizationUser(BaseModel):
    guid: str = Field(default="", description="User GUID")
    firstName: str = Field(default="", description="First name of the user")
    lastName: str = Field(default="", description="Last name of the user")
    emailID: str = Field(default="", description="Email ID of the user")
    roleInOrganization: RoleType = Field(description="Role in the organization")


class OrganizationSpec(BaseModel):
    users: list[OrganizationUser] = Field(
        default_factory=list, description="List of users in the organization"
    )


class Organization(BaseModel):
    metadata: BaseMetadata = Field(description="Metadata for the Organization resource")
    spec: OrganizationSpec = Field(
        description="Specification for the Organization resource"
    )
