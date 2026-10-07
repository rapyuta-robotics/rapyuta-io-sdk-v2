"""Render, validate, order and execute declarative resource manifests."""

from __future__ import annotations

import asyncio
import glob
import graphlib
import json
import os
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from rapyuta_io_sdk_v2.features import require_dependency
from rapyuta_io_sdk_v2.models.secret import Secret
from rapyuta_io_sdk_v2.models.usergroup import UserGroup
from rapyuta_io_sdk_v2.models.utils import resource_key

from .handlers import DEFAULT_HANDLERS, Pause, Request, ResourceHandler, resource_kind
from .types import ApplyError, ApplyPlan, ApplyReport, Outcome, ResourceResult


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
        context: Any = None,
        handlers: Mapping[str, type[ResourceHandler]] | None = None,
    ):
        client.config.features.require("apply")
        self.yaml = require_dependency("yaml", "apply")
        jinja = require_dependency("jinja2", "apply")
        if workers < 1 or readiness_attempts < 1 or readiness_interval < 0:
            raise ValueError("workers/attempts must be positive and interval nonnegative")
        self.client = client
        # Plans and execution must see the same inputs, even with a generator.
        self.resources = (
            tuple(resources) if isinstance(resources, Iterator) else resources
        )
        self.workers = workers
        self.readiness_attempts = readiness_attempts
        self.readiness_interval = readiness_interval
        self.context = context
        self.handlers = {
            **DEFAULT_HANDLERS,
            **{k.lower(): v for k, v in (handlers or {}).items()},
        }
        self.environment = jinja.Environment(
            undefined=jinja.StrictUndefined, autoescape=False
        )
        self.environment.filters["getenv"] = template_getenv
        self.environment.filters.update(filters or {})
        self.values: dict[str, Any] = {}
        if isinstance(values, Mapping):
            values = [values]
        elif isinstance(values, (str, Path)):
            values = [values]
        for value in values:
            if isinstance(value, (str, Path)):
                parsed = self._parse(Path(value).read_text(), str(value))
                if len(parsed) != 1:
                    raise ApplyError("Each values file must contain one mapping")
                value = parsed[0]
            if not isinstance(value, Mapping):
                raise ApplyError("Each values source must be a mapping")
            merge_values(self.values, value)
        config = client.config
        rio = {
            "project": {
                "name": getattr(config, "project_name", None),
                "guid": config.project_guid,
            },
            "organization": {
                "name": getattr(config, "organization_name", None),
                "guid": config.organization_guid,
                "short_id": getattr(config, "organization_short_id", None),
            },
            "email_id": getattr(config, "email", None),
        }
        merge_values(self.values, {"rio": rio})
        if secrets is not None:
            if not isinstance(secrets, Mapping):
                raise ApplyError("secrets must be an already decrypted mapping")
            merge_values(self.values, {"secrets": secrets})
        else:
            self.values.setdefault("secrets", {})

    def _parse(self, content: str, name: str) -> list[Any]:
        try:
            loaded = (
                json.loads(content)
                if Path(name).suffix.lower() == ".json"
                else list(self.yaml.safe_load_all(content))
            )
            if Path(name).suffix.lower() == ".json":
                loaded = loaded if isinstance(loaded, list) else [loaded]
            return [value for value in loaded if value is not None]
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

    def render(
        self, resources: Any = None, *, operation: str = "apply"
    ) -> list[BaseModel]:
        """Render templates and validate resource data without any platform calls."""
        self.client.config.features.require("apply")
        source = self.resources if resources is None else resources
        if isinstance(source, (str, Path, Mapping, BaseModel)):
            source = [source]
        documents = []
        for item in source:
            if isinstance(item, (BaseModel, Mapping)):
                documents.append(item)
            elif isinstance(item, (str, Path)):
                for path in self._expand(item):
                    try:
                        content = self.environment.from_string(path.read_text()).render(
                            **self.values
                        )
                    except Exception as error:
                        raise ApplyError(f"Cannot render {path}: {error}") from error
                    documents.extend(self._parse(content, str(path)))
            else:
                raise ApplyError(f"Unsupported resource input: {type(item).__name__}")
        rendered = []
        for document in documents:
            kind = (
                resource_kind(document, self.handlers)
                if isinstance(document, BaseModel)
                else document.get("kind")
            )
            handler = self.handlers.get((kind or "").lower())
            if handler is None:
                raise ApplyError(f"Unsupported resource kind: {kind}")
            model = handler.model
            if operation == "delete":
                model = {"secret": Secret, "usergroup": UserGroup}.get(
                    kind.lower(), model
                )
            if isinstance(document, BaseModel):
                if not isinstance(document, model):
                    document = model.model_validate(
                        document.model_dump(by_alias=True, exclude_none=True)
                    )
                else:
                    document = document.model_copy(deep=True)
            else:
                document = model.model_validate(deepcopy(document))
            if not document.kind:
                document.kind = kind
            if kind.lower() == "project":
                organization = (
                    getattr(self.context, "organization_guid", None)
                    or self.client.config.organization_guid
                )
                if organization is not None:
                    document.metadata.organization_guid = organization
            rendered.append(document)
        return rendered

    def plan(self, resources: Any = None, *, operation: str = "apply") -> ApplyPlan:
        """Validate the entire operation and produce dependency layers."""
        if operation not in ("apply", "delete"):
            raise ValueError("operation must be apply or delete")
        rendered = self.render(resources, operation=operation)
        objects: dict[str, ResourceHandler] = {}
        for resource in rendered:
            handler = self.handlers[resource.kind.lower()](resource)
            handler.validate_operation(operation)
            if handler.identity in objects:
                raise ApplyError(f"Duplicate resource: {handler.identity}")
            objects[handler.identity] = handler
        # Both names and GUIDs may refer to resources included in this operation.
        # Validate aliases against every name before resolving dependency edges.
        aliases = {key: key for key in objects}
        for key, handler in objects.items():
            resource = handler.resource
            guid = resource.metadata.guid
            if not guid:
                continue
            alias = resource_key(
                resource.kind,
                guid,
                resource.metadata.version if resource.kind.lower() == "package" else None,
            )
            if alias in aliases and aliases[alias] != key:
                raise ApplyError(
                    f"Ambiguous resource reference {alias}: {aliases[alias]} and {key}"
                )
            aliases[alias] = key
        graph = graphlib.TopologicalSorter()
        for key, handler in objects.items():
            # Dependencies outside this manifest set refer to existing resources.
            graph.add(key, *(aliases[d] for d in handler.dependencies() if d in aliases))
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
        return ApplyPlan(operation=operation, layers=layers, resources=rendered)

    def _objects(self, plan: ApplyPlan) -> dict[str, ResourceHandler]:
        handlers = [self.handlers[r.kind.lower()](r) for r in plan.resources]
        return {h.identity: h for h in handlers}

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


