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

"""Parse and resolve scoped configuration tree source references."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from rapyuta_io_sdk_v2.configtree.exceptions import ReferenceReason, reference_error

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2 import AsyncClient, Client
    from rapyuta_io_sdk_v2.configtree._scope import Scope
    from rapyuta_io_sdk_v2.models.configtree import ConfigTree, ConfigValue

_SELECTED_COMPONENTS = 3


class ConfigTreeRef(NamedTuple):
    """Immutable source scope, tree, revision ID, and milestone."""

    is_org: bool
    tree_name: str
    revision_id: str | None
    milestone: str | None


def parse_refspec(refspec: str) -> ConfigTreeRef:
    """Parse an organization or project tree reference.

    Args:
        refspec: ``org/tree`` or ``proj/tree`` with an optional revision ID or
            milestone selector.

    Returns:
        Immutable scope, tree, revision ID, and milestone fields.

    Raises:
        ConfigTreeReferenceError: If the grammar or a component is invalid.
    """
    if not isinstance(refspec, str):
        raise reference_error(ReferenceReason.INVALID_CONFIGURATION_REFERENCE)
    parts = refspec.split("/")
    if (
        len(parts) not in (2, _SELECTED_COMPONENTS)
        or parts[0] not in ("org", "proj")
        or any(not part or not part.strip() or part != part.strip() for part in parts)
    ):
        raise reference_error(
            ReferenceReason.INVALID_CONFIGURATION_REFERENCE, refspec=refspec
        )
    selector = parts[2] if len(parts) == _SELECTED_COMPONENTS else None
    return ConfigTreeRef(
        parts[0] == "org",
        parts[1],
        selector if selector and selector.startswith("rev-") else None,
        selector if selector and not selector.startswith("rev-") else None,
    )


def revision_guid(tree: ConfigTree) -> str:
    """Get selected revision identity from a typed tree response."""
    guid = tree.head.metadata.guid if tree.head and tree.head.metadata else None
    if not guid:
        raise reference_error(
            ReferenceReason.SELECTED_CONFIGURATION_REVISION_IS_MISSING
        )
    return guid


def require_parent(tree: ConfigTree) -> str:
    """Require a usable committed selected head for inheritance."""
    guid = revision_guid(tree)
    if tree.head.committed is not True:
        raise reference_error(ReferenceReason.SELECTED_PARENT_REVISION_IS_UNCOMMITTED)
    return guid


def require_key_map(tree: ConfigTree) -> dict[str, ConfigValue]:
    """Require the complete key map requested with ``include_data=True``."""
    if tree.keys is None:
        raise reference_error(ReferenceReason.SELECTED_CONFIGURATION_KEY_MAP_IS_MISSING)
    return tree.keys


def _candidate_id(item: object, milestone: str) -> str | None:
    metadata = item.metadata
    if (
        not metadata
        or not metadata.labels
        or metadata.labels.get("rapyuta.io/milestone") != milestone
    ):
        return None
    if not metadata.guid:
        raise reference_error(ReferenceReason.MILESTONE_REVISION_HAS_NO_GUID)
    return metadata.guid


def _page_ids(
    page: object, milestone: str, matches: set[str], *, offset: int
) -> int | None:
    if page.items is None:
        raise reference_error(ReferenceReason.INVALID_MILESTONE_CONTINUATION)
    for item in page.items:
        guid = _candidate_id(item, milestone)
        if guid:
            matches.add(guid)
    if len(matches) > 1:
        raise reference_error(ReferenceReason.MILESTONE_MATCHES_MULTIPLE_REVISIONS)
    return _continuation(page, offset)


def _continuation(page: object, offset: int) -> int | None:
    token = page.metadata.continue_ if page.metadata else None
    if token is None:
        return None
    if type(token) is not int:
        raise reference_error(ReferenceReason.INVALID_MILESTONE_CONTINUATION)
    if token == 0:
        return None
    if token <= offset:
        raise reference_error(ReferenceReason.INVALID_MILESTONE_CONTINUATION)
    return token


def _selected(tree: ConfigTree, requested: str | None) -> ConfigTree:
    guid = revision_guid(tree)
    if requested and guid != requested:
        raise reference_error(ReferenceReason.SELECTED_REVISION_IDENTITY_DOES_NOT_MATCH)
    require_key_map(tree)
    return tree


def _milestone_sync(client: Client, ref: ConfigTreeRef, scope: Scope) -> str:
    offset = 0
    matches: set[str] = set()
    while True:
        page = client.list_revisions(
            ref.tree_name,
            cont=offset,
            committed=False,
            label_selector=[f"rapyuta.io/milestone={ref.milestone}"],
            **scope.headers(),
        )
        token = _page_ids(page, ref.milestone, matches, offset=offset)
        if token is None:
            break
        offset = token
    if not matches:
        raise reference_error(ReferenceReason.MILESTONE_MATCHES_NO_REVISIONS)
    return next(iter(matches))


async def _milestone_async(
    client: AsyncClient, ref: ConfigTreeRef, scope: Scope
) -> str:
    offset = 0
    matches: set[str] = set()
    while True:
        page = await client.list_revisions(
            ref.tree_name,
            cont=offset,
            committed=False,
            label_selector=[f"rapyuta.io/milestone={ref.milestone}"],
            **scope.headers(),
        )
        token = _page_ids(page, ref.milestone, matches, offset=offset)
        if token is None:
            break
        offset = token
    if not matches:
        raise reference_error(ReferenceReason.MILESTONE_MATCHES_NO_REVISIONS)
    return next(iter(matches))


def resolve_source(client: Client, ref: ConfigTreeRef, scope: Scope) -> ConfigTree:
    """Resolve a source head, explicit revision, or unique milestone."""
    requested = (
        _milestone_sync(client, ref, scope) if ref.milestone else ref.revision_id
    )
    tree = client.get_configtree(
        ref.tree_name,
        revision=requested,
        include_data=True,
        content_types=["kv"],
        **scope.headers(),
    )
    return _selected(tree, requested)


async def resolve_source_async(
    client: AsyncClient, ref: ConfigTreeRef, scope: Scope
) -> ConfigTree:
    """Await the same source selection rules as synchronous resolution."""
    requested = (
        await _milestone_async(client, ref, scope) if ref.milestone else ref.revision_id
    )
    tree = await client.get_configtree(
        ref.tree_name,
        revision=requested,
        include_data=True,
        content_types=["kv"],
        **scope.headers(),
    )
    return _selected(tree, requested)
