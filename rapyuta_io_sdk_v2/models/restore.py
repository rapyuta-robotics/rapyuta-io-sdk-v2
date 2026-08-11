"""
Pydantic models for Restore resources.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    SecretKeyRef,
)


class RestoreOptions(BaseModel):
    """``pg_restore`` behaviours the caller may select."""

    # Drop the objects being restored before recreating them.
    clean: bool | None = Field(default=None)
    # Skip restoring object ownership.
    no_owner: bool | None = Field(default=None, alias="noOwner")
    # Tolerate objects that are already absent. Only meaningful with ``clean``;
    # the device drops it otherwise, because pg_restore errors on it alone.
    if_exists: bool | None = Field(default=None, alias="ifExists")


class RestoreArchive(BaseModel):
    """One uploaded backup file the device downloads. Server-resolved and only
    ever populated on the device-facing copy — ``url`` is blanked on every
    user-facing read."""

    guid: str | None = Field(default=None)
    role: Literal["base", "wal"] | None = Field(default=None)
    backup_id: str | None = Field(default=None, alias="backupID")
    url: str | None = Field(default=None)


class RestoreSource(BaseModel):
    """Where the restored data comes from.

    ``backup`` restores from a Backup's uploaded archives; ``dataDirectory``
    restores from an existing on-device cluster directory, which is how a
    major-version migration is expressed.
    """

    type: Literal["backup", "dataDirectory"]

    # --- type=backup ---
    backup_name: str | None = Field(default=None, alias="backupName")
    # Defaults to the backup's latest run.
    backup_run_id: str | None = Field(default=None, alias="backupRunID")
    # Point-in-time recovery. Rejected with a 501 until WAL segments are uploaded
    # to object storage: without them the only recoverable point is the base
    # backup, and restoring that would report a point-in-time result you never got.
    target_time: str | None = Field(default=None, alias="targetTime")

    # --- type=dataDirectory ---
    # Must be an absolute path: a relative one is read by Docker as a named
    # volume, so the restore would run against an empty directory.
    old_data_directory: str | None = Field(default=None, alias="oldDataDirectory")
    # The old cluster's major version, cross-checked by the image against the
    # directory's PG_VERSION.
    source_version: Literal["16", "17", "18"] | None = Field(
        default=None, alias="sourceVersion"
    )

    # --- Server-resolved, device-facing copy only. ---
    source_image: str | None = Field(default=None, alias="sourceImage")
    archives: list[RestoreArchive] | None = Field(default=None)


class RestoreSpec(BaseModel):
    """Specification for a Restore resource."""

    # Target database. The restore runs against the live instance, so this is the
    # database the data lands in. Set from the path by the CLI/apiserver.
    database: str | None = Field(default=None)

    source: RestoreSource

    # Logical databases to restore. Empty means every logical database found in
    # the source; anything outside this list is left untouched in the target.
    databases: list[str] | None = Field(default=None)

    options: RestoreOptions | None = Field(default=None)

    # --- Server-resolved from the target database. ---
    device_guid: str | None = Field(default=None, alias="deviceGuid")
    database_guid: str | None = Field(default=None, alias="databaseGuid")
    postgres_version: str | None = Field(default=None, alias="postgresVersion")
    # The restore image for the target's major version. Not the database server
    # image: the restore pod runs a one-shot pipeline, not a postmaster.
    restore_image: str | None = Field(default=None, alias="restoreImage")
    target_port: int | None = Field(default=None, alias="targetPort")
    data_directory: str | None = Field(default=None, alias="dataDirectory")
    # The target's primary user, which pg_restore authenticates as. References
    # only; the resolved value never reaches a user-facing read.
    credentials: dict[str, SecretKeyRef] | None = Field(default=None)


class RestoreStatus(BaseModel):
    """Status of a Restore resource."""

    phase: Literal["Pending", "Running", "Completed", "Failed"] | None = Field(
        default=None
    )
    message: str | None = Field(default=None)
    started_at: str | None = Field(default=None, alias="startedAt")
    completed_at: str | None = Field(default=None, alias="completedAt")
    # The logical databases the device actually loaded. A partial run reports
    # exactly what landed, which is what decides whether to re-run.
    restored_databases: list[str] | None = Field(default=None, alias="restoredDatabases")


class Restore(BaseObject):
    """Restore resource model.

    A restore loads logical databases into a **live, running** database. It never
    creates one: seeding a fresh instance is "create a Database, then restore into
    it". It is a sub-resource of Database, and one-shot — the spec is immutable
    and only the device-reported status changes.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["Restore"] | None = "Restore"
    metadata: BaseMetadata = Field(description="Metadata for the Restore resource")
    spec: RestoreSpec = Field(description="Specification for the Restore resource")
    status: RestoreStatus | None = Field(default=None)


class RestoreList(BaseList[Restore]):
    """Paginated list of Restore resources."""

    pass