class Applier(_BaseApplier):
    """Synchronous declarative operations using a shared, thread-safe client."""

    def _run(self, handler: ResourceHandler, operation: str) -> ResourceResult:
        workflow = handler.workflow(
            operation, self.readiness_attempts, self.readiness_interval
        )
        value = None
        error = None
        try:
            while True:
                try:
                    step = (
                        workflow.throw(error)
                        if error is not None
                        else workflow.send(value)
                    )
                except StopIteration as stop:
                    outcome, resource = stop.value
                    return ResourceResult(
                        identity=handler.identity, outcome=outcome, resource=resource
                    )
                value, error = None, None
                try:
                    if isinstance(step, Pause):
                        time.sleep(step.seconds)
                    elif isinstance(step, Request):
                        kwargs = dict(step.kwargs)
                        if self.context is not None:
                            kwargs["context"] = self.context
                        value = getattr(self.client, step.method)(*step.args, **kwargs)
                    else:
                        raise ApplyError(f"Invalid handler step: {step}")
                except Exception as caught:
                    error = caught
        except Exception as caught:
            return ResourceResult(
                identity=handler.identity, outcome=Outcome.FAILED, error=str(caught)
            )
        finally:
            workflow.close()

    def _execute(self, resources: Any, operation: str, dry_run: bool) -> ApplyReport:
        self.client.config.features.require("apply")
        plan = self.plan(resources, operation=operation)
        objects = self._objects(plan)
        completed = {}
        if dry_run:
            for key in objects:
                completed[key] = ResourceResult(identity=key, outcome=Outcome.PLANNED)
            return self._finish(plan, completed)
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            failed = False
            for layer in plan.layers:
                for offset in range(0, len(layer), self.workers):
                    batch = layer[offset : offset + self.workers]
                    futures = [
                        executor.submit(self._run, objects[key], operation)
                        for key in batch
                    ]
                    for future in futures:
                        result = future.result()
                        completed[result.identity] = result
                        failed |= result.outcome == Outcome.FAILED
                    if failed:
                        break
                if failed:
                    break
        return self._finish(plan, completed)

    def apply(self, resources: Any = None, *, dry_run: bool = False) -> ApplyReport:
        return self._execute(resources, "apply", dry_run)

    def delete(self, resources: Any = None, *, dry_run: bool = False) -> ApplyReport:
        return self._execute(resources, "delete", dry_run)


