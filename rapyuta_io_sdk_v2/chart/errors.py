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

"""Source-attributed chart acquisition failures and version-selection warnings."""

from typing import Literal

type ChartStage = Literal["source", "index", "download", "archive", "metadata"]


class ChartError(Exception):
    """Base exception for chart acquisition rather than resource execution."""


class ChartLoadError(ChartError):
    """Acquisition error without retained HTTP bodies or decoded input contents."""

    def __init__(
        self,
        stage: ChartStage,
        category: str,
        source: str,
        *,
        selector: str | None = None,
    ) -> None:
        """Identify the failed stage, source, category, and optional chart selector."""
        self.stage = stage
        self.category = category
        self.source = source
        self.selector = selector
        super().__init__(f"chart {stage} {category}: {source}")


class ChartVersionWarning(UserWarning):
    """Unversioned selection found several entries and chose the first."""
