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

"""Safe local parsing, templating, and initial resource preparation."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import yaml
from jinja2 import UndefinedError
from pydantic import ValidationError

from rapyuta_io_sdk_v2.apply._filters import create_environment
from rapyuta_io_sdk_v2.apply._graph import GraphPlan, prepare_dependency_graph
from rapyuta_io_sdk_v2.apply.errors import ApplierValidationError
from rapyuta_io_sdk_v2.models.applier import (
    DependencyGraph,
    DependencyReference,
    ResourceIdentity,
    ResourceReference,
    ResourceScope,
    SourceLocation,
)
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.deployment import Deployment
from rapyuta_io_sdk_v2.models.disk import Disk
from rapyuta_io_sdk_v2.models.network import Network
from rapyuta_io_sdk_v2.models.organization import Organization
from rapyuta_io_sdk_v2.models.package import Package
from rapyuta_io_sdk_v2.models.project import Project
from rapyuta_io_sdk_v2.models.role import Role
from rapyuta_io_sdk_v2.models.rolebinding import RoleBinding
from rapyuta_io_sdk_v2.models.secret import Secret, SecretCreate
from rapyuta_io_sdk_v2.models.serviceaccount import ServiceAccount
from rapyuta_io_sdk_v2.models.staticroute import StaticRoute
from rapyuta_io_sdk_v2.models.usergroup import UserGroup, UserGroupCreate

if TYPE_CHECKING:
    from jinja2.sandbox import ImmutableSandboxedEnvironment

    from rapyuta_io_sdk_v2.apply.source import (
        DeviceInterfaceResolver,
        JsonValue,
        ManifestSource,
    )

KIND_MODELS: dict[str, type[SDKModel]] = {
    "organization": Organization,
    "project": Project,
    "package": Package,
    "deployment": Deployment,
    "disk": Disk,
    "network": Network,
    "staticroute": StaticRoute,
    "secret": Secret,
    "usergroup": UserGroup,
    "role": Role,
    "rolebinding": RoleBinding,
    "serviceaccount": ServiceAccount,
}
_CANONICAL_KINDS = {
    "organization": "Organization",
    "project": "Project",
    "package": "Package",
    "deployment": "Deployment",
    "disk": "Disk",
    "network": "Network",
    "staticroute": "StaticRoute",
    "secret": "Secret",
    "usergroup": "UserGroup",
    "role": "Role",
    "rolebinding": "RoleBinding",
    "serviceaccount": "ServiceAccount",
}
_PROJECT_SCOPED_KINDS = frozenset(
    {"package", "deployment", "disk", "network", "staticroute", "secret"}
)


@dataclass(frozen=True, slots=True)
class PreparedResource:
    """One deep-copied, locally validated resource and its source position."""

    resource: SDKModel
    identity: ResourceIdentity
    dependencies: tuple[DependencyReference, ...]
    source: SourceLocation
    index: int
    source_data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PreparedCollection:
    """Local prepared resources and dependency metadata, with no client state."""

    resources: tuple[PreparedResource, ...]
    dependency_graph: DependencyGraph
    graph_plan: GraphPlan

    @property
    def resolved_manifests(self) -> tuple[SDKModel, ...]:
        """Return fresh copies so inspection cannot mutate prepared state."""
        return tuple(deepcopy(item.resource) for item in self.resources)


def prepare_source(
    source: ManifestSource, scope: ResourceScope | None = None
) -> PreparedCollection:
    """Parse, render, and validate all supplied resources without network use."""
    value_context = _load_value_sources(source.values, purpose="values")
    secret_context = _load_value_sources(source.secrets, purpose="secrets")
    rio_context = _require_string_mapping(
        source.rio if source.rio is not None else {}, SourceLocation(), "rio"
    )
    _validate_json_value(rio_context, SourceLocation(), "rio")
    context: dict[str, Any] = deepcopy(value_context)
    context["secrets"] = secret_context
    context["rio"] = deepcopy(rio_context)
    documents = _read_manifest_files(
        source.files,
        context,
        scope=scope or ResourceScope(),
        interface_resolver=source.interface_resolver,
    )
    documents.extend(_copy_resource_instances(source.resources))
    resources = _prepare_resources(documents)
    canonical_resources, graph_plan = _prepare_graph(resources)
    return PreparedCollection(
        resources=canonical_resources,
        dependency_graph=graph_plan.dependency_graph,
        graph_plan=graph_plan,
    )


def _prepare_resources(
    documents: Sequence[tuple[object, SourceLocation]],
) -> list[PreparedResource]:
    resources: list[PreparedResource] = []
    for document, location in documents:
        source_data = _document_data(document)
        resource = _validate_resource(document, location)
        identity = resource_identity(resource, location)
        resources.append(
            PreparedResource(
                resource=resource,
                identity=identity,
                dependencies=(),
                source=location,
                index=len(resources),
                source_data=source_data,
            )
        )
    return resources


def _prepare_graph(
    resources: list[PreparedResource],
) -> tuple[tuple[PreparedResource, ...], GraphPlan]:
    try:
        graph_plan = prepare_dependency_graph(
            [(item.identity, item.dependencies) for item in resources]
        )
    except ApplierValidationError as exc:
        source_location = _source_for_identity(resources, exc.identities)
        raise ApplierValidationError(
            str(exc),
            source=source_location,
            category=exc.category,
            identities=exc.identities,
        ) from exc
    canonical_resources = tuple(
        replace(item, identity=graph_plan.dependency_graph.managed[index])
        for index, item in enumerate(resources)
    )
    return canonical_resources, graph_plan


def resource_identity(resource: SDKModel, source: SourceLocation) -> ResourceIdentity:
    """Build the common structural identity used during local preparation."""
    kind_name = _resource_kind(resource, source)
    metadata = cast("Any", resource).metadata
    if metadata is None:
        msg = "resource metadata is required"
        raise ApplierValidationError(
            msg,
            source=source,
            category="identity",
        )
    organization_guid = (
        metadata.guid if kind_name == "organization" else metadata.organization_guid
    )
    project_guid = metadata.project_guid if kind_name in _PROJECT_SCOPED_KINDS else None
    scope = ResourceScope(
        organization_guid=organization_guid,
        project_guid=project_guid,
        organization_short_guid=metadata.short_guid
        if kind_name == "organization"
        else None,
    )
    identity_data: dict[str, Any] = {
        "kind": kind_name,
        "scope": scope,
        "name": metadata.name,
        "guid": metadata.guid,
    }
    if kind_name == "package":
        identity_data["version"] = metadata.version
    elif kind_name == "rolebinding":
        identity_data.update(_rolebinding_identity(resource, source))
    try:
        return ResourceIdentity.model_validate(identity_data)
    except ValidationError as exc:
        raise ApplierValidationError(
            str(exc), source=source, category="identity"
        ) from exc


def _read_manifest_files(
    files: Sequence[str | Path],
    context: Mapping[str, Any],
    *,
    scope: ResourceScope,
    interface_resolver: DeviceInterfaceResolver | None,
) -> list[tuple[object, SourceLocation]]:
    return [
        document
        for input_path in files
        for document in _read_manifest_file(
            input_path,
            context,
            scope=scope,
            interface_resolver=interface_resolver,
        )
    ]


def _manifest_text(input_path: str | Path) -> tuple[Path, str, SourceLocation]:
    location = SourceLocation(path=str(input_path))
    path = _readable_path(input_path, location, "manifest")
    if path.suffix.lower() not in {".yaml", ".yml", ".json"}:
        msg = f"unsupported manifest file type: {path.suffix or '(none)'}"
        raise ApplierValidationError(msg, source=location, category="source")
    try:
        return path, path.read_text(encoding="utf-8"), location
    except OSError as exc:
        msg = f"could not read manifest source {input_path}"
        raise ApplierValidationError(msg, source=location, category="source") from exc


def _render_manifest(
    text: str,
    *,
    context: Mapping[str, Any],
    environment: ImmutableSandboxedEnvironment,
    source: SourceLocation,
) -> str:
    try:
        return environment.from_string(text).render(context)
    except UndefinedError as exc:
        msg = f"template value is undefined: {exc}"
        raise ApplierValidationError(msg, source=source, category="template") from exc
    except Exception as exc:
        msg = f"template rendering failed: {exc}"
        raise ApplierValidationError(msg, source=source, category="template") from exc


def _read_manifest_file(
    input_path: str | Path,
    context: Mapping[str, Any],
    *,
    scope: ResourceScope,
    interface_resolver: DeviceInterfaceResolver | None,
) -> list[tuple[object, SourceLocation]]:
    path, text, location = _manifest_text(input_path)
    try:
        environment = create_environment(
            scope=scope,
            rio=context["rio"],
            interface_resolver=interface_resolver,
        )
    except Exception as exc:
        msg = f"template filter initialization failed: {exc}"
        raise ApplierValidationError(msg, source=location, category="template") from exc
    rendered = _render_manifest(
        text,
        context=context,
        environment=environment,
        source=location,
    )
    if path.suffix.lower() == ".json":
        raw_documents = [_parse_json(rendered, location, "manifest")]
    else:
        raw_documents = _parse_yaml_documents(rendered, location, "manifest")
    documents: list[tuple[object, SourceLocation]] = []
    for index, document in enumerate(raw_documents):
        if document is None:
            continue
        current = SourceLocation(path=str(input_path), document_index=index)
        _require_string_mapping(document, current, "manifest")
        documents.append((document, current))
    return documents


def _copy_resource_instances(
    resources: Sequence[SDKModel],
) -> list[tuple[object, SourceLocation]]:
    copied: list[tuple[object, SourceLocation]] = []
    for index, resource in enumerate(resources):
        location = SourceLocation(instance_index=index)
        if not isinstance(resource, SDKModel):
            msg = "resources must be SDK model instances"
            raise ApplierValidationError(
                msg,
                source=location,
                category="source",
            )
        copied.append((deepcopy(resource), location))
    return copied


def _validate_resource(document: object, source: SourceLocation) -> SDKModel:
    value, kind_value, model, is_model_instance = _resource_input(document, source)
    if not isinstance(kind_value, str) or not kind_value:
        msg = "manifest resource requires a supported kind"
        raise ApplierValidationError(
            msg,
            source=source,
            category="kind",
        )
    kind = kind_value.lower()
    if kind not in KIND_MODELS:
        msg = f"unsupported manifest kind: {kind_value}"
        raise ApplierValidationError(
            msg,
            source=source,
            category="kind",
        )
    if isinstance(document, SDKModel):
        # Instances already contain normalized values; revalidation can repeat
        # non-idempotent transformations such as Executable's Bash wrapping.
        return deepcopy(document)
    model = _creation_model(model, kind)
    canonical = deepcopy(dict(value))
    if not is_model_instance:
        canonical["kind"] = _CANONICAL_KINDS[kind]
    return _validate_model_payload(model, canonical, source)


def _resource_input(
    document: object, source: SourceLocation
) -> tuple[dict[str, Any], object, type[SDKModel], bool]:
    if isinstance(document, SDKModel):
        value = document.model_dump(exclude_unset=True, mode="python")
        return value, document.kind, type(document), True
    value = _require_string_mapping(document, source, "manifest")
    return value, value.get("kind"), SDKModel, False


def _creation_model(model: type[SDKModel], kind: str) -> type[SDKModel]:
    if model is not SDKModel:
        return model
    if kind == "secret":
        return SecretCreate
    if kind == "usergroup":
        return UserGroupCreate
    return KIND_MODELS[kind]


def _validate_model_payload(
    model: type[SDKModel], value: dict[str, Any], source: SourceLocation
) -> SDKModel:
    try:
        return deepcopy(model.model_validate(value))
    except ValidationError as exc:
        if model is SecretCreate:
            try:
                return deepcopy(Secret.model_validate(value))
            except ValidationError:
                pass
        raise ApplierValidationError(str(exc), source=source, category="model") from exc
    except (TypeError, ValueError) as exc:
        raise ApplierValidationError(str(exc), source=source, category="model") from exc


def _load_value_sources(
    sources: Sequence[object], *, purpose: str
) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for input_source in sources:
        if isinstance(input_source, Mapping):
            location = SourceLocation()
            mapping = _require_string_mapping(deepcopy(input_source), location, purpose)
        else:
            location = SourceLocation(path=str(input_source))
            mapping = _read_value_file(input_source, location, purpose)
        _validate_json_value(mapping, location, purpose)
        _merge_mapping(result, mapping)
    return result


def _read_value_file(
    input_source: object, source: SourceLocation, purpose: str
) -> dict[str, Any]:
    path = _readable_path(input_source, source, purpose)
    extension = path.suffix.lower()
    if extension not in {".yaml", ".yml", ".json"}:
        msg = f"unsupported {purpose} file type: {path.suffix or '(none)'}"
        raise ApplierValidationError(msg, source=source, category=purpose)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"could not read {purpose} source {input_source}"
        raise ApplierValidationError(msg, source=source, category=purpose) from exc
    value = _parse_value_text(text, extension, source=source, purpose=purpose)
    return _require_string_mapping(value, source, purpose)


def _parse_value_text(
    text: str,
    extension: str,
    *,
    source: SourceLocation,
    purpose: str,
) -> object:
    if extension == ".json":
        return _parse_json(text, source, purpose)
    documents = _parse_yaml_documents(text, source, purpose)
    if len(documents) != 1:
        msg = f"{purpose} source must contain exactly one mapping"
        raise ApplierValidationError(msg, source=source, category=purpose)
    return documents[0]


def _parse_json(text: str, source: SourceLocation, purpose: str) -> object:
    try:
        return json.loads(text, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        msg = f"invalid JSON {purpose} source: {exc}"
        raise ApplierValidationError(
            msg,
            source=source,
            category=purpose,
        ) from exc


def _parse_yaml_documents(
    text: str, source: SourceLocation, purpose: str
) -> list[object]:
    try:
        return list(yaml.safe_load_all(text))
    except yaml.YAMLError as exc:
        msg = f"invalid YAML {purpose} source: {exc}"
        raise ApplierValidationError(
            msg,
            source=source,
            category=purpose,
        ) from exc


def _require_string_mapping(
    value: object, source: SourceLocation, purpose: str
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        msg = f"{purpose} source must contain a string-keyed mapping"
        raise ApplierValidationError(
            msg,
            source=source,
            category=purpose,
        )
    return dict(value)


def _validate_json_value(value: object, source: SourceLocation, purpose: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    if isinstance(value, list):
        _validate_json_items(value, source, purpose)
        return
    if isinstance(value, Mapping):
        _validate_json_mapping(value, source, purpose)
        return
    msg = f"{purpose} source contains a non-JSON value"
    raise ApplierValidationError(
        msg,
        source=source,
        category=purpose,
    )


def _validate_json_items(
    values: Sequence[object], source: SourceLocation, purpose: str
) -> None:
    for item in values:
        _validate_json_value(item, source, purpose)


def _validate_json_mapping(
    value: Mapping[object, object], source: SourceLocation, purpose: str
) -> None:
    if not all(isinstance(key, str) for key in value):
        msg = f"{purpose} source contains a non-JSON value"
        raise ApplierValidationError(msg, source=source, category=purpose)
    for item in value.values():
        _validate_json_value(item, source, purpose)


def _merge_mapping(
    target: dict[str, JsonValue], source: Mapping[str, JsonValue]
) -> None:
    for key, value in source.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            _merge_mapping(current, value)
        else:
            target[key] = deepcopy(value)


def _readable_path(input_path: object, source: SourceLocation, purpose: str) -> Path:
    if not isinstance(input_path, (str, Path)):
        msg = f"{purpose} source must be a path or mapping"
        raise ApplierValidationError(
            msg,
            source=source,
            category=purpose,
        )
    path = Path(input_path)
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as exc:
        msg = f"{purpose} source path does not exist: {input_path}"
        raise ApplierValidationError(
            msg,
            source=source,
            category=purpose,
        ) from exc
    if not resolved.is_file() or not os_access_readable(resolved):
        msg = f"{purpose} source is not a readable regular file: {input_path}"
        raise ApplierValidationError(
            msg,
            source=source,
            category=purpose,
        )
    return resolved


def os_access_readable(path: Path) -> bool:
    """Return whether the file has a read permission bit and is readable."""
    return path.stat().st_mode & 0o444 != 0


def _document_data(document: object) -> dict[str, Any]:
    if isinstance(document, SDKModel):
        return document.model_dump(exclude_unset=True, mode="python")
    return deepcopy(dict(document)) if isinstance(document, Mapping) else {}


def _source_for_identity(
    resources: Sequence[PreparedResource], identities: Sequence[ResourceIdentity]
) -> SourceLocation | None:
    if not identities:
        return None
    target = identities[0]
    for resource in resources:
        if resource.identity.model_copy(update={"scope": target.scope}) == target:
            return resource.source
    return resources[0].source if resources else None


def _reject_json_constant(value: str) -> None:
    msg = f"invalid JSON number {value}"
    raise ValueError(msg)


def _resource_kind(resource: SDKModel, source: SourceLocation) -> str:
    value = cast("Any", resource).kind
    if not isinstance(value, str) or not value:
        msg = "resource model is missing its kind"
        raise ApplierValidationError(
            msg,
            source=source,
            category="kind",
        )
    kind = value.lower()
    if kind not in KIND_MODELS:
        msg = f"unsupported resource kind: {value}"
        raise ApplierValidationError(
            msg,
            source=source,
            category="kind",
        )
    return kind


def _rolebinding_identity(
    resource: SDKModel, source: SourceLocation
) -> dict[str, ResourceReference]:
    spec = cast("Any", resource).spec
    if spec is None:
        msg = "RoleBinding spec is required for identity"
        raise ApplierValidationError(
            msg,
            source=source,
            category="identity",
        )
    role_ref = spec.role_ref
    subject = spec.subject
    domain = spec.domain
    if subject.kind is None:
        msg = "RoleBinding subject kind is required for identity"
        raise ApplierValidationError(msg, source=source, category="identity")
    if domain.kind is None:
        msg = "RoleBinding domain kind is required for identity"
        raise ApplierValidationError(msg, source=source, category="identity")
    return {
        "role": ResourceReference(kind="role", name=role_ref.name, guid=role_ref.guid),
        "subject": ResourceReference(
            kind=(subject.kind or "").lower(),
            name=subject.name,
            guid=subject.guid,
        ),
        "domain": ResourceReference(
            kind=(domain.kind or "").lower(),
            name=domain.name,
            guid=domain.guid,
        ),
    }


__all__ = [
    "KIND_MODELS",
    "PreparedCollection",
    "PreparedResource",
    "prepare_source",
    "resource_identity",
]
