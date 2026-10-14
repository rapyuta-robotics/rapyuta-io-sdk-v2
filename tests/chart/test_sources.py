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

"""Typed source configuration and caller-data isolation."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from rapyuta_io_sdk_v2.apply.applier import Applier
from rapyuta_io_sdk_v2.apply.errors import ApplierValidationError
from rapyuta_io_sdk_v2.apply.source import ManifestSource
from rapyuta_io_sdk_v2.chart import ChartInputs, ChartLoadError, ChartVersionWarning
from rapyuta_io_sdk_v2.models.chart import (
    ChartEntry,
    ChartIndex,
    ChartMetadata,
    ChartSource,
)


@pytest.mark.parametrize("selector", ["", ":1", "name:", "name:1:2"])
def test_invalid_selectors_are_rejected_without_io(selector: str) -> None:
    with pytest.raises(ValidationError):
        ChartSource.from_repository(selector)


def test_source_tags_and_fields_are_coherent() -> None:
    source = ChartSource.from_directory("missing")
    assert source.path == Path("missing")
    assert source.kind == "directory"
    with pytest.raises(ValidationError):
        ChartSource(kind="directory", path="x", selector="name")
    with pytest.raises(ValidationError):
        ChartSource(kind="repository", selector="name", path="x")


@pytest.mark.parametrize("value", ["", " ", 1, True])
def test_metadata_identity_is_strict(value: object) -> None:
    with pytest.raises(ValidationError):
        ChartMetadata(name=value, version="1")
    with pytest.raises(ValidationError):
        ChartMetadata(name="sample", version=value)


def test_metadata_aliases_extra_fields_and_timestamps() -> None:
    metadata = ChartMetadata(
        name="sample", version="1", apiVersion="v1", appVersion="2"
    )
    assert metadata.api_version == "v1"
    assert metadata.model_dump(by_alias=True)["appVersion"] == "2"
    instant = datetime(2026, 1, 1, tzinfo=UTC)
    entry = ChartEntry(name="sample", version="1", created=instant)
    index = ChartIndex(entries={"sample": [entry, entry]}, generated=instant)
    assert index.entries["sample"] == (entry, entry)
    assert index.generated == instant
    assert ChartIndex(entries={}).entries == {}
    with pytest.raises(ValidationError):
        ChartIndex(entries={"other": [entry]})


def test_inputs_snapshot_iterables_and_nested_mappings() -> None:
    values = {"nested": {"name": "before"}}
    inputs = ChartInputs(values=(source for source in [values]), secrets={"token": "a"})
    values["nested"]["name"] = "after"
    assert inputs.values == ({"nested": {"name": "before"}},)
    assert ChartInputs(values={}).values == ({},)
    assert ChartInputs(values=None).values == ()
    assert inputs.secrets == ({"token": "a"},)


def test_error_contract_does_not_retain_bodies() -> None:
    error = ChartLoadError("download", "http", "https://example.test/chart")
    assert error.stage == "download"
    assert error.category == "http"
    assert error.source == "https://example.test/chart"
    assert isinstance(ChartVersionWarning("sample"), UserWarning)


@pytest.mark.asyncio
async def test_inputs_render_reserved_context_and_all_merge_rules(
    chart_dir: Path,
    chart_loader: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        msg = "implicit secret decryption"
        raise AssertionError(msg)

    monkeypatch.setattr("rapyuta_io_sdk_v2.decrypt_secret_file", forbidden)
    monkeypatch.setattr("rapyuta_io_sdk_v2.async_decrypt_secret_file", forbidden)
    values = [
        {
            "name": "first",
            "nested": {"a": 1},
            "items": [1, 2],
            "scalar": 1,
            "rio": {"org": "wrong"},
            "secrets": {"token": "wrong"},
        },
        {"name": "second", "nested": {"b": 2}, "items": [3], "scalar": "4"},
    ]
    plain = chart_dir.parent / "plain.yaml"
    plain.write_text("token: plain\n")
    inputs = ChartInputs(
        values=values, secrets=[plain, {"token": "decrypted"}], rio={"org": "chosen"}
    )
    _context_template(chart_dir / "templates/role.yaml")
    chart = await chart_loader(ChartSource.from_directory(chart_dir), inputs=inputs)
    direct = Applier(
        ManifestSource(
            files=[chart_dir / "templates/role.yaml"],
            values=values,
            secrets=[plain, {"token": "decrypted"}],
            rio={"org": "chosen"},
        )
    )
    assert chart.inspect().rendered_documents == direct.inspect().rendered_documents
    document = chart.inspect().rendered_documents[0].data
    assert document["metadata"]["name"] == "second-chosen-decrypted"
    assert json.loads(document["spec"]["description"]) == {
        "nested": {"a": 1, "b": 2},
        "items": [3],
        "scalar": 4,
    }
    assert values[0]["nested"] == {"a": 1}


def _context_template(path: Path) -> None:
    path.write_text(
        "kind: Role\nmetadata:\n"
        "  name: '{{ name }}-{{ rio.org }}-{{ secrets.token }}'\nspec:\n"
        '  description: \'{{ {"nested": nested, "items": items, '
        '"scalar": scalar | int} | to_json }}\'\n'
        "  rules: []\n"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("values", [None, [], {}])
async def test_both_modes_distinguish_defaults_and_explicit_empty(
    chart_dir: Path,
    chart_loader: object,
    values: object,
) -> None:
    if values == {}:
        with pytest.raises(ApplierValidationError):
            await chart_loader(
                ChartSource.from_directory(chart_dir), inputs=ChartInputs(values=values)
            )
    else:
        chart = await chart_loader(
            ChartSource.from_directory(chart_dir), inputs=ChartInputs(values=values)
        )
        assert chart.inspect().resource_identities[0].name == "viewer"


@pytest.mark.asyncio
@pytest.mark.parametrize("absent", [False, True])
async def test_both_modes_exclude_unused_defaults(
    chart_dir: Path,
    chart_loader: object,
    *,
    absent: bool,
) -> None:
    if absent:
        (chart_dir / "values.yaml").unlink()
    else:
        (chart_dir / "values.yaml").write_text("unused: [invalid")
    chart = await chart_loader(
        ChartSource.from_directory(chart_dir),
        inputs=ChartInputs(values={"name": "explicit"}),
    )
    assert chart.inspect().resource_identities[0].name == "explicit"


@pytest.mark.asyncio
@pytest.mark.parametrize("values", [None, {}])
async def test_empty_mapping_is_valid_when_template_needs_no_values(
    chart_dir: Path,
    chart_loader: object,
    values: object,
) -> None:
    (chart_dir / "values.yaml").write_text(
        "{}" if values is None else "unused: [invalid"
    )
    (chart_dir / "templates/role.yaml").write_text(
        "kind: Role\nmetadata: {name: constant}\nspec: {rules: []}\n"
    )
    chart = await chart_loader(
        ChartSource.from_directory(chart_dir), inputs=ChartInputs(values=values)
    )
    assert chart.inspect().resource_identities[0].name == "constant"
