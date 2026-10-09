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

"""Shared keyword option types for synchronous and asynchronous clients."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from rapyuta_io_sdk_v2.config import RequestHeaderOptions

if TYPE_CHECKING:
    import httpx


class ClientOptions(TypedDict, total=False):
    """HTTP client construction options."""

    timeout: (
        float
        | tuple[float | None, float | None, float | None, float | None]
        | httpx.Timeout
        | None
    )


class OrganizationHeaderOptions(RequestHeaderOptions, total=False):
    """Organization and group options for requests with explicit project context."""

    with_organization: bool
    organization_guid: str | None
    with_group: bool
    group_guid: str | None


class ProjectHeaderOptions(OrganizationHeaderOptions, total=False):
    """Header options for requests that set the project inclusion flag."""

    project_guid: str | None


class HeaderOptions(ProjectHeaderOptions, total=False):
    """All supported request header options."""

    with_project: bool


class ProjectOverrideHeaderOptions(OrganizationHeaderOptions, total=False):
    """Header options for requests with an explicit project GUID."""

    with_project: bool


class OrganizationOverrideHeaderOptions(RequestHeaderOptions, total=False):
    """Header options for organization requests with an explicit GUID."""

    with_organization: bool
    project_guid: str | None
    with_group: bool
    group_guid: str | None


class IdentityHeaderOptions(RequestHeaderOptions, total=False):
    """Header options for requests that omit organization and project context."""

    organization_guid: str | None
    project_guid: str | None
    with_group: bool
    group_guid: str | None


class GroupHeaderOptions(RequestHeaderOptions, total=False):
    """Header options for requests with an explicit group context."""

    with_organization: bool
    organization_guid: str | None
    project_guid: str | None
