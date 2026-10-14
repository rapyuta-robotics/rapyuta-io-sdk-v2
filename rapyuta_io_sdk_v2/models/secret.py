# Copyright 2026 Rapyuta Robotics
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

"""Pydantic models for Secret resource validation.

This module contains Pydantic models that correspond to the Secret JSON schema,
providing validation for Secret resources to help users identify missing or
incorrect fields.
"""
# Lifecycle helper imports remain local to keep model modules independent.

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field, model_validator

from rapyuta_io_sdk_v2.models.applier import (
    DependencyReference,
    ResourceCapabilities,
    ResourceContext,
    ResourceReference,
    ResourceScope,
)
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.resource import ResourceMethods
from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    DeviceDepends,
    Runtime,
)

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client


class DockerSpec(SDKModel):
    """Registry login details stored in a Docker secret."""

    registry: str = Field(
        default="https://index.docker.io/v1/", description="Docker registry URL"
    )
    username: str = Field(description="Username for docker registry authentication")
    email: str = Field(description="Email for docker registry authentication")


class DockerSpecCreate(DockerSpec):
    """Registry credentials supplied when creating a Docker secret."""

    password: str = Field(description="Password for docker registry authentication")


SecretType = Literal["Docker", "Opaque"]


class SecretSpec(SDKModel):
    """Specification for Secret resource."""

    type: SecretType = Field(
        description="Type of the secret: Docker or Opaque",
    )
    docker: DockerSpec | None = Field(
        default=None,
        description="Docker registry configuration when type is Docker",
    )
    data: dict[str, str] | None = Field(
        default=None,
        description="Arbitrary key-value data for Opaque secrets",
    )
    secret_keys: list[str] | None = Field(
        default=None,
        alias="secretKeys",
        description=(
            "List of keys present in the secret (read-only, returned by server)"
        ),
    )
    runtime: Runtime | None = None
    depends: DeviceDepends | None = None


class SecretSpecCreate(SDKModel):
    """Credential payload and dependency settings for a new secret."""

    type: SecretType = Field(
        description="Type of the secret: Docker or Opaque",
    )
    docker: DockerSpecCreate | None = None
    data: dict[str, str] | None = Field(
        default=None,
        description="Arbitrary key-value data for Opaque secrets",
    )
    runtime: Runtime | None = None
    depends: DeviceDepends | None = None


class Secret(ResourceMethods, BaseObject):
    """Secret model."""

    KIND: ClassVar[str] = "Secret"
    CAPABILITIES: ClassVar[ResourceCapabilities] = ResourceCapabilities(
        create=True, update=True, delete=True, apply_policy="create_or_update"
    )

    kind: Literal["Secret"] | None = "Secret"
    metadata: BaseMetadata
    spec: SecretSpec = Field(description="Specification for the Secret resource")

    def resource_dependencies(
        self, *, scope: ResourceScope | None = None
    ) -> tuple[DependencyReference, ...]:
        """Declare an external Device only for explicit device runtime."""
        del scope
        if self.spec.runtime != "device" or self.spec.depends is None:
            return ()
        value = self.spec.depends.name_or_guid
        return (
            DependencyReference(
                reference=ResourceReference(kind="device", name=value, guid=value)
            ),
        )

    def create_object(self, client: Client, *, context: ResourceContext) -> Secret:
        """Create a Secret without dropping SecretCreate credentials."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write,
            scoped_context,
        )

        context = scoped_context(self, context)
        payload = self._create_payload(context)
        return record_write(
            context,
            "created",
            lambda: client.create_secret(payload, **project_options(context)),
        )

    async def create_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> Secret:
        """Create a Secret through the native asynchronous endpoint."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write_async,
            scoped_context,
        )

        context = scoped_context(self, context)
        payload = self._create_payload(context)
        return await record_write_async(
            context,
            "created",
            lambda: client.create_secret(payload, **project_options(context)),
        )

    def update_object(self, client: Client, *, context: ResourceContext) -> Secret:
        """Update a Secret with its credential-bearing request variant."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write,
            scoped_context,
        )

        context = scoped_context(self, context)
        payload = self._create_payload(context)
        return record_write(
            context,
            "updated",
            lambda: client.update_secret(
                payload.metadata.name, payload, **project_options(context)
            ),
        )

    async def update_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> Secret:
        """Update a Secret through the native asynchronous endpoint."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write_async,
            scoped_context,
        )

        context = scoped_context(self, context)
        payload = self._create_payload(context)
        return await record_write_async(
            context,
            "updated",
            lambda: client.update_secret(
                payload.metadata.name, payload, **project_options(context)
            ),
        )

    def _delete_object(self, client: Client, *, context: ResourceContext) -> None:
        """Delete this Secret without requiring create credentials."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write,
        )

        record_write(
            context,
            "deleted",
            lambda: client.delete_secret(
                self.metadata.name, **project_options(context)
            ),
        )

    async def _delete_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> None:
        """Delete this Secret through the native async client."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write_async,
        )

        await record_write_async(
            context,
            "deleted",
            lambda: client.delete_secret(
                self.metadata.name, **project_options(context)
            ),
        )

    def _create_payload(self, context: ResourceContext) -> SecretCreate:
        """Build a private creation request preserving caller-supplied fields."""
        from rapyuta_io_sdk_v2.apply._resources.standard import scoped_copy  # noqa: PLC0415

        payload = scoped_copy(self, context)
        return SecretCreate.model_validate(payload.model_dump(mode="python"))


class SecretCreate(Secret):
    """Secret creation manifest with the required credential payload."""

    spec: SecretSpecCreate

    @model_validator(mode="after")
    def validate_create_fields(self) -> SecretCreate:
        """Require credential fields for the selected secret type."""
        spec = self.spec
        if spec.type == "Docker":
            if spec.docker is None:
                message = "'spec.docker' is required when creating a Docker secret"
                raise ValueError(message)
        elif spec.type == "Opaque" and not spec.data:
            message = "'spec.data' is required when creating an Opaque secret"
            raise ValueError(message)
        return self

    def list_dependencies(self) -> list[str] | None:
        """Return resource dependencies in manifest order."""
        runtime = self.spec.runtime

        if not runtime or runtime == "cloud":
            return None

        if self.spec.depends is not None:
            device_name = self.spec.depends.name_or_guid
            return [f"device:{device_name}"]

        return None


class SecretList(BaseList[Secret]):
    """List of secrets using BaseList."""
