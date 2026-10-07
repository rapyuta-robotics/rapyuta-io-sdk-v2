"""Render, validate, order and execute declarative resource manifests."""

from __future__ import annotations

import asyncio
import glob
import graphlib
import json
import math
import os
from collections.abc import Callable, Iterable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from rapyuta_io_sdk_v2.context import RequestContext
from rapyuta_io_sdk_v2.features import require_dependency
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
from rapyuta_io_sdk_v2.models.resource import ResourceModel

from .types import ApplyError, ApplyPlan, ApplyReport, Outcome, ResourceResult


DEFAULT_RESOURCE_MODELS: dict[str, type[ResourceModel]] = {
    model.resource_kind.lower(): model
    for model in (
        Organization,
        Project,
        Package,
        Deployment,
        Disk,
        Network,
        StaticRoute,
        SecretCreate,
        UserGroupCreate,
        Role,
        RoleBinding,
        ServiceAccount,
    )
}


def merge_values(destination: dict, source: Mapping) -> dict:
    """Recursively merge mappings; later scalars and sequences replace earlier ones."""
    for key, value in source.items():
        if isinstance(value, Mapping) and isinstance(destination.get(key), dict):
            merge_values(destination[key], value)
        else:
            destination[key] = deepcopy(value)
    return destination


def template_getenv(default: str, name: str) -> str:
    """CLI-compatible filter: {{ 'fallback' | getenv('VARIABLE') }}."""
    return os.getenv(name, default)