class AsyncApplier(_BaseApplier):
    """Async execution; local rendering and planning remain synchronous."""

    async def _run(self, handler: ResourceHandler, operation: str) -> ResourceResult:
        workflow = handler.workflow(
            operation, self.readiness_attempts, self.readiness_interval
        )
        value = None
        error = None
        try:
            while True:
                try:
                    step = (
                        workflow.throw(error)
                        if error is not None
                        else workflow.send(value)
                    )
                except StopIteration as stop:
                    outcome, resource = stop.value
                    return ResourceResult(
                        identity=handler.identity, outcome=outcome, resource=resource
                    )
                value, error = None, None
                try:
                    if isinstance(step, Pause):
                        await asyncio.sleep(step.seconds)
                    elif isinstance(step, Request):
                        kwargs = dict(step.kwargs)
                        if self.context is not None:
                            kwargs["context"] = self.context
                        value = await getattr(self.client, step.method)(
                            *step.args, **kwargs
                        )
                    else:
                        raise ApplyError(f"Invalid handler step: {step}")
                except Exception as caught:
                    error = caught
        except Exception as caught:
            return ResourceResult(
                identity=handler.identity, outcome=Outcome.FAILED, error=str(caught)
            )
        finally:
            workflow.close()

    async def _execute(
        self, resources: Any, operation: str, dry_run: bool
    ) -> ApplyReport:
        self.client.config.features.require("apply")
        plan = self.plan(resources, operation=operation)
        objects = self._objects(plan)
        completed = {}
        if dry_run:
            for key in objects:
                completed[key] = ResourceResult(identity=key, outcome=Outcome.PLANNED)
            return self._finish(plan, completed)
        failed = False
        for layer in plan.layers:
            for offset in range(0, len(layer), self.workers):
                batch = layer[offset : offset + self.workers]
                async with asyncio.TaskGroup() as group:
                    tasks = [
                        group.create_task(self._run(objects[key], operation))
                        for key in batch
                    ]
                results = [task.result() for task in tasks]
                for result in results:
                    completed[result.identity] = result
                    failed |= result.outcome == Outcome.FAILED
                if failed:
                    break
            if failed:
                break
        return self._finish(plan, completed)

    async def apply(self, resources: Any = None, *, dry_run: bool = False) -> ApplyReport:
        return await self._execute(resources, "apply", dry_run)

    async def delete(
        self, resources: Any = None, *, dry_run: bool = False
    ) -> ApplyReport:
        return await self._execute(resources, "delete", dry_run)
