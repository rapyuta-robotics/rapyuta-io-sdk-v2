# Copyright 2026 Rapyuta Robotics

"""Mutable progress, immutable outcomes and pure blob-status verification."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import TYPE_CHECKING

from rapyuta_io_sdk_v2.exceptions import (
    MethodNotAllowedError,
    ParameterUploadCancelled,
    ParameterUploadError,
)
from rapyuta_io_sdk_v2.models.parameter import (
    ParameterBlobStatus,
    ParameterFileUploadResult,
    ParameterSkippedEntry,
    ParameterUploadFailure,
    ParameterUploadResult,
    ParameterUploadStage,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from rapyuta_io_sdk_v2.helpers._parameter_source import (
        ClassifiedFile,
        SourceManifest,
    )
    from rapyuta_io_sdk_v2.models.parameter import ParameterBlobListResponse

DUPLICATE_MESSAGE = "blobRef signed url not generated or blobRef already uploaded"


def redacted_message(error: BaseException) -> str:
    """Remove signed URL authorization queries from public error display."""
    return re.sub(
        r"(https?://[^\s?'\"<>]+)\?[^\s'\"<>]*",
        r"\1?<redacted>",
        str(error),
        flags=re.IGNORECASE,
    )


@dataclass
class UploadProgress:
    """Mutable internal accumulator; only confirmed operations enter snapshots."""

    selected_trees: tuple[str, ...] = ()
    completed_trees: list[str] = field(default_factory=list)
    completed_files: list[ParameterFileUploadResult] = field(default_factory=list)
    created_directories: list[str] = field(default_factory=list)
    deleted_trees: list[str] = field(default_factory=list)
    skipped_entries: tuple[ParameterSkippedEntry, ...] = ()
    path: str = ""
    stage: ParameterUploadStage = ParameterUploadStage.VALIDATE_SOURCE

    def inspect(self, manifest: SourceManifest) -> None:
        """Retain exact selection and all known metadata skips."""
        self.selected_trees = manifest.selected_trees
        self.skipped_entries = manifest.skipped_entries

    def at(self, path: str, stage: ParameterUploadStage) -> None:
        """Identify the next operation before it can fail or be cancelled."""
        self.path = path
        self.stage = stage

    def snapshot(self) -> ParameterUploadResult:
        """Freeze all confirmed item identities and inspected skips."""
        return ParameterUploadResult(
            selected_trees=self.selected_trees,
            completed_trees=tuple(self.completed_trees),
            completed_files=tuple(self.completed_files),
            created_directories=tuple(self.created_directories),
            deleted_trees=tuple(self.deleted_trees),
            skipped_entries=self.skipped_entries,
        )

    def failure(self, error: BaseException) -> ParameterUploadFailure:
        """Build attributable failure context without exposing signed queries."""
        path = error.filename if isinstance(error, OSError) else None
        return ParameterUploadFailure(
            path=getattr(error, "path", path or self.path),
            stage=self.stage,
            message=redacted_message(error) or type(error).__name__,
        )

    def error(self, error: Exception) -> ParameterUploadError:
        """Wrap an ordinary error with a frozen progress snapshot."""
        return ParameterUploadError(self.failure(error), self.snapshot())

    def cancelled(self, error: asyncio.CancelledError) -> ParameterUploadCancelled:
        """Preserve cancellation semantics with the same typed result contract."""
        return ParameterUploadCancelled(self.failure(error), self.snapshot())

    def complete_file(
        self, source: ClassifiedFile, reference: str | None = None
    ) -> None:
        """Record one acknowledged intended file, even when content is shared."""
        self.completed_files.append(
            ParameterFileUploadResult(
                tree_path=source.entry.tree_path,
                storage="blob" if source.text is None else "inline",
                checksum=source.checksum,
                blob_ref_id=reference,
            )
        )


def verify_blob(
    response: ParameterBlobListResponse, reference: str, checksum: str
) -> None:
    """Require the same numeric ID, original checksum and Uploaded status."""
    matches = any(
        blob.id == int(reference)
        and blob.checksum == checksum
        and blob.status == ParameterBlobStatus.UPLOADED
        for blob in response.data.blob_refs
    )
    if not matches:
        message = f"Blob reference {reference} is not verified Uploaded"
        raise ValueError(message)


def duplicate_commit(error: MethodNotAllowedError) -> bool:
    """Allow verification only for the known 403 ambiguous lifecycle error."""
    return (
        getattr(error, "status_code", None) == HTTPStatus.FORBIDDEN
        and str(error) == DUPLICATE_MESSAGE
    )


async def disk_work[T](operation: Callable[..., T], *args: object) -> T:
    """Offload local work and wait for worker-owned cleanup on cancellation."""
    worker = asyncio.create_task(asyncio.to_thread(operation, *args))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        await asyncio.gather(worker, return_exceptions=True)
        raise
