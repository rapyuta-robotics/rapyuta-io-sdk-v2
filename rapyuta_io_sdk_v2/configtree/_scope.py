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

"""Immutable request scope captured from the caller's configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rapyuta_io_sdk_v2.configtree.exceptions import ReferenceReason, reference_error

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2 import AsyncClient, Client


@dataclass(frozen=True)
class Scope:
    """Organization and optional project identity for every request."""

    organization_guid: str
    project_guid: str | None
    with_project: bool

    @classmethod
    def capture(cls, client: Client | AsyncClient, *, with_project: bool) -> Scope:
        """Snapshot configured IDs, rejecting missing selected context."""
        organization = client.config.organization_guid
        project = client.config.project_guid if with_project else None
        if not _present(organization) or (with_project and not _present(project)):
            raise reference_error(
                ReferenceReason.REQUIRED_CONFIGURATION_TREE_SCOPE_IS_MISSING
            )
        return cls(organization, project, with_project)

    def headers(self) -> dict[str, str | bool | None]:
        """Return explicit per-call header options."""
        return {
            "organization_guid": self.organization_guid,
            "project_guid": self.project_guid,
            "with_project": self.with_project,
        }


def _present(guid: str | None) -> bool:
    return isinstance(guid, str) and bool(guid.strip())
