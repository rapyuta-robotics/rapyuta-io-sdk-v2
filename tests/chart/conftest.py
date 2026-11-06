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

"""Controlled chart bundles and transports for offline acceptance tests."""

from __future__ import annotations

import asyncio
import io
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import httpx
import pytest

from rapyuta_io_sdk_v2.chart import AsyncChart, Chart, ChartSource, _package

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


@pytest.fixture
def chart_dir(tmp_path: Path) -> Path:
    root = tmp_path / "sample"
    (root / "templates").mkdir(parents=True)
    (root / "Chart.yaml").write_text(
        "apiVersion: v1\nname: sample\nversion: 1.0.0\ndescription: sample chart\n"
    )
    (root / "values.yaml").write_text("name: viewer\n")
    (root / "templates" / "role.yaml").write_text(
        "kind: Role\nmetadata:\n  name: '{{ name }}'\nspec:\n  rules: []\n"
    )
    return root


@pytest.fixture
def archive_bytes() -> Callable[[Path], bytes]:
    def pack(root: Path) -> bytes:
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            archive.add(root, arcname=root.name)
        return stream.getvalue()

    return pack


@pytest.fixture(autouse=True)
def no_live_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*_args: object, **_kwargs: object) -> None:
        msg = "chart test attempted live HTTP"
        raise AssertionError(msg)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)


@pytest.fixture(
    params=[
        "!!timestamp not-a-timestamp",
        "!!bool maybe",
        "!!int ''",
        "!!float ''",
        None,
    ],
    ids=["invalid-timestamp", "invalid-bool", "empty-int", "empty-float", "valid-tags"],
)
def yaml_scalar_case(request: pytest.FixtureRequest) -> tuple[str, bool]:
    if request.param is not None:
        return f"extra: {request.param}\n", False
    return (
        (
            "extra:\n  enabled: !!bool true\n  count: !!int 12\n"
            "  fraction: !!float 1.5\n  text: !!str café\n"
        ),
        True,
    )


@pytest.fixture(params=[Chart, AsyncChart], ids=["sync", "async"])
def chart_loader(request: pytest.FixtureRequest) -> Callable:
    """Exercise each public loading mode without blocking the test event loop."""

    async def load(source: ChartSource, **kwargs: object) -> Chart | AsyncChart:
        if request.param is Chart:
            return await asyncio.to_thread(Chart.load, source, **kwargs)
        return await AsyncChart.load(source, **kwargs)

    load.chart_type = request.param
    return load


@pytest.fixture
def chart_staging(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Path]]:
    paths = []

    def temporary(**kwargs: object) -> TemporaryDirectory:
        value = TemporaryDirectory(**kwargs)
        paths.append(Path(value.name))
        return value

    monkeypatch.setattr(_package, "TemporaryDirectory", temporary)
    yield paths
    assert all(not path.exists() for path in paths)
