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

"""Shared offline acquisition and lifecycle boundaries for Chart acceptance tests."""

from __future__ import annotations

import asyncio
import inspect
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import httpx
import yaml

from rapyuta_io_sdk_v2 import AsyncClient, Client, Configuration
from rapyuta_io_sdk_v2.chart import AsyncChart, Chart, ChartSource
from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError
from rapyuta_io_sdk_v2.models.rolebinding import RoleBindingList
from rapyuta_io_sdk_v2.models.utils import ListMeta

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from pathlib import Path


def bundle_source(root: Path, pack: Callable, kind: str) -> ChartSource:
    if kind == "directory":
        return ChartSource.from_directory(root)
    if kind == "repository":
        return ChartSource.from_repository("sample:1.0.0")
    archive = root.parent / "sample.tgz"
    archive.write_bytes(pack(root))
    return ChartSource.from_archive(archive)


def repository_response(data: bytes, entry: dict | None = None) -> Callable:
    selected = entry or {
        "name": "sample",
        "version": "1.0.0",
        "urls": ["https://chart.test/chart.tgz"],
    }
    index = yaml.safe_dump({"entries": {"sample": [selected]}}).encode()

    def respond(request: httpx.Request) -> httpx.Response:
        content = index if request.url.path.endswith("yaml") else data
        return httpx.Response(200, content=content, request=request)

    return respond


@asynccontextmanager
async def acquisition_client(loader: Callable, respond: Callable) -> AsyncIterator:
    if loader.chart_type is Chart:
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            yield client
    else:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            yield client


async def chart_call(
    chart: Chart | AsyncChart, method: str, **kwargs: object
) -> object:
    operation = getattr(chart, method)
    if inspect.iscoroutinefunction(operation):
        return await operation(**kwargs)
    return await asyncio.to_thread(operation, **kwargs)


class PlatformRecorder:
    """Control real client methods while preserving their sync/async call shape."""

    def __init__(self, binding: object) -> None:
        """Initialize isolated controlled server state."""
        self.binding = binding
        self.present = False
        self.fail = None
        self.absent = False
        self.events = []

    def create_role(self, resource: object, **kwargs: object) -> object:
        """Record the scoped write or raise the selected failure."""
        self.events.append(
            ("create", resource.metadata.name, kwargs["organization_guid"])
        )
        if self.fail == "create":
            msg = "controlled write failure"
            raise RuntimeError(msg)
        return resource

    def list_role_bindings(self, **_kwargs: object) -> object:
        """Return the current controlled exact grant."""
        return RoleBindingList(
            items=[self.binding] if self.present else [], metadata=ListMeta()
        )

    def update_role_binding(self, payload: object, **_kwargs: object) -> object:
        """Record granting or revoking a binding."""
        operation = "grant" if payload.new_bindings else "revoke"
        self.events.append((operation,))
        if self.fail == operation:
            msg = "controlled write failure"
            raise RuntimeError(msg)
        self.present = bool(payload.new_bindings)
        return payload

    def delete_role(self, name: str, **kwargs: object) -> None:
        """Record deletion and optionally report an absent resource."""
        self.events.append(("delete", name, kwargs["organization_guid"]))
        if self.absent:
            raise HttpNotFoundError


@asynccontextmanager
async def platform_client(
    loader: Callable, recorder: PlatformRecorder, *, org: str = "org"
) -> AsyncIterator:
    kind = Client if loader.chart_type is Chart else AsyncClient
    client = kind(Configuration(auth_token="chart-test", organization_guid=org))
    for name in [
        "create_role",
        "list_role_bindings",
        "update_role_binding",
        "delete_role",
    ]:
        callback = getattr(recorder, name)
        setattr(client, name, callback if kind is Client else _awaitable(callback))
    try:
        yield client
        assert not client.c.is_closed
        assert client.config.organization_guid == org
    finally:
        if kind is Client:
            client.c.close()
        else:
            await client.c.aclose()


def _awaitable(callback: Callable) -> Callable:
    async def invoke(*args: object, **kwargs: object) -> object:
        return callback(*args, **kwargs)

    return invoke


def role_binding_documents() -> list[dict]:
    return [
        {"kind": "Role", "metadata": {"name": "viewer"}, "spec": {"rules": []}},
        {
            "kind": "RoleBinding",
            "metadata": {},
            "spec": {
                "roleRef": {"name": "viewer"},
                "domain": {"kind": "Project", "name": "alpha"},
                "subject": {"kind": "User", "name": "ava"},
            },
        },
    ]


def result_data(result: object) -> dict:
    return result.model_dump(exclude={"outcomes": {"__all__": {"source"}}})
