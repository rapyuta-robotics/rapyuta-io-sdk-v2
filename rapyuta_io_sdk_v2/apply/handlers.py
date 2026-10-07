"""Resource operations shared by synchronous and asynchronous executors.

Handlers yield API requests, so both executors follow the same resource policy
while async execution always uses the asynchronous client and sleeps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from rapyuta_io_sdk_v2.exceptions import HttpAlreadyExistsError, HttpNotFoundError
from rapyuta_io_sdk_v2.models import (
    Deployment,
    Disk,
    Network,
    Organization,
    Package,
    Project,
    Role,
    RoleBinding,
    SecretCreate,
    ServiceAccount,
    StaticRoute,
    UserGroupCreate,
)
from rapyuta_io_sdk_v2.models.rolebinding import BulkRoleBindingUpdate
from rapyuta_io_sdk_v2.models.utils import resource_key

from .types import ApplyError, Outcome, ReadinessError


@dataclass
class Request:
    method: str
    args: tuple = ()
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Pause:
    seconds: float


def resource_kind(
    resource: BaseModel, handlers: dict[str, type[ResourceHandler]] | None = None
) -> str:
    """Infer an omitted kind from registered typed models without modifying them."""
    if getattr(resource, "kind", None):
        return resource.kind
    registry = DEFAULT_HANDLERS if handlers is None else handlers
    exact = [
        name for name, handler in registry.items() if type(resource) is handler.model
    ]
    candidates = exact or [
        name for name, handler in registry.items() if isinstance(resource, handler.model)
    ]
    if len(candidates) != 1:
        raise ApplyError(f"Cannot infer resource kind for {type(resource).__name__}")
    name = candidates[0]
    model_name = registry[name].model.__name__.removesuffix("Create")
    return model_name if model_name.lower() == name else name


def identity(resource: BaseModel) -> str:
    kind = resource_kind(resource).lower()
    metadata = resource.metadata
    if kind == "rolebinding":
        spec = resource.spec
        references = [spec.role_ref, spec.domain, spec.subject]
        # Include kind and name/GUID to avoid unrelated bindings colliding.
        parts = [f"{r.kind}:{r.guid or r.name}" for r in references]
        return "rolebinding:" + ":".join(parts)
    if metadata is None or not metadata.name:
        raise ApplyError("A resource must have a nonempty metadata.name")
    if kind == "package":
        return resource_key(kind, metadata.name, metadata.version)
    return resource_key(kind, metadata.name)


def _permission_denied(error: Exception) -> bool:
    # Authentication errors must never trigger an update or become EXISTS.
    return getattr(error, "status_code", None) == 403


class ResourceHandler[T: BaseModel]:
    """Operational base model: identity, capabilities, dependencies and workflow.

    Subclasses may override dependencies() and workflow() and be registered
    through Applier(handlers={"MyKind": MyHandler}). The workflow yields
    Request/Pause values and returns an (Outcome, response) tuple.
    """

    model: type[T]
    endpoint: str
    mutable = False
    can_delete = True

    def __init__(self, resource: T):
        self.resource = resource
        self.identity = identity(resource)

    def dependencies(self) -> list[str]:
        loader = getattr(self.resource, "list_dependencies", None)
        dependencies = list(loader() or []) if loader else []
        spec = getattr(self.resource, "spec", None)
        environment = (
            getattr(spec, "environment_vars", None)
            or getattr(spec, "env_args", None)
            or []
        )
        for variable in environment:
            reference = getattr(
                getattr(variable, "value_from", None), "secret_key_ref", None
            )
            if reference and reference.name:
                dependencies.append(resource_key("Secret", reference.name))
        service_account = getattr(spec, "service_account", None)
        if service_account:
            dependencies.append(resource_key("ServiceAccount", service_account))
        for binding in (getattr(spec, "roles", None) or []) + (
            getattr(spec, "members", None) or []
        ):
            for reference in (
                getattr(binding, "domain", None),
                getattr(binding, "subject", None),
            ):
                if reference and reference.kind and reference.name:
                    dependencies.append(resource_key(reference.kind, reference.name))
            for name in getattr(binding, "role_names", None) or []:
                dependencies.append(resource_key("Role", name))
            if getattr(binding, "role_name", None):
                dependencies.append(resource_key("Role", binding.role_name))
        return list(dict.fromkeys(dependencies))

    def validate_operation(self, operation: str) -> None:
        if operation == "delete" and not self.can_delete:
            raise ApplyError(f"{self.identity} does not support deletion")

    def named_resources(self, method: str):
        """Find all exact name matches, following a filtered list's cursor."""
        matches = []
        seen = set()
        kwargs = {"name": self.resource.metadata.name}
        while True:
            page = yield Request(method, kwargs=kwargs)
            matches.extend(
                r for r in page.items if r.metadata.name == self.resource.metadata.name
            )
            cursor = getattr(getattr(page, "metadata", None), "continue_", None)
            if cursor is None or not page.items or len(page.items) < 50:
                return matches
            if cursor in seen:
                raise ApplyError(
                    f"Repeated continuation token while resolving {self.identity}"
                )
            seen.add(cursor)
            kwargs = {"name": self.resource.metadata.name, "cont": cursor}

    def create(self):
        return (yield Request(f"create_{self.endpoint}", (self.resource,)))

    def update(self):
        return (yield Request(f"update_{self.endpoint}", (self.resource,)))

    def delete(self):
        yield Request(f"delete_{self.endpoint}", (self.resource.metadata.name,))

    def wait(self, attempts: int, interval: float):
        # Ordinary resource creation is complete when the direct API returns.
        if False:
            yield

    def prerequisites(self, attempts: int, interval: float):
        if False:
            yield

    def workflow(self, operation: str, attempts: int, interval: float):
        if operation == "delete":
            labels = self.resource.metadata.labels or {}
            if labels.get("rapyuta.io/deletionPolicy") == "retain":
                return Outcome.RETAINED, None
            try:
                yield from self.delete()
            except HttpNotFoundError:
                return Outcome.NOT_FOUND, None
            return Outcome.DELETED, None
        yield from self.prerequisites(attempts, interval)
        try:
            response = yield from self.create()
            result = Outcome.CREATED
        except Exception as error:
            conflict = isinstance(error, HttpAlreadyExistsError)
            if not conflict and not (_permission_denied(error) and self.mutable):
                raise
            if not self.mutable:
                return Outcome.EXISTS, None
            response = yield from self.update()
            result = Outcome.UPDATED
        yield from self.wait(attempts, interval)
        return result, response


