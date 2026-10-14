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

"""Local package confinement, values semantics, and eager ownership cleanup."""

from __future__ import annotations

import bz2
import gzip
import hashlib
import io
import lzma
import os
import struct
import subprocess
import sys
import tarfile
import zlib
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import httpx
import pytest
import yaml
from pydantic import ValidationError

from rapyuta_io_sdk_v2 import ApplierUsageError, ApplierValidationError
from rapyuta_io_sdk_v2.chart import (
    DEFAULT_REPOSITORY,
    AsyncChart,
    Chart,
    ChartInputs,
    ChartLoadError,
    ChartSource,
    ChartVersionWarning,
)
from tests.chart.helpers import (
    PlatformRecorder,
    acquisition_client,
    bundle_source,
    platform_client,
    repository_response,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def test_archive_survives_source_removal_and_matches_directory(
    chart_dir: Path, archive_bytes: Callable, tmp_path: Path
) -> None:
    local = Chart.load(ChartSource.from_directory(chart_dir))
    archive = tmp_path / "chart.tgz"
    archive.write_bytes(archive_bytes(chart_dir))
    packed = Chart.load(ChartSource.from_archive(archive))
    archive.unlink()
    assert packed.template_paths == local.template_paths == ("templates/role.yaml",)
    assert packed.metadata.name == "sample"
    exclude = {"outcomes": {"__all__": {"source"}}}
    assert packed.apply(dry_run=True).model_dump(exclude=exclude) == local.apply(
        dry_run=True
    ).model_dump(exclude=exclude)


@pytest.mark.parametrize("values", [None, (), []])
def test_absent_values_use_bundled_defaults(chart_dir: Path, values: object) -> None:
    chart = Chart.load(
        ChartSource.from_directory(chart_dir), inputs=ChartInputs(values=values)
    )
    assert chart.apply(dry_run=True).outcomes[0].identity.name == "viewer"


def test_explicit_empty_values_do_not_fall_back(chart_dir: Path) -> None:
    with pytest.raises(ApplierValidationError):
        Chart.load(ChartSource.from_directory(chart_dir), inputs=ChartInputs(values={}))


def test_unused_defaults_do_not_need_to_be_read(chart_dir: Path) -> None:
    (chart_dir / "values.yaml").write_text("not: [valid")
    chart = Chart.load(
        ChartSource.from_directory(chart_dir),
        inputs=ChartInputs(values={"name": "explicit"}),
    )
    assert chart.apply(dry_run=True).outcomes[0].identity.name == "explicit"


def test_ordered_merge_and_external_value_sources(
    chart_dir: Path, tmp_path: Path
) -> None:
    values = tmp_path / "external.yaml"
    values.write_text("name: first\nnested: {first: A}\n")
    chart = Chart.load(
        ChartSource.from_directory(chart_dir),
        inputs=ChartInputs(
            values=[values, {"name": "second", "nested": {"second": "B"}}]
        ),
    )
    assert chart.apply(dry_run=True).outcomes[0].identity.name == "second"


def test_local_links_are_rejected_before_reading(
    chart_dir: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.yaml"
    outside.write_text("sensitive contents")
    (chart_dir / "templates" / "link.yaml").symlink_to(outside)
    with pytest.raises(ChartLoadError):
        Chart.load(ChartSource.from_directory(chart_dir))
    assert outside.read_text() == "sensitive contents"


@pytest.mark.parametrize(
    "name", ["../outside", "/absolute", "sample/../outside", "bad\\name"]
)
def test_archive_traversal_is_rejected(tmp_path: Path, name: str) -> None:
    archive_path = tmp_path / "bad.tgz"
    with tarfile.open(archive_path, "w:gz") as archive:
        member = tarfile.TarInfo(name)
        archive.addfile(member, io.BytesIO())
    with pytest.raises(ChartLoadError) as error:
        Chart.load(ChartSource.from_archive(archive_path))
    assert error.value.stage == "archive"
    assert not (tmp_path / "outside").exists()


@pytest.mark.parametrize(
    "kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE]
)
def test_archive_special_members_are_rejected(tmp_path: Path, kind: bytes) -> None:
    archive_path = tmp_path / "bad.tgz"
    with tarfile.open(archive_path, "w:gz") as archive:
        member = tarfile.TarInfo("sample/link")
        member.type = kind
        member.linkname = "outside"
        archive.addfile(member)
    with pytest.raises(ChartLoadError):
        Chart.load(ChartSource.from_archive(archive_path))


@pytest.mark.parametrize("names", [("same", "same"), ("parent", "parent/child")])
def test_archive_duplicate_and_file_directory_collisions(
    tmp_path: Path, names: tuple
) -> None:
    archive_path = tmp_path / "bad.tgz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for name in names:
            archive.addfile(tarfile.TarInfo(name), io.BytesIO())
    with pytest.raises(ChartLoadError):
        Chart.load(ChartSource.from_archive(archive_path))


def test_no_supported_templates_is_invalid_but_empty_documents_are_valid(
    chart_dir: Path,
) -> None:
    template = chart_dir / "templates" / "role.yaml"
    template.unlink()
    with pytest.raises(ChartLoadError):
        Chart.load(ChartSource.from_directory(chart_dir))
    template.write_text("---\n")
    assert Chart.load(ChartSource.from_directory(chart_dir)).apply().successful


def test_repository_exact_entry_and_first_url_only(
    chart_dir: Path, archive_bytes: Callable
) -> None:

    data = archive_bytes(chart_dir)
    requested = []
    entry = {
        "name": "sample",
        "version": "1.0.0",
        "urls": ["https://charts.test/first.tgz", "https://charts.test/second.tgz"],
    }

    def response(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        content = (
            yaml.safe_dump({"entries": {"sample": [entry, entry]}}).encode()
            if request.url.path.endswith("yaml")
            else data
        )
        return httpx.Response(200, content=content, request=request)

    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        with pytest.warns(ChartVersionWarning):
            chart = Chart.load(
                ChartSource.from_repository(
                    "sample", repository="https://charts.test/index.yaml"
                ),
                http_client=client,
            )
        assert chart.entry.version == "1.0.0"
        assert chart.apply(dry_run=True).successful
        assert requested == [
            "https://charts.test/index.yaml",
            "https://charts.test/first.tgz",
        ]
        assert not client.is_closed


def test_repository_metadata_mismatch_is_rejected(
    chart_dir: Path, archive_bytes: Callable
) -> None:

    data = archive_bytes(chart_dir)

    def response(request: httpx.Request) -> httpx.Response:
        entry = {
            "name": "sample",
            "version": "9",
            "urls": ["https://charts.test/package.tgz"],
        }
        content = (
            yaml.safe_dump({"entries": {"sample": [entry]}}).encode()
            if request.url.path.endswith("yaml")
            else data
        )
        return httpx.Response(200, content=content, request=request)

    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        with pytest.raises(ChartLoadError) as error:
            Chart.load(ChartSource.from_repository("sample:9"), http_client=client)
        assert error.value.category == "identity_mismatch"


def test_owned_sync_http_client_is_closed_after_loading(
    chart_dir: Path, archive_bytes: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = archive_bytes(chart_dir)
    owned = []
    real_client = httpx.Client

    def response(request: httpx.Request) -> httpx.Response:
        entry = {
            "name": "sample",
            "version": "1.0.0",
            "urls": ["https://charts.test/package.tgz"],
        }
        content = (
            yaml.safe_dump({"entries": {"sample": [entry]}}).encode()
            if request.url.path.endswith("yaml")
            else data
        )
        return httpx.Response(200, content=content, request=request)

    class RecordingClient(real_client):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(transport=httpx.MockTransport(response), **kwargs)
            owned.append(self)

    monkeypatch.setattr(httpx, "Client", RecordingClient)
    chart = Chart.load(ChartSource.from_repository("sample"))
    assert chart.apply(dry_run=True).successful
    assert len(owned) == 1
    assert owned[0].is_closed


@pytest.mark.parametrize("suffix", [".yaml", ".yml", ".JSON"])
def test_templates_have_deterministic_relative_paths(
    chart_dir: Path, suffix: str
) -> None:
    directory = chart_dir / "templates/nested"
    directory.mkdir()
    text = '{"kind":"Role","metadata":{"name":"other"},"spec":{"rules":[]}}'
    (directory / f"a{suffix}").write_text(text)
    (chart_dir / "notes.yaml").write_text("not a manifest")
    chart = Chart.load(ChartSource.from_directory(chart_dir))
    assert chart.template_paths == (
        f"templates/nested/a{suffix}",
        "templates/role.yaml",
    )
    assert [item.identity.name for item in chart.apply(dry_run=True).outcomes] == [
        "other",
        "viewer",
    ]


def test_missing_defaults_identifies_the_needed_source(chart_dir: Path) -> None:
    defaults = chart_dir / "values.yaml"
    defaults.unlink()
    with pytest.raises(ApplierValidationError) as error:
        Chart.load(ChartSource.from_directory(chart_dir))
    assert error.value.source.path == str(defaults)


def test_duplicate_identity_keeps_applier_failure(chart_dir: Path) -> None:
    (chart_dir / "templates/second.yaml").write_text(
        (chart_dir / "templates/role.yaml").read_text()
    )
    with pytest.raises(ApplierValidationError) as error:
        Chart.load(ChartSource.from_directory(chart_dir))
    assert error.value.category == "duplicate_identity"


def test_hidden_templates_follow_cli_directory_discovery(chart_dir: Path) -> None:
    (chart_dir / "templates/.hidden.yaml").write_text("kind: UnknownKind\n")
    hidden = chart_dir / "templates/.private"
    hidden.mkdir()
    (hidden / "invalid.yaml").write_text("not valid yaml: [")
    chart = Chart.load(ChartSource.from_directory(chart_dir))
    assert chart.template_paths == ("templates/role.yaml",)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["directory", "archive", "repository"])
async def test_invalid_metadata_encoding_has_chart_boundary(
    chart_dir: Path,
    archive_bytes: Callable,
    chart_loader: Callable,
    *,
    kind: str,
    chart_staging: list[Path],
) -> None:
    (chart_dir / "Chart.yaml").write_bytes(b"\xff\xfeinvalid")
    source = bundle_source(chart_dir, archive_bytes, kind)
    async with acquisition_client(
        chart_loader, repository_response(archive_bytes(chart_dir))
    ) as client:
        with pytest.raises(ChartLoadError) as error:
            await chart_loader(source, http_client=client)
    assert error.value.stage == "metadata"
    assert error.value.source == str(source.path or source.selector)
    assert (chart_dir / "Chart.yaml").read_bytes() == b"\xff\xfeinvalid"
    assert bool(chart_staging) == (kind != "directory")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["directory", "archive", "repository"])
async def test_yaml_constructor_failure_keeps_metadata_boundary(
    chart_dir: Path,
    archive_bytes: Callable,
    chart_loader: Callable,
    *,
    kind: str,
    chart_staging: list[Path],
) -> None:
    metadata = b"name: sample\nversion: 1.0.0\ncreated: 2026-99-99\n"
    (chart_dir / "Chart.yaml").write_bytes(metadata)
    data = archive_bytes(chart_dir)
    archive = chart_dir.parent / "bad-metadata.tgz"
    archive.write_bytes(data)
    source = {
        "directory": ChartSource.from_directory(chart_dir),
        "archive": ChartSource.from_archive(archive),
        "repository": ChartSource.from_repository("sample:1.0.0"),
    }[kind]
    async with acquisition_client(chart_loader, repository_response(data)) as client:
        with pytest.raises(ChartLoadError) as error:
            await chart_loader(source, http_client=client)
        assert not client.is_closed
    assert error.value.stage == "metadata"
    assert error.value.category == "invalid_metadata"
    assert error.value.source == str(source.path or source.selector)
    assert "2026-99-99" not in str(error.value)
    assert (chart_dir / "Chart.yaml").read_bytes() == metadata
    assert archive.read_bytes() == data
    assert bool(chart_staging) == (kind != "directory")
    assert all(not path.exists() for path in chart_staging)


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("kind", ["directory", "archive", "repository"])
@pytest.mark.skipif(
    sys.platform == "win32", reason="LC_ALL does not select the Windows ANSI code page"
)
def test_metadata_is_utf8_under_ascii_locale(
    chart_dir: Path, archive_bytes: Callable, *, mode: str, kind: str
) -> None:
    metadata = "name: sample\nversion: 1.0.0\ndescription: café\n".encode()
    (chart_dir / "Chart.yaml").write_bytes(metadata)
    archive = chart_dir.parent / "utf8-chart.tgz"
    data = archive_bytes(chart_dir)
    archive.write_bytes(data)
    program = r"""
import asyncio
import codecs
import locale
import sys
from pathlib import Path
import httpx
from rapyuta_io_sdk_v2.chart import Chart, AsyncChart, ChartSource

assert not sys.flags.utf8_mode
assert codecs.lookup(locale.getencoding()).name == "ascii"
mode, kind, directory = sys.argv[1:]
root = Path(directory)
data = (root.parent / "utf8-chart.tgz").read_bytes()
sources = {
    "directory": ChartSource.from_directory(root),
    "archive": ChartSource.from_archive(root.parent / "utf8-chart.tgz"),
    "repository": ChartSource.from_repository("sample:1.0.0"),
}
def respond(request):
    if request.url.path.endswith("yaml"):
        index = (
            'entries: {sample: [{name: sample, version: "1.0.0", '
            'urls: ["https://chart.test/chart.tgz"]}]}'
        )
        return httpx.Response(200, text=index)
    assert str(request.url) == "https://chart.test/chart.tgz"
    return httpx.Response(200, content=data)
def no_live(*args, **kwargs):
    raise AssertionError("unexpected live HTTP")
httpx.HTTPTransport.handle_request = no_live
httpx.AsyncHTTPTransport.handle_async_request = no_live
def check(chart, client):
    assert chart.metadata.description == "caf\u00e9"
    assert chart.inspect().resource_identities[0].name == "viewer"
    assert not client.is_closed
async def load_async():
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        check(await AsyncChart.load(sources[kind], http_client=client), client)
if mode == "sync":
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        check(Chart.load(sources[kind], http_client=client), client)
else:
    asyncio.run(load_async())
"""
    environment = {
        **os.environ,
        "LC_ALL": "C",
        "LANG": "C",
        "PYTHONUTF8": "0",
        "PYTHONCOERCECLOCALE": "0",
        "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
    }
    result = subprocess.run(  # noqa: S603 - fixed interpreter and controlled offline probe
        [sys.executable, "-X", "utf8=0", "-c", program, mode, kind, str(chart_dir)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert (chart_dir / "Chart.yaml").read_bytes() == metadata
    assert archive.read_bytes() == data


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["directory", "archive", "repository"])
async def test_explicit_yaml_scalars_keep_metadata_contract(
    chart_dir: Path,
    chart_loader: Callable,
    yaml_scalar_case: tuple[str, bool],
    *,
    kind: str,
    chart_staging: list[Path],
) -> None:
    content, valid = yaml_scalar_case
    metadata = ("name: sample\nversion: 1.0.0\n" + content).encode()
    (chart_dir / "Chart.yaml").write_bytes(metadata)
    archive = chart_dir.parent / "scalar.tgz"
    with tarfile.open(archive, mode="w:gz") as packed:
        packed.add(chart_dir, arcname=chart_dir.name)
    data = archive.read_bytes()
    source = {
        "directory": ChartSource.from_directory(chart_dir),
        "archive": ChartSource.from_archive(archive),
        "repository": ChartSource.from_repository("sample:1.0.0"),
    }[kind]
    calls = []
    respond = repository_response(
        data,
        {
            "name": "sample",
            "version": "1.0.0",
            "urls": ["https://chart.test/chart.tgz", "https://chart.test/fallback.tgz"],
        },
    )

    def response(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return respond(request)

    async with acquisition_client(chart_loader, response) as client:
        if valid:
            chart = await chart_loader(source, http_client=client)
            extra = chart.metadata.model_extra["extra"]
            assert extra == {
                "enabled": True,
                "count": 12,
                "fraction": 1.5,
                "text": "café",
            }
            assert {key: type(value) for key, value in extra.items()} == {
                "enabled": bool,
                "count": int,
                "fraction": float,
                "text": str,
            }
            assert chart.inspect().resource_identities[0].name == "viewer"
        else:
            with pytest.raises(ChartLoadError) as error:
                await chart_loader(source, http_client=client)
            assert (
                error.value.stage,
                error.value.category,
                error.value.source,
            ) == ("metadata", "invalid_metadata", str(source.path or source.selector))
            assert content not in str(error.value)
        assert not client.is_closed
    assert calls == (
        [DEFAULT_REPOSITORY, "https://chart.test/chart.tgz"]
        if kind == "repository"
        else []
    )
    assert ((chart_dir / "Chart.yaml").read_bytes(), archive.read_bytes()) == (
        metadata,
        data,
    )
    assert bool(chart_staging) == (kind != "directory")
    assert all(not path.exists() for path in chart_staging)


@pytest.mark.parametrize("kind", ["directory", "archive"])
def test_invalid_local_path_is_configuration_error(kind: str) -> None:
    with pytest.raises(ValidationError, match="NUL"):
        ChartSource(kind=kind, path="invalid\x00path")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["directory", "archive"])
@pytest.mark.parametrize("direct", [False, True])
async def test_source_links_are_checked_before_reading(
    chart_dir: Path,
    chart_loader: Callable,
    *,
    kind: str,
    direct: bool,
) -> None:
    target = chart_dir
    if kind == "archive":
        target = chart_dir / "source.tgz"
        target.write_bytes(b"caller-owned archive")
    alias = chart_dir.parent / "alias"
    alias.symlink_to(
        target if direct else chart_dir.parent,
        target_is_directory=kind == "directory" or not direct,
    )
    selected = alias if direct else alias / chart_dir.name
    if not direct and kind == "archive":
        selected /= target.name
    before = (chart_dir / "Chart.yaml").read_bytes()
    with pytest.raises(ChartLoadError) as error:
        await chart_loader(ChartSource(kind=kind, path=selected))
    assert error.value.category == "unsafe_path"
    assert error.value.source == str(selected)
    assert (chart_dir / "Chart.yaml").read_bytes() == before
    if kind == "archive":
        assert target.read_bytes() == b"caller-owned archive"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "damage",
    ["metadata_missing", "metadata_sequence", "metadata_multiple", "templates_missing"],
)
async def test_invalid_structure_has_source_boundary(
    chart_dir: Path,
    chart_loader: Callable,
    damage: str,
) -> None:
    if damage == "metadata_missing":
        (chart_dir / "Chart.yaml").unlink()
    elif damage == "templates_missing":
        (chart_dir / "templates/role.yaml").unlink()
        (chart_dir / "templates").rmdir()
    else:
        content = (
            "[]" if damage == "metadata_sequence" else "name: a\nversion: b\n---\n{}"
        )
        (chart_dir / "Chart.yaml").write_text(content)
    with pytest.raises(ChartLoadError) as error:
        await chart_loader(ChartSource.from_directory(chart_dir))
    assert error.value.source == str(chart_dir)
    assert error.value.stage in {"metadata", "source"}


@pytest.mark.asyncio
@pytest.mark.parametrize("layout", ["direct", "ambiguous", "corrupt"])
async def test_archive_layout_and_failure_cleanup(
    chart_dir: Path,
    chart_loader: Callable,
    *,
    layout: str,
    chart_staging: list[Path],
) -> None:
    archive = chart_dir.parent / "layout.tgz"
    _write_layout_archive(chart_dir, archive, layout)
    before = archive.read_bytes()
    if layout == "direct":
        chart = await chart_loader(ChartSource.from_archive(archive))
        assert chart.inspect().resource_identities[0].name == "viewer"
    else:
        with pytest.raises(ChartLoadError) as error:
            await chart_loader(ChartSource.from_archive(archive))
        assert error.value.stage == "archive"
        assert error.value.source == str(archive)
    assert chart_staging
    assert archive.read_bytes() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("namespace", ["values", "secrets"])
@pytest.mark.parametrize("content", [None, "[]", "not: [valid", "unreadable"])
async def test_values_and_secret_failures_keep_original_attribution(
    chart_dir: Path,
    chart_loader: Callable,
    *,
    namespace: str,
    content: str | None,
) -> None:
    path = chart_dir.parent / "input.yaml"
    if content is not None:
        path.write_text(content)
    if content == "unreadable":
        path.chmod(0)
    inputs = ChartInputs(**{namespace: path})
    with pytest.raises(ApplierValidationError) as error:
        await chart_loader(ChartSource.from_directory(chart_dir), inputs=inputs)
    assert error.value.source.path == str(path)
    assert str(chart_dir) in " ".join(error.value.__notes__)
    assert error.value.category == namespace


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["[]", "not: [yaml"])
async def test_needed_bad_defaults_are_not_ignored(
    chart_dir: Path,
    chart_loader: Callable,
    content: str,
) -> None:
    (chart_dir / "values.yaml").write_text(content)
    with pytest.raises(ApplierValidationError) as error:
        await chart_loader(ChartSource.from_directory(chart_dir))
    assert error.value.source.path.endswith("values.yaml")
    assert str(chart_dir) in " ".join(error.value.__notes__)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "expression", ["'x' | nonexistent_filter", "'value' | regex_search('[')"]
)
async def test_filter_errors_keep_template_and_origin(
    chart_dir: Path,
    chart_loader: Callable,
    expression: str,
) -> None:
    (chart_dir / "templates/role.yaml").write_text(
        "kind: Role\nmetadata: {name: viewer}\nspec:\n"
        f'  description: "{{{{ {expression} }}}}"\n  rules: []\n'
    )
    with pytest.raises(ApplierValidationError) as error:
        await chart_loader(ChartSource.from_directory(chart_dir))
    assert error.value.category == "template"
    assert error.value.source.path.endswith("templates/role.yaml")
    assert str(chart_dir) in " ".join(error.value.__notes__)


