"""Resource operations independent of manifest rendering and optional packages."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, ClassVar, Self

from pydantic import BaseModel

from rapyuta_io_sdk_v2.context import RequestContext
from rapyuta_io_sdk_v2.exceptions import (
    HttpAlreadyExistsError,
    HttpNotFoundError,
    SDKError,
)
from rapyuta_io_sdk_v2.resource_operations import ApplyError, Outcome, ResourceResult
from .base import SDKModel

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.config import Configuration
    from .utils import BaseMetadata


class ResourceModel(SDKModel):
    """Shared apply/delete policy; concrete resources make explicit API calls."""

    resource_kind: ClassVar[str | None] = None
    mutable: ClassVar[bool] = False
    can_apply: ClassVar[bool] = True
    can_delete: ClassVar[bool] = True

    if TYPE_CHECKING:
        metadata: BaseMetadata
        kind: str | None

    @property
    def identity(self) -> str:
        if not self.resource_kind:
            raise ApplyError(
                f"{type(self).__name__} does not support resource operations"
            )
        if not self.metadata.name:
            raise ApplyError("A resource must have a nonempty metadata.name")
        return f"{self.resource_kind.lower()}:{self.metadata.name}"

    def reference_keys(self) -> list[str]:
        """Names and GUIDs that resolve to this manifest resource."""
        keys = [self.identity]
        if self.metadata.guid:
            keys.append(f"{self.resource_kind.lower()}:{self.metadata.guid}")
        return list(dict.fromkeys(keys))

    @classmethod
    def model_for_operation(cls, operation: str) -> type[ResourceModel]:
        return cls

    def bind_context(self, config: Configuration, context: RequestContext | None) -> None:
        """Bind resource-specific context on the executor's private model copy."""
        if self.resource_kind and self.kind is None:
            self.kind = self.resource_kind

    def validate_operation(self, operation: str) -> None:
        if operation not in ("apply", "delete"):
            raise ApplyError(f"Unsupported resource operation: {operation}")
        if self.resource_kind is None:
            raise ApplyError(
                f"{type(self).__name__} does not support resource operations"
            )
        if operation == "apply" and not self.can_apply:
            raise ApplyError(f"{type(self).__name__} requires its Create model for apply")
        if operation == "delete" and not self.can_delete:
            raise ApplyError(f"{self.identity} does not support deletion")

    def dependencies(self) -> list[str]:
        return []

    def create(
        self, client: Client, *, context: RequestContext | None = None
    ) -> BaseModel:
        raise ApplyError(f"{self.identity} does not support creation")

    async def create_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ) -> BaseModel:
        raise ApplyError(f"{self.identity} does not support creation")

    def update(
        self, client: Client, *, context: RequestContext | None = None
    ) -> BaseModel:
        raise ApplyError(f"{self.identity} does not support updates")

    async def update_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ) -> BaseModel:
        raise ApplyError(f"{self.identity} does not support updates")

    def _delete(self, client: Client, *, context: RequestContext | None = None) -> None:
        raise ApplyError(f"{self.identity} does not support deletion")

    async def _delete_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ) -> None:
        raise ApplyError(f"{self.identity} does not support deletion")

    def wait(
        self,
        client: Client,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None = None,
    ) -> None:
        """Most resources are ready when their API call returns."""

    async def wait_async(
        self,
        client: AsyncClient,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None = None,
    ) -> None:
        """Most resources are ready when their API call returns."""

    def prerequisites(
        self,
        client: Client,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None = None,
    ) -> None:
        """Wait for resource-specific prerequisites, when any are required."""

    async def prerequisites_async(
        self,
        client: AsyncClient,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None = None,
    ) -> None:
        """Wait for resource-specific prerequisites, when any are required."""

    def _apply(
        self,
        client: Client,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None,
    ) -> tuple[Outcome, BaseModel | None]:
        self.prerequisites(client, attempts, interval, context=context)
        try:
            response = self.create(client, context=context)
            outcome = Outcome.CREATED
        except SDKError as error:
            if not isinstance(error, HttpAlreadyExistsError) and not (
                self.mutable and error.status_code == 403
            ):
                raise
            if not self.mutable:
                return Outcome.EXISTS, None
            response = self.update(client, context=context)
            outcome = Outcome.UPDATED
        self.wait(client, attempts, interval, context=context)
        return outcome, response

    async def _apply_async(
        self,
        client: AsyncClient,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None,
    ) -> tuple[Outcome, BaseModel | None]:
        await self.prerequisites_async(client, attempts, interval, context=context)
        try:
            response = await self.create_async(client, context=context)
            outcome = Outcome.CREATED
        except SDKError as error:
            if not isinstance(error, HttpAlreadyExistsError) and not (
                self.mutable and error.status_code == 403
            ):
                raise
            if not self.mutable:
                return Outcome.EXISTS, None
            response = await self.update_async(client, context=context)
            outcome = Outcome.UPDATED
        await self.wait_async(client, attempts, interval, context=context)
        return outcome, response

    def _prepare_operation(
        self,
        client: Client | AsyncClient,
        operation: str,
        context: RequestContext | None,
        attempts: int,
        interval: float,
    ) -> Self:
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
        _ = self.identity
        resource = self.model_copy(deep=True)
        resource.bind_context(client.config, context)
        return resource

    def apply(
        self,
        client: Client,
        *,
        context: RequestContext | None = None,
        readiness_attempts: int = 50,
        readiness_interval: float = 6,
    ) -> ResourceResult:
        """Create or update this resource without changing the input model."""
        resource = self._prepare_operation(
            client, "apply", context, readiness_attempts, readiness_interval
        )
        try:
            outcome, response = resource._apply(
                client, readiness_attempts, readiness_interval, context=context
            )
            return ResourceResult(
                identity=self.identity, outcome=outcome, resource=response
            )
        except Exception as error:
            return ResourceResult(
                identity=self.identity, outcome=Outcome.FAILED, error=str(error)
            )

    async def apply_async(
        self,
        client: AsyncClient,
        *,
        context: RequestContext | None = None,
        readiness_attempts: int = 50,
        readiness_interval: float = 6,
    ) -> ResourceResult:
        """Apply through explicit asynchronous model methods."""
        resource = self._prepare_operation(
            client, "apply", context, readiness_attempts, readiness_interval
        )
        try:
            outcome, response = await resource._apply_async(
                client, readiness_attempts, readiness_interval, context=context
            )
            return ResourceResult(
                identity=self.identity, outcome=outcome, resource=response
            )
        except Exception as error:
            return ResourceResult(
                identity=self.identity, outcome=Outcome.FAILED, error=str(error)
            )

    def delete(
        self,
        client: Client,
        *,
        context: RequestContext | None = None,
        readiness_attempts: int = 50,
        readiness_interval: float = 6,
    ) -> ResourceResult:
        """Delete this resource, respecting the retain label."""
        resource = self._prepare_operation(
            client, "delete", context, readiness_attempts, readiness_interval
        )
        if (resource.metadata.labels or {}).get("rapyuta.io/deletionPolicy") == "retain":
            return ResourceResult(identity=self.identity, outcome=Outcome.RETAINED)
        try:
            resource._delete(client, context=context)
            return ResourceResult(identity=self.identity, outcome=Outcome.DELETED)
        except HttpNotFoundError:
            return ResourceResult(identity=self.identity, outcome=Outcome.NOT_FOUND)
        except Exception as error:
            return ResourceResult(
                identity=self.identity, outcome=Outcome.FAILED, error=str(error)
            )

    async def delete_async(
        self,
        client: AsyncClient,
        *,
        context: RequestContext | None = None,
        readiness_attempts: int = 50,
        readiness_interval: float = 6,
    ) -> ResourceResult:
        """Delete through explicit asynchronous model methods."""
        resource = self._prepare_operation(
            client, "delete", context, readiness_attempts, readiness_interval
        )
        if (resource.metadata.labels or {}).get("rapyuta.io/deletionPolicy") == "retain":
            return ResourceResult(identity=self.identity, outcome=Outcome.RETAINED)
        try:
            await resource._delete_async(client, context=context)
            return ResourceResult(identity=self.identity, outcome=Outcome.DELETED)
        except HttpNotFoundError:
            return ResourceResult(identity=self.identity, outcome=Outcome.NOT_FOUND)
        except Exception as error:
            return ResourceResult(
                identity=self.identity, outcome=Outcome.FAILED, error=str(error)
            )
