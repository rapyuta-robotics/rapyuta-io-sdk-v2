# Copyright 2026 Rapyuta Robotics

"""Asynchronous submission of local directory trees to v1 Parameters."""

from __future__ import annotations

from asyncio import CancelledError
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from rapyuta_io_sdk_v2._parameter_api import blob_id
from rapyuta_io_sdk_v2.exceptions import MethodNotAllowedError
from rapyuta_io_sdk_v2.helpers._parameter_source import (
    check_source,
    classify_file_async,
    preflight,
    validate_storage_client,
)
from rapyuta_io_sdk_v2.helpers._parameter_storage import transfer_blob_async
from rapyuta_io_sdk_v2.helpers._parameter_upload import (
    UploadProgress,
    disk_work,
    duplicate_commit,
    redacted_message,
    verify_blob,
)
from rapyuta_io_sdk_v2.models.parameter import (
    ParameterBlobQuery,
    ParameterNodeType,
    ParameterNodeWrite,
    ParameterUploadOptions,
    ParameterUploadStage,
)

if TYPE_CHECKING:
    from pathlib import Path

    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.helpers._parameter_source import (
        ClassifiedFile,
        SourceEntry,
        SourceManifest,
    )
    from rapyuta_io_sdk_v2.models.parameter import ParameterUploadResult


@dataclass
class _Uploader:
    client: AsyncClient
    storage: httpx.AsyncClient
    progress: UploadProgress
    manifest: SourceManifest
    options: ParameterUploadOptions

    async def run(self) -> ParameterUploadResult:
        self.progress.inspect(self.manifest)
        for tree in self.manifest.selected_trees:
            await self.tree(tree)
        return self.progress.snapshot()

    async def tree(self, name: str) -> None:
        self.progress.at(name, ParameterUploadStage.VALIDATE_SOURCE)
        root = next(entry for entry in self.manifest.roots if entry.tree_path == name)
        await disk_work(check_source, root)
        if self.options.delete_existing_trees:
            self.progress.at(name, ParameterUploadStage.DELETE_TREE)
            await self.client.delete_parameter_tree(name)
            self.progress.deleted_trees.append(name)
        self.progress.at(name, ParameterUploadStage.CREATE_TREE)
        await self.client.create_parameter_tree(name)
        self.progress.created_directories.append(name)
        for entry in self.manifest.entries:
            if entry.tree_path.split("/", 1)[0] == name:
                await self.entry(entry)
        self.progress.completed_trees.append(name)

    async def entry(self, entry: SourceEntry) -> None:
        if entry.node_type != ParameterNodeType.FILE:
            self.progress.at(entry.tree_path, ParameterUploadStage.CREATE_NODE)
            await disk_work(check_source, entry)
            await self.client.put_parameter_node(
                entry.tree_path, ParameterNodeWrite(node_type=entry.node_type)
            )
            self.progress.created_directories.append(entry.tree_path)
            return
        self.progress.at(entry.tree_path, ParameterUploadStage.READ_FILE)
        source = await classify_file_async(entry)
        if source.text is None:
            reference = await self.blob(source)
        else:
            self.progress.at(entry.tree_path, ParameterUploadStage.CREATE_NODE)
            await disk_work(check_source, entry)
            await self.client.put_parameter_node(
                entry.tree_path,
                ParameterNodeWrite(
                    node_type=ParameterNodeType.FILE,
                    data=source.text,
                    content_type=source.content_type,
                ),
            )
            await disk_work(check_source, entry)
            reference = None
        self.progress.complete_file(source, reference)

    async def blob(self, source: ClassifiedFile) -> str:
        self.progress.at(source.entry.tree_path, ParameterUploadStage.PREPARE_UPLOAD)
        node = (
            await self.client.prepare_parameter_upload(
                source.entry.tree_path, source.metadata
            )
        ).data
        reference = blob_id(node.blob_ref_id or "")
        if node.upload_url:
            self.progress.at(source.entry.tree_path, ParameterUploadStage.TRANSFER_BLOB)
            await transfer_blob_async(self.storage, node.upload_url, source)
            await self.confirm(source, reference)
        else:
            await self.verify(source, reference)
        await disk_work(check_source, source.entry)
        return reference

    async def verify(self, source: ClassifiedFile, reference: str) -> None:
        self.progress.at(source.entry.tree_path, ParameterUploadStage.VERIFY_BLOB)
        query = ParameterBlobQuery(
            tree_names=(source.entry.tree_path.split("/", 1)[0],)
        )
        verify_blob(
            await self.client.list_parameter_blobs(query), reference, source.checksum
        )

    async def confirm(self, source: ClassifiedFile, reference: str) -> None:
        self.progress.at(source.entry.tree_path, ParameterUploadStage.CONFIRM_UPLOAD)
        tree = source.entry.tree_path.split("/", 1)[0]
        try:
            await self.client.commit_parameter_upload(tree, reference)
        except MethodNotAllowedError as error:
            if not duplicate_commit(error):
                raise
            await self._verify_commit(source, reference, error)

    async def _verify_commit(
        self, source: ClassifiedFile, reference: str, error: MethodNotAllowedError
    ) -> None:
        try:
            await self.verify(source, reference)
        except Exception as verification:
            error.add_note(
                "Blob verification failed: " + redacted_message(verification)
            )
            self.progress.at(
                source.entry.tree_path, ParameterUploadStage.CONFIRM_UPLOAD
            )
            raise error from verification


async def upload_parameters_async(
    client: AsyncClient,
    rootdir: str | Path,
    *,
    options: ParameterUploadOptions | None = None,
    storage_client: httpx.AsyncClient | None = None,
) -> ParameterUploadResult:
    """Submit selected immediate directories, preserving original file contents.

    Args:
        client: Caller-owned authenticated client with a configured project.
        rootdir: Directory whose immediate child directories become trees.
        options: Exact selection, optional recreation and folder/legacy mode.
        storage_client: Optional isolated caller-owned storage transport.

    Returns:
        Immutable identities of confirmed trees/files/directories and skips.

    Raises:
        ParameterUploadCancelled: Cancellation with typed failure/partial_result.
        ParameterUploadError: Attributable failure with immutable partial_result
            and the original exception as its cause. No automatic rollback.

    Caller-owned clients remain open; an internally created storage client closes.
    """
    progress = UploadProgress(path=str(rootdir))
    try:
        options = options if options is not None else ParameterUploadOptions()
        options = ParameterUploadOptions.model_validate(options.model_dump())
        validate_storage_client(storage_client)
        manifest = await disk_work(preflight, client.config, rootdir, options)
        async with AsyncExitStack() as stack:
            storage = (
                storage_client
                if storage_client is not None
                else await stack.enter_async_context(
                    httpx.AsyncClient(follow_redirects=False, trust_env=False)
                )
            )
            return await _Uploader(client, storage, progress, manifest, options).run()
    except CancelledError as error:
        raise progress.cancelled(error) from error
    except Exception as error:
        raise progress.error(error) from error
