"""
Pydantic models for Backup resources.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject


class BackupSpec(BaseModel):
    """Specification for a Backup resource."""

    type: Literal["scheduled", "onDemand"] = Field(default="scheduled")
    database: str = Field(description="Source database name (reference only)")
    # Server-resolved at creation time.
    barman_image: str | None = Field(default=None, alias="barmanImage")
    device_guid: str | None = Field(default=None, alias="deviceGuid")
    schedule: str | None = Field(
        default=None, description="Cron schedule (required when type=scheduled)"
    )
    postgres_version: str | None = Field(default=None, alias="postgresVersion")
    primary_port: int | None = Field(default=None, alias="primaryPort")


class BackupVerification(BaseModel):
    """Verification outcomes for a backup run."""

    check: Literal["Passed", "Failed", "Skipped"] | None = Field(default=None)
    verify_backup: Literal["Passed", "Failed", "Skipped"] | None = Field(
        default=None, alias="verifyBackup"
    )


class BackupRun(BaseModel):
    """A single backup run."""

    backup_id: str | None = Field(default=None, alias="backupID")
    begin_wal: str | None = Field(default=None, alias="beginWAL")
    end_wal: str | None = Field(default=None, alias="endWAL")
    verification: BackupVerification | None = Field(default=None)
    completed_at: str | None = Field(default=None, alias="completedAt")


class BackupFileUpload(BaseModel):
    """One archive this backup uploaded to object storage.

    A restore resolves what to download from this list, so the ``guid`` here is
    what ``rio restore create --file-upload`` takes.
    """

    guid: str | None = Field(default=None)
    role: Literal["base", "wal"] | None = Field(default=None)
    backup_id: str | None = Field(default=None, alias="backupID")
    # Resolved from the file-upload service. Left a free string rather than a
    # Literal: it is that service's vocabulary, not this API's.
    status: str | None = Field(default=None)
    size_bytes: int | None = Field(default=None, alias="sizeBytes")


class BackupStatus(BaseModel):
    """Status of a Backup resource."""

    phase: Literal["Pending", "Running", "Ready", "Failed"] | None = Field(default=None)
    message: str | None = Field(default=None)
    # Which stage the current run is on. The recover dominates a run's duration,
    # so the phase alone cannot tell a slow backup from a stuck one.
    step: str | None = Field(default=None)
    latest_run: BackupRun | None = Field(default=None, alias="latestRun")
    # Accumulates across runs: the device's per-backup result pointer is
    # overwritten every run while the archives it produced live on.
    file_uploads: list[BackupFileUpload] | None = Field(default=None, alias="fileUploads")


class Backup(BaseObject):
    """Backup resource model."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["Backup"] | None = "Backup"
    metadata: BaseMetadata = Field(description="Metadata for the Backup resource")
    spec: BackupSpec = Field(description="Specification for the Backup resource")
    status: BackupStatus | None = Field(default=None)


class BackupList(BaseList[Backup]):
    """Paginated list of Backup resources."""

    pass