class OrganizationHandler(ResourceHandler[Organization]):
    model = Organization
    endpoint = "organization"
    can_delete = False

    def validate_operation(self, operation: str) -> None:
        super().validate_operation(operation)
        if not self.resource.metadata.guid:
            raise ApplyError("Organization apply requires metadata.guid")

    def workflow(self, operation: str, attempts: int, interval: float):
        response = yield Request(
            "update_organization",
            (self.resource,),
            {"organization_guid": self.resource.metadata.guid},
        )
        return Outcome.UPDATED, response


class ProjectHandler(ResourceHandler[Project]):
    model = Project
    endpoint = "project"
    mutable = True

    def dependencies(self) -> list[str]:
        cache = self.resource.spec.features.docker_cache
        return (
            [f"secret:{cache.registry_secret}"]
            if cache.enabled and cache.registry_secret
            else []
        )

    def lookup(self):
        if self.resource.metadata.guid:
            return self.resource.metadata.guid
        matches = yield from self.named_resources("list_projects")
        if not matches or not matches[0].metadata.guid:
            raise HttpNotFoundError(f"Project {self.resource.metadata.name} not found")
        if len(matches) != 1:
            raise ApplyError(f"Ambiguous project name {self.resource.metadata.name}")
        return matches[0].metadata.guid

    def update(self):
        guid = yield from self.lookup()
        return (yield Request("update_project", (self.resource,), {"project_guid": guid}))

    def delete(self):
        guid = yield from self.lookup()
        yield Request("delete_project", (guid,))

    def create(self):
        if not self.resource.spec.features.docker_cache.enabled:
            return (yield Request("create_project", (self.resource,)))
        # DockerCache is supported only by the update endpoint.
        try:
            yield from self.lookup()
        except HttpNotFoundError:
            initial = self.resource.model_copy(deep=True)
            initial.spec.features.docker_cache.enabled = False
            for name in type(initial.spec.features.docker_cache).model_fields:
                if name != "enabled":
                    setattr(initial.spec.features.docker_cache, name, None)
            created = yield Request("create_project", (initial,))
            self.resource.metadata.guid = created.metadata.guid
        # Report UPDATED, even when an initial shell project was necessary.
        raise HttpAlreadyExistsError("Project requires update for DockerCache")

    def wait(self, attempts: int, interval: float):
        for attempt in range(attempts):
            page = yield Request(
                "list_projects", kwargs={"name": self.resource.metadata.name}
            )
            matches = [
                r for r in page.items if r.metadata.name == self.resource.metadata.name
            ]
            status = getattr(matches[0], "status", None) if matches else None
            state = getattr(status, "status", None)
            if state == "Success":
                return
            if state in ("Error", "Deleting"):
                raise ReadinessError(f"{self.identity} entered {state}")
            if attempt + 1 < attempts:
                yield Pause(interval)
        raise ReadinessError(f"{self.identity} readiness timed out")


class PackageHandler(ResourceHandler[Package]):
    model = Package
    endpoint = "package"

    def delete(self):
        yield Request(
            "delete_package",
            (self.resource.metadata.name, self.resource.metadata.version),
        )