class _BaseApplier:
    def __init__(
        self,
        client: Any,
        resources: Any = (),
        *,
        values: Mapping | Iterable[Mapping | str | Path] = (),
        secrets: Mapping | None = None,
        filters: Mapping[str, Callable] | None = None,
        workers: int = 6,
        readiness_attempts: int = 50,
        readiness_interval: float = 6,
        context: RequestContext | None = None,
        resource_models: Mapping[str, type[ResourceModel]] | None = None,
    ):
        client.config.features.require("apply")
        self._validate_execution_options(
            workers, readiness_attempts, readiness_interval, context
        )
        self.client = client
        # Plans and execution must see the same inputs, even with a generator.
        self.resources = (
            tuple(resources) if isinstance(resources, Iterator) else resources
        )
        self.workers = workers
        self.readiness_attempts = readiness_attempts
        self.readiness_interval = readiness_interval
        self.context = context
        self.resource_models = self._build_registry(resource_models)
        self.yaml = require_dependency("yaml", "apply")
        self.environment = self._template_environment(filters)
        self.values = self._load_values(values)
        self._add_rio_context()
        self._add_secrets(secrets)

    @staticmethod
    def _validate_execution_options(workers, attempts, interval, context) -> None:
        if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
            raise ValueError("workers must be a positive integer")
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

    @staticmethod
    def _build_registry(overrides) -> dict[str, type[ResourceModel]]:
        registry = dict(DEFAULT_RESOURCE_MODELS)
        for kind, model in (overrides or {}).items():
            if not isinstance(model, type) or not issubclass(model, ResourceModel):
                raise TypeError("resource_models values must be ResourceModel subclasses")
            if (
                not isinstance(kind, str)
                or not kind
                or not isinstance(model.resource_kind, str)
                or kind.lower() != model.resource_kind.lower()
            ):
                raise ValueError("Registry keys must match the model's resource_kind")
            registry[kind.lower()] = model
        return registry

    @staticmethod
    def _template_environment(filters):
        jinja = require_dependency("jinja2", "apply")
        environment = jinja.Environment(undefined=jinja.StrictUndefined, autoescape=False)
        environment.filters["getenv"] = template_getenv
        environment.filters.update(filters or {})
        return environment

    def _load_values(self, sources) -> dict[str, Any]:
        if isinstance(sources, (Mapping, str, Path)):
            sources = [sources]
        values: dict[str, Any] = {}
        for source in sources:
            if isinstance(source, (str, Path)):
                parsed = self._parse(Path(source).read_text(), str(source))
                if len(parsed) != 1:
                    raise ApplyError("Each values file must contain one mapping")
                source = parsed[0]
            if not isinstance(source, Mapping):
                raise ApplyError("Each values source must be a mapping")
            merge_values(values, source)
        return values

    def _add_rio_context(self) -> None:
        config = self.client.config
        rio = {
            "project": {"name": config.project_name, "guid": config.project_guid},
            "organization": {
                "name": config.organization_name,
                "guid": config.organization_guid,
                "short_id": config.organization_short_id,
            },
            "email_id": config.email,
        }
        merge_values(self.values, {"rio": rio})

    def _add_secrets(self, secrets) -> None:
        if secrets is None:
            self.values.setdefault("secrets", {})
            return
        if not isinstance(secrets, Mapping):
            raise ApplyError("secrets must be an already decrypted mapping")
        merge_values(self.values, {"secrets": secrets})

    def _parse(self, content: str, name: str) -> list[Any]:
        try:
            if Path(name).suffix.lower() == ".json":
                loaded = json.loads(content)
                documents = loaded if isinstance(loaded, list) else [loaded]
            else:
                documents = list(self.yaml.safe_load_all(content))
            return [value for value in documents if value is not None]
        except (ValueError, self.yaml.YAMLError) as error:
            raise ApplyError(f"Cannot parse {name}: {error}") from error

    def _expand(self, source: str | Path) -> list[Path]:
        path = Path(source)
        if path.is_symlink() and not path.exists():
            raise ApplyError(f"Manifest path is a broken symlink: {source}")
        if path.is_dir():
            files = sorted(
                p
                for p in path.rglob("*")
                if p.suffix.lower() in (".yaml", ".yml", ".json")
            )
        elif path.is_file():
            files = [path]
        else:
            files = []
            for matched in sorted(glob.glob(str(source), recursive=True)):
                files.extend(self._expand(Path(matched)))
        if not files:
            raise ApplyError(f"No manifests found for {source}")
        if any(p.suffix.lower() not in (".yaml", ".yml", ".json") for p in files):
            raise ApplyError("Only YAML and JSON manifests are supported")
        return files

    def _render_file(self, path: Path) -> list[Any]:
        try:
            content = self.environment.from_string(path.read_text()).render(**self.values)
        except Exception as error:
            raise ApplyError(f"Cannot render {path}: {error}") from error
        return self._parse(content, str(path))

    def _collect_documents(self, resources) -> list[Any]:
        source = self.resources if resources is None else resources
        if isinstance(source, (str, Path, Mapping, BaseModel)):
            source = [source]
        documents = []
        for item in source:
            if isinstance(item, (BaseModel, Mapping)):
                documents.append(item)
            elif isinstance(item, (str, Path)):
                for path in self._expand(item):
                    documents.extend(self._render_file(path))
            else:
                raise ApplyError(f"Unsupported resource input: {type(item).__name__}")
        return documents

    def _select_model(self, document, operation: str) -> type[ResourceModel]:
        if isinstance(document, ResourceModel):
            kind = document.resource_kind
        elif isinstance(document, Mapping):
            kind = document.get("kind")
        else:
            raise ApplyError(f"Unsupported resource input: {type(document).__name__}")
        if not isinstance(kind, str) or kind.lower() not in self.resource_models:
            raise ApplyError(f"Unsupported resource kind: {kind}")
        return self.resource_models[kind.lower()].model_for_operation(operation)

    def _prepare_resource(self, document, operation: str) -> ResourceModel:
        model = self._select_model(document, operation)
        if isinstance(document, model):
            resource = document.model_copy(deep=True)
        elif isinstance(document, ResourceModel):
            resource = model.model_validate(
                document.model_dump(by_alias=True, exclude_none=True)
            )
        else:
            resource = model.model_validate(deepcopy(document))
        resource.bind_context(self.client.config, self.context)
        return resource

    def render(
        self, resources: Any = None, *, operation: str = "apply"
    ) -> list[ResourceModel]:
        """Render templates and validate resource data without any platform calls."""
        self.client.config.features.require("apply")
        self._validate_operation(operation)
        return [
            self._prepare_resource(document, operation)
            for document in self._collect_documents(resources)
        ]

    @staticmethod
    def _validate_operation(operation: str) -> None:
        if operation not in ("apply", "delete"):
            raise ValueError("operation must be apply or delete")

    @staticmethod
    def _index_resources(resources, operation: str) -> dict[str, ResourceModel]:
        objects = {}
        for resource in resources:
            resource.validate_operation(operation)
            if resource.identity in objects:
                raise ApplyError(f"Duplicate resource: {resource.identity}")
            objects[resource.identity] = resource
        return objects

    @staticmethod
    def _resolve_aliases(objects: Mapping[str, ResourceModel]) -> dict[str, str]:
        # Validate aliases against every name before resolving dependency edges.
        aliases = {key: key for key in objects}
        for key, resource in objects.items():
            for alias in resource.reference_keys():
                if alias in aliases and aliases[alias] != key:
                    raise ApplyError(
                        f"Ambiguous resource reference {alias}: {aliases[alias]} and {key}"
                    )
                aliases[alias] = key
        return aliases

    @staticmethod
    def _dependency_layers(objects, aliases, operation: str) -> list[list[str]]:
        graph = graphlib.TopologicalSorter()
        for key, resource in objects.items():
            # Dependencies outside this manifest set refer to existing resources.
            graph.add(key, *(aliases[d] for d in resource.dependencies() if d in aliases))
        try:
            graph.prepare()
        except graphlib.CycleError as error:
            raise ApplyError(f"Dependency cycle: {error.args[1]}") from error
        layers = []
        while graph.is_active():
            ready = list(graph.get_ready())
            layers.append(ready)
            graph.done(*ready)
        if operation == "delete":
            layers.reverse()
        return layers

    def plan(self, resources: Any = None, *, operation: str = "apply") -> ApplyPlan:
        """Validate the entire operation and produce dependency layers."""
        rendered = self.render(resources, operation=operation)
        objects = self._index_resources(rendered, operation)
        aliases = self._resolve_aliases(objects)
        layers = self._dependency_layers(objects, aliases, operation)
        return ApplyPlan(operation=operation, layers=layers, resources=rendered)

    def _batches(self, plan: ApplyPlan) -> Iterator[list[ResourceModel]]:
        objects = {resource.identity: resource for resource in plan.resources}
        for layer in plan.layers:
            for offset in range(0, len(layer), self.workers):
                yield [objects[key] for key in layer[offset : offset + self.workers]]

    @staticmethod
    def _record_results(completed, results: Iterable[ResourceResult]) -> bool:
        failed = False
        for result in results:
            completed[result.identity] = result
            failed |= result.outcome == Outcome.FAILED
        return failed

    @staticmethod
    def _finish(plan: ApplyPlan, completed: dict[str, ResourceResult]) -> ApplyReport:
        return ApplyReport(
            operation=plan.operation,
            results=[
                completed.get(key, ResourceResult(identity=key, outcome=Outcome.SKIPPED))
                for layer in plan.layers
                for key in layer
            ],
        )

    def _dry_run_report(self, plan: ApplyPlan) -> ApplyReport:
        return self._finish(
            plan,
            {
                resource.identity: ResourceResult(
                    identity=resource.identity, outcome=Outcome.PLANNED
                )
                for resource in plan.resources
            },
        )


