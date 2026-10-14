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


"""Exact scoped UserGroup GUID lookup for lifecycle methods."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rapyuta_io_sdk_v2.apply._resources.standard import organization_options

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.models.applier import ResourceContext
    from rapyuta_io_sdk_v2.models.usergroup import UserGroup


def _one_usergroup_guid(items: list[UserGroup]) -> str | None:
    if len(items) > 1:
        msg = "UserGroup lookup returned multiple exact matches"
        raise ValueError(msg)
    return items[0].metadata.guid if items else None


def resolve_usergroup_guid(
    client: Client, resource: UserGroup, context: ResourceContext
) -> str | None:
    if resource.metadata.guid is not None:
        return resource.metadata.guid
    items: list[UserGroup] = []
    continuation = 0
    seen: set[int] = set()
    while True:
        page = client.list_user_groups(
            cont=continuation,
            limit=50,
            name=resource.metadata.name,
            **organization_options(context),
        )
        items.extend(
            item
            for item in page.items or []
            if item.metadata.name == resource.metadata.name
            and item.metadata.organization_guid == context.scope.organization_guid
        )
        token = page.metadata.continue_ if page.metadata is not None else None
        if token is None:
            break
        if token in seen:
            msg = "UserGroup lookup repeated a continuation token"
            raise ValueError(msg)
        seen.add(token)
        continuation = token
    return _one_usergroup_guid(items)


async def resolve_usergroup_guid_async(
    client: AsyncClient, resource: UserGroup, context: ResourceContext
) -> str | None:
    if resource.metadata.guid is not None:
        return resource.metadata.guid
    items: list[UserGroup] = []
    continuation = 0
    seen: set[int] = set()
    while True:
        page = await client.list_user_groups(
            cont=continuation,
            limit=50,
            name=resource.metadata.name,
            **organization_options(context),
        )
        items.extend(
            item
            for item in page.items or []
            if item.metadata.name == resource.metadata.name
            and item.metadata.organization_guid == context.scope.organization_guid
        )
        token = page.metadata.continue_ if page.metadata is not None else None
        if token is None:
            break
        if token in seen:
            msg = "UserGroup lookup repeated a continuation token"
            raise ValueError(msg)
        seen.add(token)
        continuation = token
    return _one_usergroup_guid(items)
