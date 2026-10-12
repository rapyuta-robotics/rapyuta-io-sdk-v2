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

"""Controlled clients and reusable fixtures for applier contract tests."""

from __future__ import annotations

import asyncio
import textwrap
from typing import TYPE_CHECKING, get_args

import httpx
import pytest
import pytest_asyncio

from rapyuta_io_sdk_v2.async_client import AsyncClient
from rapyuta_io_sdk_v2.client import Client
from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.models import (
    Deployment,
    Disk,
    Network,
    Organization,
    Package,
    Project,
    Role,
    RoleBinding,
    Secret,
    ServiceAccount,
    StaticRoute,
    UserGroup,
)
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.network import NetworkSpec
from rapyuta_io_sdk_v2.models.organization import OrganizationSpec
from rapyuta_io_sdk_v2.models.rolebinding import (
    RoleBindingSpec,
    RoleRef,
)
from rapyuta_io_sdk_v2.models.utils import Domain, Subject

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

ResourceModel = (
    Organization
    | Project
    | Package
    | Deployment
    | Disk
    | Network
    | StaticRoute
    | Secret
    | UserGroup
    | Role
    | RoleBinding
    | ServiceAccount
)


class RequestRecorder:
    """Record requests and provide a replaceable typed test response handler."""

    def __init__(self) -> None:
        """Create an empty request recorder with a default response handler."""
        self.requests: list[httpx.Request] = []
        self.handler: Callable[[httpx.Request], httpx.Response] = self._default

    def _default(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json={"data": {}})

    def respond_with(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        """Install a custom request handler while retaining request accounting."""

        def record_and_respond(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return handler(request)

        self.handler = record_and_respond


@pytest.fixture
def request_recorder() -> RequestRecorder:
    return RequestRecorder()


@pytest.fixture
def configured_client(request_recorder: RequestRecorder) -> Client:
    configuration = Configuration(
        auth_token="dummy-token",
        organization_guid="dummy-organization",
        project_guid="dummy-project",
        environment="local",
    )
    client = Client(configuration)
    client.c.close()
    client.c = httpx.Client(transport=httpx.MockTransport(request_recorder.handler))
    return client


@pytest_asyncio.fixture
async def configured_async_client(request_recorder: RequestRecorder) -> AsyncClient:
    configuration = Configuration(
        auth_token="dummy-token",
        organization_guid="dummy-organization",
        project_guid="dummy-project",
        environment="local",
    )
    client = AsyncClient(configuration)
    await client.c.aclose()
    client.sync_client.close()
    client.c = httpx.AsyncClient(
        transport=httpx.MockTransport(request_recorder.handler)
    )
    try:
        yield client
    finally:
        await client.c.aclose()


@pytest.fixture
def resource_fixtures() -> dict[str, ResourceModel]:
    models: dict[str, type[ResourceModel]] = {
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
    return {kind: _resource_fixture(kind, model) for kind, model in models.items()}


def _fixture_model_type(annotation: object) -> type[SDKModel]:
    if isinstance(annotation, type) and issubclass(annotation, SDKModel):
        return annotation
    return next(
        candidate
        for candidate in get_args(annotation)
        if isinstance(candidate, type) and issubclass(candidate, SDKModel)
    )


def _resource_fixture(kind: str, model: type[ResourceModel]) -> ResourceModel:
    fields = model.model_fields
    metadata_type = _fixture_model_type(fields["metadata"].annotation)
    metadata_values: dict[str, object] = {"name": f"fixture-{kind}"}
    if kind == "package":
        metadata_values["version"] = "v1"
    values: dict[str, object] = {
        "metadata": metadata_type.model_construct(**metadata_values)
    }
    spec = _fixture_spec(kind, fields)
    if spec is not None:
        values["spec"] = spec
    return model.model_construct(**values)


def _fixture_spec(kind: str, fields: object) -> SDKModel | None:
    if "spec" not in fields:
        return None
    if kind == "rolebinding":
        spec = RoleBindingSpec(
            role_ref=RoleRef(name="fixture-role"),
            domain=Domain(kind="Project", name="fixture-project"),
            subject=Subject(kind="User", name="fixture-user"),
        )
    elif kind == "organization":
        spec = OrganizationSpec(members=[])
    elif kind == "network":
        spec = NetworkSpec.model_construct(
            type="routed", ros_distro="noetic", runtime="cloud"
        )
    else:
        spec_type = _fixture_model_type(fields["spec"].annotation)
        spec = spec_type.model_construct()
    return spec


@pytest.fixture
def async_barrier() -> asyncio.Event:
    return asyncio.Event()


@pytest.fixture
def fake_sops(tmp_path: Path) -> Callable[..., Path]:
    def create(
        *,
        stdout: str = "{}",
        stderr: str = "",
        exit_code: int = 0,
        delay: float = 0,
    ) -> Path:
        executable = tmp_path / "fake sops executable"
        source = textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import sys
            import time

            time.sleep({delay!r})
            sys.stdout.write({stdout!r})
            sys.stderr.write({stderr!r})
            raise SystemExit({exit_code})
            """
        )
        executable.write_text(source)
        executable.chmod(0o755 | (executable.stat().st_mode & 0o111))
        return executable

    return create


__all__ = ["RequestRecorder", "ResourceModel"]
