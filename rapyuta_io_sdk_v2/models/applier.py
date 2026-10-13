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

"""Immutable public models used by the reusable applier."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    ConfigDict,
    Field,
    SerializeAsAny,
    StrictInt,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema

from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.progress import MutationAction, MutationJournal

ResourceKind = Literal[
    "organization",
    "project",
    "usergroup",
    "role",
    "rolebinding",
    "serviceaccount",
    "package",
    "deployment",
    "disk",
    "network",
    "staticroute",
    "secret",
    "user",
    "device",
]
ApplyPolicy = Literal["create_or_update", "create_or_exists", "update_only", "grant"]
OutcomeStatus = Literal[
    "created",
    "updated",
    "exists",
    "deleted",
    "absent",
    "retained",
    "planned",
    "failed",
    "not_completed",
]
PlannedAction = Literal[
    "create_or_update", "create_or_exists", "update", "grant", "delete", "revoke"
]

_SUPPORTED_KINDS = frozenset(ResourceKind.__args__)
_NAMED_KINDS = _SUPPORTED_KINDS - {"rolebinding"}
_SUBJECT_KINDS = frozenset({"user", "usergroup", "serviceaccount"})
_DOMAIN_KINDS = frozenset({"usergroup", "project", "organization"})


class ResourceScope(SDKModel):
    """Optional organization and project identifiers for one operation."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    organization_guid: str | None = Field(default=None, min_length=1)
    project_guid: str | None = Field(default=None, min_length=1)
    organization_short_guid: str | None = Field(default=None, min_length=1)


class ResourceReference(SDKModel):
    """A structurally identified managed or external resource reference."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    kind: ResourceKind
    name: str | None = Field(default=None, min_length=1)
    guid: str | None = Field(default=None, min_length=1)
    version: str | None = None

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, value: object) -> object:
        """Normalize supported kind spellings without changing identifiers."""
        return value.lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_reference(self) -> ResourceReference:
        """Require identity and a concrete version for Package references."""
        if self.name is None and self.guid is None:
            msg = "a reference requires a name or GUID"
            raise ValueError(msg)
        if self.kind == "package" and (self.version is None or self.version == ""):
            msg = "Package references require a non-empty version"
            raise ValueError(msg)
        return self


class ResourceIdentity(SDKModel):
    """A typed, structured identity suitable for dependency graph keys."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    kind: ResourceKind
    scope: ResourceScope = Field(default_factory=ResourceScope)
    name: str | None = Field(default=None, min_length=1)
    guid: str | None = Field(default=None, min_length=1)
    version: str | None = None
    role: ResourceReference | None = None
    subject: ResourceReference | None = None
    domain: ResourceReference | None = None

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, value: object) -> object:
        """Normalize supported kind spellings without changing identifiers."""
        return value.lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_identity(self) -> ResourceIdentity:
        """Validate named and composite identities without parsing display keys."""
        self._validate_named_identity()
        self._validate_rolebinding_identity()
        return self

    def _validate_named_identity(self) -> None:
        if self.kind in _NAMED_KINDS and self.name is None:
            msg = f"{self.kind} resources require a name"
            raise ValueError(msg)
        if self.kind == "package" and (self.version is None or self.version == ""):
            msg = "Package identities require a non-empty version"
            raise ValueError(msg)

    def _validate_rolebinding_identity(self) -> None:
        if self.kind != "rolebinding":
            return
        if self.role is None or self.role.kind != "role":
            msg = "RoleBinding identity requires a typed role reference"
            raise ValueError(msg)
        if self.subject is None or self.subject.kind not in _SUBJECT_KINDS:
            msg = "RoleBinding identity requires a typed subject reference"
            raise ValueError(msg)
        if self.domain is None or self.domain.kind not in _DOMAIN_KINDS:
            msg = "RoleBinding identity requires a typed domain reference"
            raise ValueError(msg)


class DependencyReference(SDKModel):
    """An explicit resource prerequisite and optional readiness requirement."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    reference: ResourceReference
    wait: bool = False


class ResourceCapabilities(SDKModel):
    """Immutable lifecycle support declared by one resource model."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    create: bool
    update: bool
    delete: bool
    apply_policy: ApplyPolicy
    readiness_kind: str | None = None


