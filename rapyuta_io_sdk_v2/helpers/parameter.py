# Copyright 2026 Rapyuta Robotics

"""Synchronous submission of local directory trees to v1 Parameters."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from rapyuta_io_sdk_v2._parameter_api import blob_id
from rapyuta_io_sdk_v2.exceptions import MethodNotAllowedError
from rapyuta_io_sdk_v2.helpers._parameter_source import (
    check_source,
    classify_file,
    preflight,
    validate_storage_client,
)
from rapyuta_io_sdk_v2.helpers._parameter_storage import transfer_blob
from rapyuta_io_sdk_v2.helpers._parameter_upload import (
    UploadProgress,
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

    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.helpers._parameter_source import (
        ClassifiedFile,
        SourceEntry,
        SourceManifest,
    )
    from rapyuta_io_sdk_v2.models.parameter import ParameterUploadResult


@dataclass
class _Uploader:
    client: Client
    storage: httpx.Client
    progress: UploadProgress
    manifest: SourceManifest
    options: ParameterUploadOptions

    def run(self) -> ParameterUploadResult:
        self.progress.inspect(self.manifest)
        for tree in self.manifest.selected_trees:
            self.tree(tree)
        return self.progress.snapshot()

    def tree(self, name: str) -> None:
        self.progress.at(name, ParameterUploadStage.VALIDATE_SOURCE)
        root = next(entry for entry in self.manifest.roots if entry.tree_path == name)
        check_source(root)
        if self.options.delete_existing_trees:
            self.progress.at(name, ParameterUploadStage.DELETE_TREE)
            self.client.delete_parameter_tree(name)
            self.progress.deleted_trees.append(name)
        self.progress.at(name, ParameterUploadStage.CREATE_TREE)
        self.client.create_parameter_tree(name)
        self.progress.created_directories.append(name)
        for entry in self.manifest.entries:
            if entry.tree_path.split("/", 1)[0] == name:
                self.entry(entry)
        self.progress.completed_trees.append(name)

    def entry(self, entry: SourceEntry) -> None:
        if entry.node_type != ParameterNodeType.FILE:
            self.progress.at(entry.tree_path, ParameterUploadStage.CREATE_NODE)
            check_source(entry)
            self.client.put_parameter_node(
                entry.tree_path, ParameterNodeWrite(node_type=entry.node_type)
            )
            self.progress.created_directories.append(entry.tree_path)
            return
        self.progress.at(entry.tree_path, ParameterUploadStage.READ_FILE)
        source = classify_file(entry)
        if source.text is None:
            reference = self.blob(source)
        else:
            self.progress.at(entry.tree_path, ParameterUploadStage.CREATE_NODE)
            check_source(entry)
            self.client.put_parameter_node(
                entry.tree_path,
                ParameterNodeWrite(
                    node_type=ParameterNodeType.FILE,
                    data=source.text,
                    content_type=source.content_type,
                ),
            )
            check_source(entry)
            reference = None
        self.progress.complete_file(source, reference)

    def blob(self, source: ClassifiedFile) -> str:
        self.progress.at(source.entry.tree_path, ParameterUploadStage.PREPARE_UPLOAD)
        node = self.client.prepare_parameter_upload(
            source.entry.tree_path, source.metadata
        ).data
        reference = blob_id(node.blob_ref_id or "")
        if node.upload_url:
            self.progress.at(source.entry.tree_path, ParameterUploadStage.TRANSFER_BLOB)
            transfer_blob(self.storage, node.upload_url, source)
            self.confirm(source, reference)
        else:
            self.verify(source, reference)
        check_source(source.entry)
        return reference

    def verify(self, source: ClassifiedFile, reference: str) -> None:
        self.progress.at(source.entry.tree_path, ParameterUploadStage.VERIFY_BLOB)
        query = ParameterBlobQuery(
            tree_names=(source.entry.tree_path.split("/", 1)[0],)
        )
        verify_blob(self.client.list_parameter_blobs(query), reference, source.checksum)

    def confirm(self, source: ClassifiedFile, reference: str) -> None:
        self.progress.at(source.entry.tree_path, ParameterUploadStage.CONFIRM_UPLOAD)
        tree = source.entry.tree_path.split("/", 1)[0]
        try:
            self.client.commit_parameter_upload(tree, reference)
        except MethodNotAllowedError as error:
            if not duplicate_commit(error):
                raise
            self._verify_commit(source, reference, error)

    def _verify_commit(
        self, source: ClassifiedFile, reference: str, error: MethodNotAllowedError
    ) -> None:
        try:
            self.verify(source, reference)
        except Exception as verification:
            error.add_note(
                "Blob verification failed: " + redacted_message(verification)
            )
            self.progress.at(
                source.entry.tree_path, ParameterUploadStage.CONFIRM_UPLOAD
            )
            raise error from verification


def upload_parameters(
    client: Client,
    rootdir: str | Path,
    *,
    options: ParameterUploadOptions | None = None,
    storage_client: httpx.Client | None = None,
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
        ParameterUploadError: Attributable failure with immutable partial_result
            and the original exception as its cause. No automatic rollback.

    Caller-owned clients remain open; an internally created storage client closes.
    """
    progress = UploadProgress(path=str(rootdir))
    try:
        options = options if options is not None else ParameterUploadOptions()
        options = ParameterUploadOptions.model_validate(options.model_dump())
        validate_storage_client(storage_client)
        manifest = preflight(client.config, rootdir, options)
        with ExitStack() as stack:
            storage = (
                storage_client
                if storage_client is not None
                else stack.enter_context(
                    httpx.Client(follow_redirects=False, trust_env=False)
                )
            )
            return _Uploader(client, storage, progress, manifest, options).run()
    except Exception as error:
        raise progress.error(error) from error