@pytest.mark.asyncio
async def test_dependency_cycle_retains_apply_identities_and_chart_origin(
    chart_dir: Path,
    chart_loader: Callable,
) -> None:
    documents = [
        {
            "kind": "Deployment",
            "metadata": {"name": name},
            "spec": {"runtime": "cloud", "depends": [{"nameOrGUID": other}]},
        }
        for name, other in [("first", "second"), ("second", "first")]
    ]
    (chart_dir / "templates/role.yaml").write_text(yaml.safe_dump_all(documents))
    with pytest.raises(ApplierValidationError) as error:
        await chart_loader(ChartSource.from_directory(chart_dir))
    assert error.value.category == "dependency_cycle"
    assert {identity.name for identity in error.value.identities} == {"first", "second"}
    assert str(chart_dir) in " ".join(error.value.__notes__)


def _write_layout_archive(chart_dir: Path, archive: Path, layout: str) -> None:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as packed:
        for path in sorted(chart_dir.rglob("*")):
            packed.add(path, arcname=path.relative_to(chart_dir), recursive=False)
        if layout == "ambiguous":
            packed.add(chart_dir, arcname="second")
    archive.write_bytes(
        b"invalid archive" if layout == "corrupt" else stream.getvalue()
    )


@pytest.mark.asyncio
async def test_three_source_kinds_have_identical_prepared_documents(
    chart_dir: Path,
    archive_bytes: Callable,
    chart_loader: Callable,
) -> None:
    (chart_dir / "templates/z.yaml").write_text(
        "kind: Role\nmetadata: {name: second}\nspec: {rules: []}\n"
    )
    results = []
    async with acquisition_client(
        chart_loader, repository_response(archive_bytes(chart_dir))
    ) as client:
        for kind in ["directory", "archive", "repository"]:
            chart = await chart_loader(
                bundle_source(chart_dir, archive_bytes, kind), http_client=client
            )
            results.append(
                (
                    [doc.data for doc in chart.inspect().rendered_documents],
                    chart.template_paths,
                )
            )
            assert chart.metadata.name == "sample"
        assert not client.is_closed
    assert results[0] == results[1] == results[2]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "status",
        "timeout",
        "network",
        "no_url",
        "empty_url",
        "relative_url",
        "bad_archive",
    ],
)
async def test_first_package_failure_has_no_retry_or_fallback(
    chart_loader: Callable,
    failure: str,
    chart_staging: list[Path],
) -> None:
    calls = []
    response = _failing_package_response(failure, calls)
    async with acquisition_client(chart_loader, response) as client:
        with pytest.raises(ChartLoadError) as error:
            await chart_loader(
                ChartSource.from_repository("sample:1.0.0", branch="feature"),
                http_client=client,
            )
        assert not client.is_closed
    expected = "archive" if failure == "bad_archive" else "download"
    assert error.value.stage == expected
    assert len(calls) == (1 if failure.endswith("url") else 2)
    assert all("second" not in url for url in calls)
    assert bool(chart_staging) == (failure == "bad_archive")


