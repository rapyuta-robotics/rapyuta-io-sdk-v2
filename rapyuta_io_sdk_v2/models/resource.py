"""Resource workflows independent of template rendering and optional packages."""

from __future__ import annotations

import asyncio
import math
import time
from typing import Any, ClassVar

from rapyuta_io_sdk_v2.context import RequestContext
from rapyuta_io_sdk_v2.exceptions import HttpAlreadyExistsError, HttpNotFoundError
from rapyuta_io_sdk_v2.resource_operations import (
    ApplyError,
    Outcome,
    Pause,
    Request,
    ResourceResult,
)

from .base import SDKModel


def _permission_denied(error: Exception) -> bool:
    return getattr(error, "status_code", None) == 403


class ResourceModel(SDKModel):
    """Validated resource with shared sync and async operational execution.

    Concrete models define API policy through workflow hooks. Clients and
    execution state are never stored in Pydantic fields.
    """

    resource_kind: ClassVar[str | None] = None
    endpoint: ClassVar[str | None] = None
    mutable: ClassVar[bool] = False
    can_apply: ClassVar[bool] = True
    can_delete: ClassVar[bool] = True

    @property
    def identity(self) -> str:
        from .utils import resource_key

        kind = getattr(self, "kind", None) or self.resource_kind
        if not kind:
            raise ApplyError(f"Cannot infer resource kind for {type(self).__name__}")
        kind = kind.lower()
        metadata = getattr(self, "metadata", None)
        if kind == "rolebinding":
            references = [self.spec.role_ref, self.spec.domain, self.spec.subject]
            return "rolebinding:" + ":".join(
                f"{r.kind}:{r.guid or r.name}" for r in references
            )
        if metadata is None or not metadata.name:
            raise ApplyError("A resource must have a nonempty metadata.name")
        if kind == "package":
            return resource_key(kind, metadata.name, metadata.version)
        return resource_key(kind, metadata.name)

    def validate_operation(self, operation: str) -> None:
        if operation not in ("apply", "delete"):
            raise ApplyError(f"Unsupported resource operation: {operation}")
        if self.endpoint is None:
            raise ApplyError(
                f"{type(self).__name__} does not support resource operations"
            )
        if operation == "apply" and not self.can_apply:
            raise ApplyError(f"{type(self).__name__} requires its Create model for apply")
        if operation == "delete" and not self.can_delete:
            raise ApplyError(f"{self.identity} does not support deletion")

    def dependencies(self) -> list[str]:
        from .utils import resource_key

        loader = getattr(self, "list_dependencies", None)
        dependencies = list(loader() or []) if loader else []
        spec = getattr(self, "spec", None)
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

    def _named_resources(self, method: str):
        """Find all exact name matches, following a filtered list's cursor."""
        matches = []
        seen = set()
        kwargs = {"name": self.metadata.name}
        while True:
            page = yield Request(method, kwargs=kwargs)
            matches.extend(r for r in page.items if r.metadata.name == self.metadata.name)
            cursor = getattr(getattr(page, "metadata", None), "continue_", None)
            if cursor is None or not page.items or len(page.items) < 50:
                return matches
            if cursor in seen:
                raise ApplyError(
                    f"Repeated continuation token while resolving {self.identity}"
                )
            seen.add(cursor)
            kwargs = {"name": self.metadata.name, "cont": cursor}

    def _create(self):
        return (yield Request(f"create_{self.endpoint}", (self,)))

    def _update(self):
        return (yield Request(f"update_{self.endpoint}", (self,)))

    def _delete(self):
        yield Request(f"delete_{self.endpoint}", (self.metadata.name,))

    def _wait(self, attempts: int, interval: float):
        # Ordinary resource creation is complete when the direct API returns.
        if False:
            yield

    def _prerequisites(self, attempts: int, interval: float):
        if False:
            yield

    def workflow(self, operation: str, attempts: int, interval: float):
        if operation == "delete":
            labels = self.metadata.labels or {}
            if labels.get("rapyuta.io/deletionPolicy") == "retain":
                return Outcome.RETAINED, None
            try:
                yield from self._delete()
            except HttpNotFoundError:
                return Outcome.NOT_FOUND, None
            return Outcome.DELETED, None
        yield from self._prerequisites(attempts, interval)
        try:
            response = yield from self._create()
            result = Outcome.CREATED
        except Exception as error:
            conflict = isinstance(error, HttpAlreadyExistsError)
            if not conflict and not (_permission_denied(error) and self.mutable):
                raise
            if not self.mutable:
                return Outcome.EXISTS, None
            response = yield from self._update()
            result = Outcome.UPDATED
        yield from self._wait(attempts, interval)
        return result, response

    def _prepare_operation(
        self,
        client: Any,
        operation: str,
        context: RequestContext | None,
        attempts: int,
        interval: float,
    ):
        client.config.features.require("apply")
        self.validate_operation(operation)
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
            raise ValueError("readiness_attempts must be a positive integer")
        if (
            isinstance(interval, bool)
            or not isinstance(interval, (int, float))
            or not math.isfinite(interval)
            or interval < 0
        ):
            raise ValueError("readiness_interval must be a finite nonnegative number")
        if context is not None and not isinstance(context, RequestContext):
            raise TypeError("context must be a RequestContext")
        identity = self.identity
        resource = self.model_copy(deep=True)
        return identity, resource.workflow(operation, attempts, interval)

    def _execute_operation(
        self,
        client: Any,
        operation: str,
        *,
        context: RequestContext | None,
        readiness_attempts: int,
        readiness_interval: float,
    ) -> ResourceResult:
        identity, workflow = self._prepare_operation(
            client, operation, context, readiness_attempts, readiness_interval
        )
        value, error = None, None
        try:
            while True:
                try:
                    step = (
                        workflow.throw(error)
                        if error is not None
                        else workflow.send(value)
                    )
                except StopIteration as completed:
                    outcome, resource = completed.value
                    return ResourceResult(
                        identity=identity, outcome=outcome, resource=resource
                    )
                value, error = None, None
                try:
                    if isinstance(step, Pause):
                        time.sleep(step.seconds)
                    elif isinstance(step, Request):
                        kwargs = dict(step.kwargs)
                        if context is not None:
                            kwargs["context"] = context
                        value = getattr(client, step.method)(*step.args, **kwargs)
                    else:
                        raise ApplyError(f"Invalid resource workflow step: {step}")
                except Exception as caught:
                    error = caught
        except Exception as caught:
            return ResourceResult(
                identity=identity, outcome=Outcome.FAILED, error=str(caught)
            )
        finally:
            workflow.close()

    async def _execute_operation_async(
        self,
        client: Any,
        operation: str,
        *,
        context: RequestContext | None,
        readiness_attempts: int,
        readiness_interval: float,
    ) -> ResourceResult:
        identity, workflow = self._prepare_operation(
            client, operation, context, readiness_attempts, readiness_interval
        )
        value, error = None, None
        try:
            while True:
                try:
                    step = (
                        workflow.throw(error)
                        if error is not None
                        else workflow.send(value)
                    )
                except StopIteration as completed:
                    outcome, resource = completed.value
                    return ResourceResult(
                        identity=identity, outcome=outcome, resource=resource
                    )
                value, error = None, None
                try:
                    if isinstance(step, Pause):
                        await asyncio.sleep(step.seconds)
                    elif isinstance(step, Request):
                        kwargs = dict(step.kwargs)
                        if context is not None:
                            kwargs["context"] = context
                        value = await getattr(client, step.method)(*step.args, **kwargs)
                    else:
                        raise ApplyError(f"Invalid resource workflow step: {step}")
                except Exception as caught:
                    error = caught
        except Exception as caught:
            return ResourceResult(
                identity=identity, outcome=Outcome.FAILED, error=str(caught)
            )
        finally:
            workflow.close()

    def apply(
        self,
        client: Any,
        *,
        context: RequestContext | None = None,
        readiness_attempts: int = 50,
        readiness_interval: float = 6,
    ) -> ResourceResult:
        """Apply this rendered resource without changing the input model."""
        return self._execute_operation(
            client,
            "apply",
            context=context,
            readiness_attempts=readiness_attempts,
            readiness_interval=readiness_interval,
        )

    async def apply_async(
        self,
        client: Any,
        *,
        context: RequestContext | None = None,
        readiness_attempts: int = 50,
        readiness_interval: float = 6,
    ) -> ResourceResult:
        """Apply using only the supplied asynchronous client."""
        return await self._execute_operation_async(
            client,
            "apply",
            context=context,
            readiness_attempts=readiness_attempts,
            readiness_interval=readiness_interval,
        )

    def delete(
        self,
        client: Any,
        *,
        context: RequestContext | None = None,
        readiness_attempts: int = 50,
        readiness_interval: float = 6,
    ) -> ResourceResult:
        """Delete this resource, respecting the retain label."""
        return self._execute_operation(
            client,
            "delete",
            context=context,
            readiness_attempts=readiness_attempts,
            readiness_interval=readiness_interval,
        )

    async def delete_async(
        self,
        client: Any,
        *,
        context: RequestContext | None = None,
        readiness_attempts: int = 50,
        readiness_interval: float = 6,
    ) -> ResourceResult:
        """Delete using only the supplied asynchronous client."""
        return await self._execute_operation_async(
            client,
            "delete",
            context=context,
            readiness_attempts=readiness_attempts,
            readiness_interval=readiness_interval,
        )
