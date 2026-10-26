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


from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict

from rapyuta_io_sdk_v2 import Configuration
from rapyuta_io_sdk_v2.pydantic_source import ConfigTreeSource

if TYPE_CHECKING:
    from pathlib import Path


class TreeSettings(BaseSettings):
    """Accept the complete configuration tree for settings source verification."""

    model_config = SettingsConfigDict(extra="allow")


@pytest.mark.parametrize("file_format", ["json", "yaml"])
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"value": "setting", "metadata": {}}, "setting"),
        (
            {"value": "setting", "metadata": None},
            {"value": "setting", "metadata": None},
        ),
        (
            {"value": "setting", "metadata": {"revision": "1"}, "other": "retained"},
            {"value": "setting", "metadata": {"revision": "1"}, "other": "retained"},
        ),
    ],
)
def test_config_tree_source_unwraps_only_metadata_wrappers(
    *,
    tmp_path: Path,
    value: dict[str, Any],
    expected: object,
    file_format: str,
) -> None:
    # JSON content is valid YAML, so exercise both decoders with the same payload.
    path = tmp_path / f"settings.{file_format}"
    path.write_text(json.dumps({"entry": value}), encoding="utf-8")
    source = ConfigTreeSource(TreeSettings, Configuration(), local_file=str(path))
    assert source()["settings"]["entry"] == expected
