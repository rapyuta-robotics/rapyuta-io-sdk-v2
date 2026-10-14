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

"""Independent inspection and diagnostics survive package cleanup and caller edits."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from rapyuta_io_sdk_v2 import ApplierValidationError
from rapyuta_io_sdk_v2.chart import Chart, ChartSource

if TYPE_CHECKING:
    from collections.abc import Callable


def test_inspection_is_independent_and_prepared_data_survives_edits(
    chart_dir: Path,
) -> None:
    chart = Chart.load(ChartSource.from_directory(chart_dir))
    first = chart.inspect()
    first.resolved_manifests[0].metadata.name = "changed"
    first.rendered_documents[0].data["metadata"]["name"] = "changed"
    (chart_dir / "templates/role.yaml").unlink()
    assert chart.inspect().resolved_manifests[0].metadata.name == "viewer"
    assert chart.inspect().rendered_documents[0].data["metadata"]["name"] == "viewer"
    assert chart.apply(dry_run=True).successful


def test_archive_releases_staging_directory_before_return(
    chart_dir: Path, archive_bytes: Callable, tmp_path: Path
) -> None:
    archive = tmp_path / "sample.tgz"
    archive.write_bytes(archive_bytes(chart_dir))
    chart = Chart.load(ChartSource.from_archive(archive))
    source_path = Path(chart.inspect().rendered_documents[0].source.path)
    assert not source_path.exists()
    assert chart.source.path == archive
    assert chart.template_paths == ("templates/role.yaml",)


def test_archive_template_failure_preserves_apply_error_with_origin_note(
    chart_dir: Path, archive_bytes: Callable, tmp_path: Path
) -> None:
    (chart_dir / "templates/role.yaml").write_text(
        "kind: Role\nmetadata: {name: '{{ absent }}'}\nspec: {rules: []}\n"
    )
    archive = tmp_path / "sample.tgz"
    archive.write_bytes(archive_bytes(chart_dir))
    with pytest.raises(ApplierValidationError) as error:
        Chart.load(ChartSource.from_archive(archive))
    assert error.value.category == "template"
    assert "templates/role.yaml" in error.value.source.path
    notes = " ".join(error.value.__notes__)
    assert str(archive) in notes
    assert "templates/role.yaml" in notes
    assert not Path(error.value.source.path).exists()


def test_metadata_extra_snapshots_are_independent(chart_dir: Path) -> None:
    (chart_dir / "Chart.yaml").write_text(
        "name: sample\nversion: 1.0.0\nmaintainers: [{name: first}]\n"
    )
    chart = Chart.load(ChartSource.from_directory(chart_dir))
    chart.metadata.maintainers[0]["name"] = "changed"
    assert chart.metadata.maintainers[0]["name"] == "first"