def _failing_package_response(failure: str, calls: list) -> Callable:
    urls = {
        "no_url": [],
        "empty_url": ["", "https://chart.test/second.tgz"],
        "relative_url": ["relative.tgz", "https://chart.test/second.tgz"],
    }.get(failure, ["https://chart.test/first.tgz", "https://chart.test/second.tgz"])
    entry = {"name": "sample", "version": "1.0.0", "urls": urls}
    original = repository_response(b"not a tar archive", entry)

    def response(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path.endswith("yaml"):
            return original(request)
        if failure == "timeout":
            msg = "controlled timeout"
            raise httpx.ReadTimeout(msg, request=request)
        if failure == "network":
            msg = "controlled failure"
            raise httpx.ConnectError(msg, request=request)
        return (
            httpx.Response(500, request=request)
            if failure == "status"
            else original(request)
        )

    return response


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["status", "bad_archive"])
async def test_owned_acquisition_transport_closes_on_failure(
    chart_loader: Callable,
    monkeypatch: pytest.MonkeyPatch,
    *,
    failure: str,
    chart_staging: list[Path],
) -> None:
    clients = []
    kind = httpx.Client if chart_loader.chart_type is Chart else httpx.AsyncClient
    response = _failing_package_response(failure, [])

    class OwnedClient(kind):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(transport=httpx.MockTransport(response), **kwargs)
            clients.append(self)

    monkeypatch.setattr(httpx, kind.__name__, OwnedClient)
    with pytest.raises(ChartLoadError):
        await chart_loader(ChartSource.from_repository("sample:1.0.0"))
    assert clients
    assert all(client.is_closed for client in clients)
    assert bool(chart_staging) == (failure == "bad_archive")