class Applier(_BaseApplier):
    """Synchronous declarative operations using a shared, thread-safe client."""

    def _run(self, resource: ResourceModel, operation: str) -> ResourceResult:
        try:
            if operation == "apply":
                return resource.apply(
                    self.client,
                    context=self.context,
                    readiness_attempts=self.readiness_attempts,
                    readiness_interval=self.readiness_interval,
                )
            return resource.delete(
                self.client,
                context=self.context,
                readiness_attempts=self.readiness_attempts,
                readiness_interval=self.readiness_interval,
            )
        except Exception as error:
            return ResourceResult(
                identity=resource.identity, outcome=Outcome.FAILED, error=str(error)
            )

    def _execute(self, resources: Any, operation: str, dry_run: bool) -> ApplyReport:
        plan = self.plan(resources, operation=operation)
        if dry_run:
            return self._dry_run_report(plan)
        completed = {}
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            for batch in self._batches(plan):
                futures = [
                    executor.submit(self._run, resource, operation) for resource in batch
                ]
                if self._record_results(
                    completed, (future.result() for future in futures)
                ):
                    break
        return self._finish(plan, completed)

    def apply(self, resources: Any = None, *, dry_run: bool = False) -> ApplyReport:
        return self._execute(resources, "apply", dry_run)

    def delete(self, resources: Any = None, *, dry_run: bool = False) -> ApplyReport:
        return self._execute(resources, "delete", dry_run)


class AsyncApplier(_BaseApplier):
    """Async execution; local rendering and planning remain synchronous."""

    async def _run(self, resource: ResourceModel, operation: str) -> ResourceResult:
        try:
            if operation == "apply":
                return await resource.apply_async(
                    self.client,
                    context=self.context,
                    readiness_attempts=self.readiness_attempts,
                    readiness_interval=self.readiness_interval,
                )
            return await resource.delete_async(
                self.client,
                context=self.context,
                readiness_attempts=self.readiness_attempts,
                readiness_interval=self.readiness_interval,
            )
        except Exception as error:
            return ResourceResult(
                identity=resource.identity, outcome=Outcome.FAILED, error=str(error)
            )

    async def _execute(
        self, resources: Any, operation: str, dry_run: bool
    ) -> ApplyReport:
        plan = self.plan(resources, operation=operation)
        if dry_run:
            return self._dry_run_report(plan)
        completed = {}
        for batch in self._batches(plan):
            async with asyncio.TaskGroup() as group:
                tasks = [
                    group.create_task(self._run(resource, operation))
                    for resource in batch
                ]
            if self._record_results(completed, (task.result() for task in tasks)):
                break
        return self._finish(plan, completed)

    async def apply(self, resources: Any = None, *, dry_run: bool = False) -> ApplyReport:
        return await self._execute(resources, "apply", dry_run)

    async def delete(
        self, resources: Any = None, *, dry_run: bool = False
    ) -> ApplyReport:
        return await self._execute(resources, "delete", dry_run)
