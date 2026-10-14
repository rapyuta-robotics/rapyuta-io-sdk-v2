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

"""Resource validation models for rolebinding."""
# Lifecycle helper imports remain local to keep model modules independent.

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal, cast

from pydantic import Field, model_validator

from rapyuta_io_sdk_v2.models.applier import (
    DependencyReference,
    ResourceCapabilities,
    ResourceIdentity,
    ResourceReference,
    ResourceScope,
)
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.resource import ResourceMethods
from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    Domain,
    Subject,
)

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.models.applier import ResourceContext, ResourceOutcome


class RoleBindingMetadata(BaseMetadata):
    """Binding metadata that omits the resource name."""

    name: None = Field(default=None, exclude=True)


class RoleRef(SDKModel):
    """Role identified by name or GUID."""

    kind: Literal["Role"] = "Role"
    name: str | None = None
    guid: str | None = None

    @model_validator(mode="after")
    def ensure_name_or_guid(self) -> RoleRef:
        """Require a resource name or GUID."""
        if self.name is None and self.guid is None:
            message = "either 'name' or 'guid' should be specified"
            raise ValueError(message)

        return self


class RoleBindingSpec(SDKModel):
    """Role granted to a subject within a domain."""

    role_ref: RoleRef = Field(alias="roleRef")
    domain: Domain
    subject: Subject


class RoleBinding(ResourceMethods, BaseObject):
    """Authorization grant connecting a role, subject, and domain."""

    KIND: ClassVar[str] = "RoleBinding"
    CAPABILITIES: ClassVar[ResourceCapabilities] = ResourceCapabilities(
        create=False, update=False, delete=True, apply_policy="grant"
    )

    kind: Literal["RoleBinding"] | None = "RoleBinding"
    metadata: RoleBindingMetadata
    spec: RoleBindingSpec

    def resource_identity(
        self, *, scope: ResourceScope | None = None
    ) -> ResourceIdentity:
        """Use the role, subject, and domain tuple as the binding identity."""
        selected_scope = scope or ResourceScope()
        if self.spec.subject.kind is None:
            msg = "RoleBinding subject kind is required for identity"
            raise ValueError(msg)
        if self.spec.domain.kind is None:
            msg = "RoleBinding domain kind is required for identity"
            raise ValueError(msg)
        role = ResourceReference(
            kind="role", name=self.spec.role_ref.name, guid=self.spec.role_ref.guid
        )
        subject = ResourceReference(
            kind=self.spec.subject.kind,
            name=self.spec.subject.name,
            guid=self.spec.subject.guid,
        )
        domain = ResourceReference(
            kind=self.spec.domain.kind,
            name=self.spec.domain.name,
            guid=self.spec.domain.guid,
        )
        return ResourceIdentity(
            kind="rolebinding",
            scope=ResourceScope(
                organization_guid=(
                    self.metadata.organization_guid or selected_scope.organization_guid
                )
            ),
            guid=self.metadata.guid,
            role=role,
            subject=subject,
            domain=domain,
        )

    def resource_dependencies(
        self, *, scope: ResourceScope | None = None
    ) -> tuple[DependencyReference, ...]:
        """Declare the exact role, subject, and domain references in the grant."""
        identity = self.resource_identity(scope=scope)
        return tuple(
            DependencyReference(reference=reference)
            for reference in (
                cast("ResourceReference", identity.role),
                cast("ResourceReference", identity.subject),
                cast("ResourceReference", identity.domain),
            )
        )

    def apply(self, client: Client, *, context: ResourceContext) -> ResourceOutcome:
        """Create the grant only when its exact tuple is absent."""
        from rapyuta_io_sdk_v2.apply._resources.rolebinding import apply_rolebinding  # noqa: PLC0415

        return apply_rolebinding(client, self, context=context)

    async def apply_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> ResourceOutcome:
        """Apply the grant through native async lookup and mutation calls."""
        from rapyuta_io_sdk_v2.apply._resources.rolebinding import (  # noqa: PLC0415
            apply_rolebinding_async,
        )

        return await apply_rolebinding_async(client, self, context=context)

    def _delete_object(self, client: Client, *, context: ResourceContext) -> None:
        """Revoke this exact role/subject/domain tuple."""
        from rapyuta_io_sdk_v2.apply._resources.rolebinding import delete_rolebinding  # noqa: PLC0415

        delete_rolebinding(client, self, context=context)

    async def _delete_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> None:
        """Revoke the exact grant using native async lookup and mutation calls."""
        from rapyuta_io_sdk_v2.apply._resources.rolebinding import (  # noqa: PLC0415
            delete_rolebinding_async,
        )

        await delete_rolebinding_async(client, self, context=context)

    def list_dependencies(self) -> list[str] | None:
        """Return resource dependencies in manifest order."""
        dependencies: list[str] = []

        # Add role dependency
        if self.spec.role_ref.name is not None:
            dependencies.append(f"role:{self.spec.role_ref.name}")

        # Add subject dependency
        if self.spec.subject.kind is not None and self.spec.subject.name is not None:
            dependencies.append(f"{self.spec.subject.kind}:{self.spec.subject.name}")

        # Add domain dependency
        if self.spec.domain.kind is not None and self.spec.domain.name is not None:
            dependencies.append(f"{self.spec.domain.kind}:{self.spec.domain.name}")

        return dependencies


class BulkRoleBindingUpdate(SDKModel):
    """Bindings to add and bindings to replace in one update."""

    new_bindings: list[RoleBinding] = Field(default_factory=list, alias="newBindings")
    old_bindings: list[RoleBinding | None] = Field(
        default_factory=list, alias="oldBindings"
    )


class RoleBindingList(BaseList[RoleBinding]):
    """Paginated role binding resources."""
