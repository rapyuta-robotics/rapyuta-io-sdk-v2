"""
Pydantic models for Project resource validation.

This module contains Pydantic models that correspond to the Project JSON schema,
providing validation for Project resources to help users identify missing or
incorrect fields.
"""

from typing import Literal
from pydantic import BaseModel, Field, model_validator

from rapyuta_io_sdk_v2.models.utils import BaseMetadata, BaseList


class RoleSpec(str):
    pass


class User(BaseModel):
    emailID: str
    firstName: str | None = None
    lastName: str | None = None
    userGUID: str | None = None
    role: Literal["admin", "viewer"] | None = Field(default="viewer")


class UserGroup(BaseModel):
    name: str
    userGroupGUID: str | None = None
    role: Literal["admin", "viewer"] | None = Field(default="viewer")


class FeaturesVPN(BaseModel):
    subnets: list[str] | None = None
    enabled: bool = Field(default=False)


class FeaturesTracing(BaseModel):
    enabled: bool = Field(default=False)


class FeaturesDockerCache(BaseModel):
    enabled: bool = Field(default=False)
    proxyDevice: str | None = None
    proxyInterface: str | None = None
    registrySecret: str | None = None
    registryURL: str | None = None
    dataDirectory: str | None = Field(default="/opt/rapyuta/volumes/docker-cache/")

    @model_validator(mode="after")
    def validate_data_directory(self):
        if not self.enabled:
            self.dataDirectory = None
        return self


class Features(BaseModel):
    vpn: FeaturesVPN | None = None
    tracing: FeaturesTracing | None = None
    dockerCache: FeaturesDockerCache | None = None


class ProjectSpec(BaseModel):
    users: list[User] | None = None
    userGroups: list[UserGroup] | None = None
    features: Features | None = None


class ProjectStatus(BaseModel):
    status: str | None = None
    vpn: str | None = None
    tracing: str | None = None


class Metadata(BaseMetadata):
    """Metadata for Project resource."""

    pass


class Project(BaseModel):
    """Project model."""

    apiVersion: str | None = None
    kind: str | None = None
    metadata: BaseMetadata | None = None
    spec: ProjectSpec | None = None
    status: ProjectStatus | None = None


class ProjectList(BaseList[Project]):
    """List of projects using BaseList."""

    pass
    """List of Project resources."""

    pass