@pytest.mark.asyncio
async def test_platform_clients_cannot_be_used_for_acquisition(
    chart_loader: Callable,
) -> None:
    async with platform_client(chart_loader, PlatformRecorder(None)) as client:
        with pytest.raises(ApplierUsageError):
            await chart_loader(
                ChartSource.from_repository("sample"), http_client=client
            )


@pytest.mark.asyncio
async def test_opposite_http_mode_is_rejected_before_requests(
    chart_loader: Callable,
) -> None:
    opposite = SimpleNamespace(
        chart_type=AsyncChart if chart_loader.chart_type is Chart else Chart
    )

    def forbidden(_request: httpx.Request) -> httpx.Response:
        msg = "request before usage validation"
        raise AssertionError(msg)

    async with acquisition_client(opposite, forbidden) as client:
        with pytest.raises(ApplierUsageError):
            await chart_loader(
                ChartSource.from_repository("sample"), http_client=client
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["archive", "repository"])
async def test_truncated_gzip_has_archive_error_and_releases_staging(
    chart_dir: Path,
    archive_bytes: Callable,
    chart_loader: Callable,
    *,
    kind: str,
    chart_staging: list[Path],
) -> None:
    (chart_dir / "asset.bin").write_bytes(
        hashlib.shake_256(b"deterministic chart asset").digest(32768)
    )
    data = archive_bytes(chart_dir)
    truncated = data[: len(data) // 2]
    archive = chart_dir.parent / "truncated.tgz"
    archive.write_bytes(truncated)
    source = (
        ChartSource.from_archive(archive)
        if kind == "archive"
        else ChartSource.from_repository("sample:1.0.0")
    )
    async with acquisition_client(
        chart_loader, repository_response(truncated)
    ) as client:
        with pytest.raises(ChartLoadError) as error:
            await chart_loader(source, http_client=client)
        assert not client.is_closed
    assert error.value.stage == "archive"
    assert error.value.category == "invalid_archive"
    assert error.value.source == str(source.path or source.selector)
    assert archive.read_bytes() == truncated
    assert chart_staging


def _chart_tar(*, large_asset: bool = True, asset_size: int = 32768) -> bytes:
    stream = io.BytesIO()
    members = [
        ("sample/Chart.yaml", b"name: sample\nversion: 1.0.0\n"),
        ("sample/values.yaml", b"{}\n"),
        (
            "sample/templates/role.yaml",
            b"kind: Role\nmetadata: {name: viewer}\nspec: {rules: []}\n",
        ),
    ]
    if large_asset:
        members.insert(
            0,
            ("sample/assets.bin", hashlib.shake_256(b"chart asset").digest(asset_size)),
        )
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, content in members:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    return stream.getvalue()


def _gzip_with_corrupt_later_block() -> tuple[bytes, bytes]:
    raw = _chart_tar()
    compressor = zlib.compressobj(wbits=-15)
    prefix = compressor.compress(raw[:16384]) + compressor.flush(zlib.Z_FULL_FLUSH)
    suffix = compressor.compress(raw[16384:]) + compressor.flush()
    header = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff"
    trailer = struct.pack("<II", zlib.crc32(raw), len(raw))
    # A full flush establishes a block boundary beyond gzip's initial read buffer.
    # Reserved BTYPE=3 damages the later block while preserving the valid prefix.
    damaged = bytes([suffix[0] | 6]) + suffix[1:]
    return header + prefix + suffix + trailer, header + prefix + damaged + trailer


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["archive", "repository"])
@pytest.mark.parametrize("damage", [False, True])
async def test_later_gzip_block_corruption_keeps_chart_boundary(
    chart_dir: Path,
    chart_loader: Callable,
    *,
    kind: str,
    damage: bool,
    chart_staging: list[Path],
) -> None:
    valid, corrupt = _gzip_with_corrupt_later_block()
    data = corrupt if damage else valid
    archive = chart_dir.parent / "late-block.tgz"
    archive.write_bytes(data)
    source = (
        ChartSource.from_archive(archive)
        if kind == "archive"
        else ChartSource.from_repository("sample:1.0.0")
    )
    requested = []
    respond = repository_response(
        data,
        {
            "name": "sample",
            "version": "1.0.0",
            "urls": [
                "https://chart.test/chart.tgz",
                "https://chart.test/fallback.tgz",
            ],
        },
    )

    def response(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return respond(request)

    async with acquisition_client(chart_loader, response) as client:
        if damage:
            with pytest.raises(ChartLoadError) as error:
                await chart_loader(source, http_client=client)
            assert error.value.stage == "archive"
            assert error.value.category == "invalid_archive"
            assert error.value.source == str(source.path or source.selector)
        else:
            chart = await chart_loader(source, http_client=client)
            assert chart.metadata.name == "sample"
            assert chart.inspect().resource_identities[0].name == "viewer"
        assert not client.is_closed
    assert requested == (
        [DEFAULT_REPOSITORY, "https://chart.test/chart.tgz"]
        if kind == "repository"
        else []
    )
    assert archive.read_bytes() == data
    assert chart_staging


def _concatenated_compression(compress: Callable) -> tuple[bytes, bytes]:
    raw = _chart_tar()
    first = compress(raw[:16384])
    second = compress(raw[16384:])
    offset = len(second) // 2
    damaged = second[:offset] + bytes([second[offset] ^ 1]) + second[offset + 1 :]
    return first + second, first + damaged


def _damaged_compression_footer(data: bytes, state: str, offset: int) -> bytes:
    if state.startswith("truncated"):
        return data[:-1]
    if state.startswith("corrupt"):
        damaged = bytearray(data)
        damaged[offset] ^= 1
        return bytes(damaged)
    return data


def _footer_compression(codec: str, state: str) -> bytes:
    compress, decompress, checksum_offset = {
        "gzip": (gzip.compress, gzip.decompress, -8),
        "bzip2": (bz2.compress, bz2.decompress, -2),
        "xz": (lzma.compress, lzma.decompress, -9),
    }[codec]
    valid = compress(_chart_tar(large_asset=False))
    # A second stream follows the complete tar, including its end markers.
    prefix = b""
    if "concatenated" in state:
        prefix, valid = valid, compress(bytes(1024))
    if "padded" in state:
        return (prefix + bytes(4) if prefix else b"") + valid + bytes(4)
    valid = _damaged_compression_footer(valid, state, checksum_offset)
    if not state.startswith("valid"):
        with pytest.raises((EOFError, OSError, ValueError, lzma.LZMAError)):
            decompress(valid)
    return prefix + valid


def _zstandard_compression(state: str) -> bytes:
    zstd = pytest.importorskip("compression.zstd")
    valid = zstd.compress(
        _chart_tar(asset_size=1024 * 1024),
        options={zstd.CompressionParameter.checksum_flag: 1},
    )
    data = _damaged_compression_footer(valid, state, -1)
    if state != "valid":
        with pytest.raises(zstd.ZstdError):
            zstd.decompress(data)
    return data


@pytest.fixture(
    params=[
        (codec, state)
        for codec in ["gzip", "bzip2", "xz"]
        for state in [
            "valid",
            "truncated",
            "corrupt",
            "valid-footer",
            "truncated-footer",
            "corrupt-footer",
            "valid-concatenated-footer",
            "truncated-concatenated-footer",
            "corrupt-concatenated-footer",
        ]
    ]
    + [
        ("xz", "valid-padded-footer"),
        ("xz", "valid-padded-concatenated-footer"),
    ]
    + [("zstd", state) for state in ["valid", "truncated", "corrupt"]],
    ids="-".join,
)
def compressed_package(request: pytest.FixtureRequest) -> tuple[str, str, bytes]:
    codec, state = request.param
    if codec == "zstd":
        return codec, state, _zstandard_compression(state)
    if state.endswith("footer"):
        return codec, state, _footer_compression(codec, state)
    builders = {
        "gzip": _gzip_with_corrupt_later_block,
        "bzip2": lambda: _concatenated_compression(bz2.compress),
        "xz": lambda: _concatenated_compression(lzma.compress),
    }
    valid, corrupt = builders[codec]()
    cases = {"valid": valid, "truncated": valid[: len(valid) // 2], "corrupt": corrupt}
    return codec, state, cases[state]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["archive", "repository"])
async def test_supported_compressed_formats_share_error_contract(
    chart_dir: Path,
    chart_loader: Callable,
    compressed_package: tuple[str, str, bytes],
    *,
    kind: str,
    chart_staging: list[Path],
) -> None:
    codec, state, data = compressed_package
    archive = chart_dir.parent / f"chart-{codec}.tar"
    archive.write_bytes(data)
    source = (
        ChartSource.from_archive(archive)
        if kind == "archive"
        else ChartSource.from_repository("sample:1.0.0")
    )
    requested = []
    respond = repository_response(
        data,
        {
            "name": "sample",
            "version": "1.0.0",
            "urls": ["https://chart.test/chart.tgz", "https://chart.test/fallback.tgz"],
        },
    )

    def response(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return respond(request)

    async with acquisition_client(chart_loader, response) as client:
        if state.startswith("valid"):
            chart = await chart_loader(source, http_client=client)
            assert chart.metadata.name == "sample"
            assert chart.inspect().resource_identities[0].name == "viewer"
        else:
            with pytest.raises(ChartLoadError) as error:
                await chart_loader(source, http_client=client)
            assert error.value.stage == "archive"
            assert error.value.category == "invalid_archive"
            assert error.value.source == str(source.path or source.selector)
        assert not client.is_closed
    assert requested == (
        [DEFAULT_REPOSITORY, "https://chart.test/chart.tgz"]
        if kind == "repository"
        else []
    )
    assert archive.read_bytes() == data
    assert chart_staging
    assert all(not path.exists() for path in chart_staging)


@pytest.fixture(params=["1.5", "1e30", "-1e30", "nan", "inf", "-inf"])
def archive_timestamp_package(request: pytest.FixtureRequest) -> tuple[str, bytes]:
    timestamp = request.param
    stream = io.BytesIO()
    with (
        tarfile.open(
            fileobj=io.BytesIO(_chart_tar(large_asset=False)), mode="r:"
        ) as raw,
        tarfile.open(fileobj=stream, mode="w:gz", format=tarfile.PAX_FORMAT) as archive,
    ):
        for member in raw:
            member.pax_headers = {"mtime": timestamp}
            archive.addfile(member, raw.extractfile(member))
    return timestamp, stream.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["archive", "repository"])
async def test_invalid_archive_timestamps_keep_chart_boundary(
    chart_dir: Path,
    chart_loader: Callable,
    archive_timestamp_package: tuple[str, bytes],
    *,
    kind: str,
    chart_staging: list[Path],
) -> None:
    timestamp, data = archive_timestamp_package
    archive = chart_dir.parent / "timestamp.tgz"
    archive.write_bytes(data)
    source = (
        ChartSource.from_archive(archive)
        if kind == "archive"
        else ChartSource.from_repository("sample:1.0.0")
    )
    calls = []
    respond = repository_response(
        data,
        {
            "name": "sample",
            "version": "1.0.0",
            "urls": ["https://chart.test/chart.tgz", "https://chart.test/fallback.tgz"],
        },
    )

    def response(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return respond(request)

    async with acquisition_client(chart_loader, response) as client:
        if timestamp == "1.5":
            chart = await chart_loader(source, http_client=client)
            assert chart.inspect().resource_identities[0].name == "viewer"
        else:
            with pytest.raises(ChartLoadError) as error:
                await chart_loader(source, http_client=client)
            assert error.value.stage == "archive"
            assert error.value.category == "invalid_archive"
            assert error.value.source == str(source.path or source.selector)
        assert not client.is_closed
    assert calls == (
        [DEFAULT_REPOSITORY, "https://chart.test/chart.tgz"]
        if kind == "repository"
        else []
    )
    assert archive.read_bytes() == data
    assert chart_staging
    assert all(not path.exists() for path in chart_staging)
