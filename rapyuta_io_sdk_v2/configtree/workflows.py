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

"""Synchronous and asynchronous configuration tree import and fast merge."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from rapyuta_io_sdk_v2.configtree._documents import prepare_documents
from rapyuta_io_sdk_v2.configtree._lifecycle import annotate
from rapyuta_io_sdk_v2.configtree._refs import (
    parse_refspec,
    require_key_map,
    require_parent,
    resolve_source,
    resolve_source_async,
)
from rapyuta_io_sdk_v2.configtree._scope import Scope
from rapyuta_io_sdk_v2.configtree._values import merge_values, validate_key
from rapyuta_io_sdk_v2.configtree.revision import AsyncRevision, Revision
from rapyuta_io_sdk_v2.models.configtree import (
    ConfigTree,
    ConfigTreeRevision,
    ConfigTreeRevisionMetadata,
)
from rapyuta_io_sdk_v2.models.configtree_operations import (
    ImportOptions,
    MergeOptions,
    RevisionOptions,
)
from rapyuta_io_sdk_v2.models.utils import BaseMetadata

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from rapyuta_io_sdk_v2 import AsyncClient, Client


def _head_body(tree_name: str, revision_id: str) -> ConfigTree:
    return ConfigTree(
        metadata=BaseMetadata(name=tree_name),
        head=ConfigTreeRevision(metadata=ConfigTreeRevisionMetadata(guid=revision_id)),
    )


def _revision_options(
    options: ImportOptions | MergeOptions, *, commit: bool
) -> RevisionOptions:
    return RevisionOptions(
        with_project=options.with_project,
        commit=commit,
        commit_body=options.commit_body.model_copy(deep=True)
        if options.commit_body
        else None,
    )


def _select_head(
    client: Client, tree_name: str, revision_id: str, *, scope: Scope
) -> None:
    try:
        client.set_configtree_revision(
            tree_name, _head_body(tree_name, revision_id), **scope.headers()
        )
    except BaseException as error:
        annotate(error, "head", revision_id)
        raise


async def _select_head_async(
    client: AsyncClient, tree_name: str, revision_id: str, *, scope: Scope
) -> None:
    try:
        await client.set_configtree_revision(
            tree_name, _head_body(tree_name, revision_id), **scope.headers()
        )
    except BaseException as error:
        annotate(error, "head", revision_id)
        raise


def import_configtree(
    client: Client,
    tree_name: str,
    files: Iterable[str | Path],
    *,
    options: ImportOptions | None = None,
) -> str:
    """Import named JSON/YAML files into one new revision.

    Args:
        client: Authenticated synchronous SDK client.
        tree_name: Existing destination tree name.
        files: Nonempty iterable of named local JSON, YAML, or YML paths.
        options: Scope, commit, head update, and optional commit body.

    Returns:
        Created revision GUID after every requested stage succeeds.

    Raises:
        ConfigTreeInputError: If any file or key is invalid.
        ConfigTreeReferenceError: If the target or parent cannot be used.
        Exception: Original platform failures carry revision ID and stage when
            known. Head selection of an uncommitted revision may be rejected.
    """
    selected = options or ImportOptions()
    try:
        validate_key(tree_name)
        scope = Scope.capture(client, with_project=selected.with_project)
        values = prepare_documents(files)
        tree = client.get_configtree(tree_name, **scope.headers())
        require_parent(tree)
    except BaseException as error:
        annotate(error, "prepare", None)
        raise
    try:
        revision = Revision(
            client,
            tree_name,
            options=_revision_options(selected, commit=selected.commit),
            commit_message="Imported configuration through rapyuta-io-sdk-v2",
            _scope=scope,
        )
    except BaseException as error:
        annotate(error, "prepare", None)
        raise
    with revision:
        revision.keys.update(values)
    revision_id = revision.revision_id
    if selected.update_head:
        _select_head(client, tree_name, revision_id, scope=scope)
    return revision_id


async def import_configtree_async(
    client: AsyncClient,
    tree_name: str,
    files: Iterable[str | Path],
    *,
    options: ImportOptions | None = None,
) -> str:
    """Asynchronously import named files into one new revision.

    Args:
        client: Authenticated asynchronous SDK client.
        tree_name: Existing destination tree name.
        files: Nonempty iterable of named local JSON, YAML, or YML paths.
        options: Scope, commit, head update, and optional commit body.

    Returns:
        Created revision GUID after every requested stage succeeds.

    Raises:
        ConfigTreeInputError: If any file or key is invalid.
        ConfigTreeReferenceError: If the target or parent cannot be used.
        Exception: Original platform errors and cancellation propagate with
            revision ID and stage when known.
    """
    selected = options or ImportOptions()
    try:
        validate_key(tree_name)
        scope = Scope.capture(client, with_project=selected.with_project)
        values = await asyncio.to_thread(prepare_documents, files)
        tree = await client.get_configtree(tree_name, **scope.headers())
        require_parent(tree)
    except BaseException as error:
        annotate(error, "prepare", None)
        raise
    try:
        revision = AsyncRevision(
            client,
            tree_name,
            options=_revision_options(selected, commit=selected.commit),
            commit_message="Imported configuration through rapyuta-io-sdk-v2",
            _scope=scope,
        )
    except BaseException as error:
        annotate(error, "prepare", None)
        raise
    async with revision:
        revision.keys.update(values)
    revision_id = revision.revision_id
    if selected.update_head:
        await _select_head_async(client, tree_name, revision_id, scope=scope)
    return revision_id


def merge_configtree(
    client: Client,
    tree_name: str,
    refspec: str,
    *,
    options: MergeOptions | None = None,
) -> str:
    """Fast merge a scoped source into one committed destination revision.

    Args:
        client: Authenticated synchronous SDK client.
        tree_name: Existing destination tree name.
        refspec: ``org/tree`` or ``proj/tree`` with optional selector.
        options: Destination scope and optional commit body.

    Returns:
        New committed and selected revision GUID.

    Raises:
        ConfigTreeReferenceError: If a reference or parent is unusable.
        ConfigTreeMergeConflictError: If shared stored values differ.
        Exception: Original platform errors retain revision recovery details.
    """
    selected = options or MergeOptions()
    try:
        validate_key(tree_name)
        ref = parse_refspec(refspec)
        destination_scope = Scope.capture(client, with_project=selected.with_project)
        source_scope = Scope.capture(client, with_project=not ref.is_org)
        destination = client.get_configtree(
            tree_name,
            include_data=True,
            content_types=["kv"],
            **destination_scope.headers(),
        )
        parent = require_parent(destination)
        destination_keys = require_key_map(destination)
        values = merge_values(
            destination_keys, require_key_map(resolve_source(client, ref, source_scope))
        )
    except BaseException as error:
        annotate(error, "resolve", None)
        raise
    try:
        revision = Revision(
            client,
            tree_name,
            options=_revision_options(selected, commit=True),
            parent=parent,
            commit_message="Merged configuration through rapyuta-io-sdk-v2",
            _scope=destination_scope,
        )
    except BaseException as error:
        annotate(error, "prepare", None)
        raise
    with revision:
        revision.keys.update(values)
    revision_id = revision.revision_id
    _select_head(client, tree_name, revision_id, scope=destination_scope)
    return revision_id


async def merge_configtree_async(
    client: AsyncClient,
    tree_name: str,
    refspec: str,
    *,
    options: MergeOptions | None = None,
) -> str:
    """Await compatible merge, commit, and head selection in order.

    Args:
        client: Authenticated asynchronous SDK client.
        tree_name: Existing destination tree name.
        refspec: Scoped source tree with optional revision or milestone selector.
        options: Destination scope and optional commit body.

    Returns:
        New committed and selected revision GUID.

    Raises:
        ConfigTreeReferenceError: If source or parent resolution fails.
        ConfigTreeMergeConflictError: If stored shared keys differ.
        Exception: Original platform errors and cancellation propagate with
            revision ID and stage when known.
    """
    selected = options or MergeOptions()
    try:
        validate_key(tree_name)
        ref = parse_refspec(refspec)
        destination_scope = Scope.capture(client, with_project=selected.with_project)
        source_scope = Scope.capture(client, with_project=not ref.is_org)
        destination = await client.get_configtree(
            tree_name,
            include_data=True,
            content_types=["kv"],
            **destination_scope.headers(),
        )
        parent = require_parent(destination)
        destination_keys = require_key_map(destination)
        values = merge_values(
            destination_keys,
            require_key_map(await resolve_source_async(client, ref, source_scope)),
        )
    except BaseException as error:
        annotate(error, "resolve", None)
        raise
    try:
        revision = AsyncRevision(
            client,
            tree_name,
            options=_revision_options(selected, commit=True),
            parent=parent,
            commit_message="Merged configuration through rapyuta-io-sdk-v2",
            _scope=destination_scope,
        )
    except BaseException as error:
        annotate(error, "prepare", None)
        raise
    async with revision:
        revision.keys.update(values)
    revision_id = revision.revision_id
    await _select_head_async(client, tree_name, revision_id, scope=destination_scope)
    return revision_id