class DeploymentHandler(ResourceHandler[Deployment]):
    model = Deployment
    endpoint = "deployment"

    def dependencies(self) -> list[str]:
        dependencies = super().dependencies()
        package = self.resource.metadata.depends
        if package:
            dependencies = [
                d for d in dependencies if d != f"package:{package.name_or_guid}"
            ]
            key = resource_key("Package", package.name_or_guid, package.version)
            if key not in dependencies:
                dependencies.append(key)
        return dependencies

    def prerequisites(self, attempts: int, interval: float):
        required = {d.name_or_guid for d in (self.resource.spec.depends or []) if d.wait}
        if not required:
            return
        for attempt in range(attempts):
            # Get each named dependency; an empty list response cannot pass.
            ready = True
            for name in sorted(required):
                try:
                    deployment = yield Request("get_deployment", (name,))
                except HttpNotFoundError:
                    ready = False
                    continue
                state = getattr(deployment.status, "status", None)
                phase = getattr(deployment.status, "phase", None)
                if state in ("Error", "Stopped") or phase in ("FailedToStart", "Stopped"):
                    raise ReadinessError(f"Dependency deployment:{name} failed")
                ready &= state == "Running"
            if ready:
                return
            if attempt + 1 < attempts:
                yield Pause(interval)
        raise ReadinessError(f"Dependencies did not become ready: {sorted(required)}")


class DiskHandler(ResourceHandler[Disk]):
    model = Disk
    endpoint = "disk"

    def wait(self, attempts: int, interval: float):
        for attempt in range(attempts):
            resource = yield Request(
                f"get_{self.endpoint}", (self.resource.metadata.name,)
            )
            status = getattr(resource.status, "status", None)
            if status in ("Available", "Released", "Bound"):
                return
            if status == "Failed":
                raise ReadinessError(f"{self.identity} failed")
            if attempt + 1 < attempts:
                yield Pause(interval)
        raise ReadinessError(f"{self.identity} readiness timed out")


class NetworkHandler(ResourceHandler[Network]):
    model = Network
    endpoint = "network"

    def wait(self, attempts: int, interval: float):
        for attempt in range(attempts):
            resource = yield Request("get_network", (self.resource.metadata.name,))
            phase = getattr(resource.status, "phase", None)
            if phase == "Succeeded":
                return
            if phase in ("Stopped", "FailedToStart", "FailedToUpdate"):
                raise ReadinessError(f"{self.identity} entered {phase}")
            if attempt + 1 < attempts:
                yield Pause(interval)
        raise ReadinessError(f"{self.identity} readiness timed out")


class StaticRouteHandler(ResourceHandler[StaticRoute]):
    model = StaticRoute
    endpoint = "staticroute"
    mutable = True

    def update(self):
        return (
            yield Request(
                "update_staticroute", (self.resource.metadata.name, self.resource)
            )
        )


class SecretHandler(ResourceHandler[SecretCreate]):
    model = SecretCreate
    endpoint = "secret"
    mutable = True

    def update(self):
        return (
            yield Request("update_secret", (self.resource.metadata.name, self.resource))
        )


class UserGroupHandler(ResourceHandler[UserGroupCreate]):
    model = UserGroupCreate
    endpoint = "user_group"
    mutable = True

    def lookup(self):
        if self.resource.metadata.guid:
            return self.resource.metadata.guid
        matches = yield from self.named_resources("list_user_groups")
        if not matches or not matches[0].metadata.guid:
            raise HttpNotFoundError(f"Group {self.resource.metadata.name} not found")
        if len(matches) != 1:
            raise ApplyError(f"Ambiguous group name {self.resource.metadata.name}")
        return matches[0].metadata.guid

    def update(self):
        self.resource.metadata.guid = yield from self.lookup()
        return (
            yield Request(
                "update_user_group",
                (
                    self.resource.metadata.name,
                    self.resource.metadata.guid,
                    self.resource,
                ),
            )
        )

    def delete(self):
        guid = yield from self.lookup()
        yield Request("delete_user_group", (self.resource.metadata.name, guid))


class RoleHandler(ResourceHandler[Role]):
    model = Role
    endpoint = "role"
    mutable = True

    def update(self):
        return (
            yield Request("update_role", (self.resource.metadata.name, self.resource))
        )


class RoleBindingHandler(ResourceHandler[RoleBinding]):
    model = RoleBinding
    endpoint = "role_binding"

    def create(self):
        body = BulkRoleBindingUpdate.model_validate(
            {"newBindings": [self.resource], "oldBindings": []}
        )
        return (yield Request("update_role_binding", (body,)))

    def delete(self):
        body = BulkRoleBindingUpdate.model_validate(
            {"newBindings": [], "oldBindings": [self.resource]}
        )
        yield Request("update_role_binding", (body,))


class ServiceAccountHandler(ResourceHandler[ServiceAccount]):
    model = ServiceAccount
    endpoint = "service_account"
    mutable = True

    def update(self):
        return (
            yield Request(
                "update_service_account", (self.resource, self.resource.metadata.name)
            )
        )


DEFAULT_HANDLERS = {
    cls.model.__name__.removesuffix("Create").lower(): cls
    for cls in (
        OrganizationHandler,
        ProjectHandler,
        PackageHandler,
        DeploymentHandler,
        DiskHandler,
        NetworkHandler,
        StaticRouteHandler,
        SecretHandler,
        UserGroupHandler,
        RoleHandler,
        RoleBindingHandler,
        ServiceAccountHandler,
    )
}
