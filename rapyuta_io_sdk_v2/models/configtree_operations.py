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

"""Options and logical content types for configuration tree workflows."""

from datetime import date, datetime

from pydantic import ConfigDict

from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.configtree import ConfigTreeRevision

type ConfigContent = (
    str
    | int
    | float
    | bool
    | date
    | datetime
    | list[ConfigContent]
    | dict[str, ConfigContent]
    | None
)


class RevisionOptions(SDKModel):
    """Frozen revision scope, commit choice, and optional commit payload."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)
    with_project: bool = True
    commit: bool = False
    commit_body: ConfigTreeRevision | None = None


class ImportOptions(RevisionOptions):
    """Revision options with independent head selection."""

    update_head: bool = False


class MergeOptions(SDKModel):
    """Merge scope and optional commit payload; merge always publishes."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)
    with_project: bool = True
    commit_body: ConfigTreeRevision | None = None