class ReadinessOptions(SDKModel):
    """Bounded polling policy shared by resource lifecycle methods."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    checks: StrictInt = Field(default=50, ge=1)
    interval: float = Field(default=6.0, ge=0, allow_inf_nan=False)


class ApplierOptions(SDKModel):
    """Worker, readiness, and default routing settings for one facade."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    workers: StrictInt = Field(default=6, gt=0)
    readiness: ReadinessOptions = Field(default_factory=ReadinessOptions)
    scope: ResourceScope = Field(default_factory=ResourceScope)


class ResourceContext(SDKModel):
    """Frozen per-operation context, with an optional runtime recorder."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        frozen=True,
        populate_by_name=True,
    )

    scope: ResourceScope = Field(default_factory=ResourceScope)
    readiness: ReadinessOptions = Field(default_factory=ReadinessOptions)
    progress: SkipJsonSchema[MutationJournal | None] = Field(
        default=None, exclude=True, repr=False
    )


class SourceLocation(SDKModel):
    """Manifest file/document or caller resource attribution."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    path: str | None = None
    instance_index: StrictInt | None = Field(default=None, ge=0)
    document_index: StrictInt | None = Field(default=None, ge=0)


class OperationFailure(SDKModel):
    """Safe structured diagnostic for one failed lifecycle stage."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    category: str
    stage: str
    message: str
    exception_type: str | None = None


class ResourceOutcome(SDKModel):
    """Immutable lifecycle status for one managed input resource."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    identity: ResourceIdentity
    source: SourceLocation | None = None
    operation: Literal["apply", "delete"]
    status: OutcomeStatus
    planned_action: PlannedAction | None = None
    completed_actions: tuple[MutationAction, ...] = ()
    failure: OperationFailure | None = None
    incomplete_reason: Literal["cancelled", "blocked", "not_started"] | None = None
    write_uncertain: bool = False


class ApplierResult(SDKModel):
    """Immutable ordered result for a live operation or offline preview."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    operation: Literal["apply", "delete"]
    dry_run: bool = False
    outcomes: tuple[ResourceOutcome, ...] = ()

    @computed_field
    @property
    def successful(self) -> bool:
        """Whether every outcome is successful or a valid plan."""
        return all(
            outcome.status
            in {
                "created",
                "updated",
                "exists",
                "deleted",
                "absent",
                "retained",
                "planned",
            }
            for outcome in self.outcomes
        )


class DependencyGraph(SDKModel):
    """Inspectable graph edges and references outside the managed set."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    managed: tuple[ResourceIdentity, ...] = ()
    edges: tuple[tuple[ResourceIdentity, ResourceIdentity], ...] = ()
    external_references: tuple[DependencyReference, ...] = ()


class RenderedDocument(SDKModel):
    """Independent parsed manifest before resource model normalization."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    source: SourceLocation
    data: dict[str, Any]


class InspectionResult(SDKModel):
    """Independent prepared manifests and graph metadata for inspection."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    resource_identities: tuple[ResourceIdentity, ...] = ()
    resolved_manifests: tuple[SerializeAsAny[SDKModel], ...] = ()
    rendered_documents: tuple[RenderedDocument, ...] = ()
    dependency_graph: DependencyGraph = Field(default_factory=DependencyGraph)


class SopsOptions(SDKModel):
    """Executable and cleanup grace for explicit SOPS decryption."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    executable: str = Field(default="sops", min_length=1)
    termination_grace: float = Field(default=1.0, gt=0, allow_inf_nan=False)


__all__ = [
    "ApplierOptions",
    "ApplierResult",
    "DependencyGraph",
    "DependencyReference",
    "InspectionResult",
    "OperationFailure",
    "ReadinessOptions",
    "RenderedDocument",
    "ResourceCapabilities",
    "ResourceContext",
    "ResourceIdentity",
    "ResourceKind",
    "ResourceOutcome",
    "ResourceReference",
    "ResourceScope",
    "SopsOptions",
    "SourceLocation",
]
