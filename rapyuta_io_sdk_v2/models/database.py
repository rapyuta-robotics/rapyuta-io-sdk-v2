"""
Pydantic models for Database resource.

This module contains Pydantic models that correspond to the Database JSON schema,
providing validation for Database resources.

The server uses a custom JSON encoding for DatabaseSpec:
  {"type": "postgres", "postgres": {...PostgresSpec...}}

And for DatabaseStatus:
  {"phase": "running", "postgres": {...PostgresStatus...}}
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject


DatabasePhase = Literal["provisioning", "running", "stopped", "error"]
UploadStatus = Literal["PENDING", "IN PROGRESS", "FAILED", "COMPLETED", "CANCELLED", "UNKNOWN"]


class DeviceSpec(BaseModel):
    """Identifies a device by name and an optional data directory."""

    deviceName: str | None = Field(default=None, description="Device name")
    deviceGUID: str | None = Field(default=None, description="Device GUID")
    dataDirectory: str | None = Field(default=None, description="Data directory path on device")


class Credentials(BaseModel):
    """Username/password credentials."""

    username: str = Field(description="Username")
    password: str = Field(description="Password")


class MigrationSpec(BaseModel):
    """Spec for in-place data migration."""

    enabled: bool = Field(default=False, description="Whether migration is enabled")
    sourceDataDirectory: str | None = Field(
        default=None, description="Source data directory to migrate from"
    )


class StandbySpec(BaseModel):
    """Standby (replication) configuration."""

    primaryInterface: str | None = Field(
        default=None, description="Network interface on the primary device"
    )
    primaryIP: str | None = Field(default=None, description="Primary device IP address")
    devices: list[DeviceSpec] | None = Field(
        default=None, description="List of standby device specs"
    )


class BackupSpec(BaseModel):
    """Backup configuration."""

    enabled: bool = Field(default=False, description="Whether backups are enabled")
    schedule: str | None = Field(default=None, description="Cron schedule for backups")
    directory: str | None = Field(default=None, description="Directory to store backups")
    credentials: Credentials | None = Field(
        default=None, description="Credentials for remote backup storage"
    )


class RecoverySpec(BaseModel):
    """Point-in-time recovery configuration."""

    sourceBackupID: str = Field(description="Source backup ID to restore from")


class PostgresSpec(BaseModel):
    """Engine-specific configuration for a PostgreSQL database (response model)."""

    version: str = Field(description="PostgreSQL version")
    primary: DeviceSpec = Field(description="Primary device spec")
    migration: MigrationSpec | None = Field(default=None, description="Migration spec")
    credentials: Credentials | None = Field(default=None, description="Database credentials")
    multipleDatabase: list[str] | None = Field(
        default=None, description="Additional database names to create"
    )
    parameters: dict[str, str] | None = Field(
        default=None, description="PostgreSQL server parameters"
    )
    standby: StandbySpec | None = Field(default=None, description="Standby replication spec")
    backup: BackupSpec | None = Field(default=None, description="Backup spec")
    recovery: RecoverySpec | None = Field(default=None, description="Recovery spec")


class PostgresSpecCreate(PostgresSpec):
    """PostgresSpec for create requests — credentials are required."""

    credentials: Credentials = Field(description="Database credentials")


class DatabaseSpec(BaseModel):
    """Database spec — wraps the engine-specific config under a type-keyed field.

    JSON form: {"type": "postgres", "postgres": {...}}
    """

    type: str = Field(description='Database engine type, e.g. "postgres"')
    postgres: PostgresSpec | None = Field(
        default=None, description="PostgreSQL engine config (when type is postgres)"
    )


class DatabaseSpecCreate(DatabaseSpec):
    """DatabaseSpec for create requests."""

    postgres: PostgresSpecCreate | None = Field(
        default=None, description="PostgreSQL engine config (when type is postgres)"
    )


class DatabaseCreate(BaseObject):
    """Database model for create requests — credentials are required."""

    kind: Literal["Database"] | None = "Database"
    metadata: BaseMetadata = Field(description="Metadata for the Database resource")
    spec: DatabaseSpecCreate = Field(description="Specification for the Database resource")


class DatabasePatch(BaseModel):
    """Payload for updating a database."""

    spec: DatabaseSpec = Field(description="Updated database spec")


# --- Status models ---


class DBContainerStateWaiting(BaseModel):
    reason: str | None = None
    message: str | None = None


class DBContainerStateRunning(BaseModel):
    startedAt: str | None = None


class DBContainerStateTerminated(BaseModel):
    exitCode: int = 0
    signal: int | None = None
    reason: str | None = None
    message: str | None = None
    startedAt: str | None = None
    finishedAt: str | None = None


class DBContainerState(BaseModel):
    waiting: DBContainerStateWaiting | None = None
    running: DBContainerStateRunning | None = None
    terminated: DBContainerStateTerminated | None = None


class DatabaseCondition(BaseModel):
    type: str | None = None
    status: Literal["True", "False", "Unknown"] | None = None
    reason: str | None = None
    message: str | None = None
    lastTransitionTime: str | None = None


class PrimaryStatus(BaseModel):
    name: str | None = None
    phase: DatabasePhase | None = None
    message: str | None = None
    deviceName: str | None = None
    port: int | None = None
    lastUpdated: str | None = None
    conditions: list[DatabaseCondition] | None = None
    state: DBContainerState | None = None
    lastState: DBContainerState | None = None
    restartCount: int | None = None


class StandbyStatus(BaseModel):
    phase: DatabasePhase | None = None
    replicationLagSeconds: int | None = None


BackupLastStatus = Literal["Success", "Failed", "Unknown"]


class BackupStatus(BaseModel):
    lastStatus: BackupLastStatus | None = None
    lastBackupTime: str | None = None
    failureReason: str | None = None
    barmanPhase: DatabasePhase | None = None
    conditions: list[DatabaseCondition] | None = None
    barmanConditions: list[DatabaseCondition] | None = None


class MigrationStatus(BaseModel):
    phase: DatabasePhase | None = None
    sourceVersion: str | None = None
    startedAt: str | None = None
    dumpStartedAt: str | None = None
    restoreStartedAt: str | None = None
    completedAt: str | None = None


class RecoveryStatus(BaseModel):
    lastRecoveryID: str | None = None
    backupSource: str | None = None
    phase: DatabasePhase | None = None
    failureReason: str | None = None
    startedAt: str | None = None
    completedAt: str | None = None


class PostgresStatus(BaseModel):
    """Status details for a PostgreSQL database engine."""

    primary: PrimaryStatus | None = None
    standby: StandbyStatus | None = None
    backup: BackupStatus | None = None
    migration: MigrationStatus | None = None
    recovery: RecoveryStatus | None = None


class DatabaseStatus(BaseModel):
    """Database status.

    JSON form: {"phase": "running", "postgres": {...PostgresStatus...}}
    """

    model_config = ConfigDict(extra="allow")

    phase: DatabasePhase | None = None
    postgres: PostgresStatus | None = None


class Database(BaseObject):
    """Database model."""

    kind: Literal["Database"] | None = "Database"
    metadata: BaseMetadata = Field(description="Metadata for the Database resource")
    spec: DatabaseSpec = Field(description="Specification for the Database resource")
    status: DatabaseStatus | None = Field(default=None)


class DatabaseList(BaseList[Database]):
    """List of databases."""

    pass


# --- Backup models ---


class DBBackupSpec(BaseModel):
    """Specification for a Database backup record."""

    id: str | None = Field(default=None, description="Backup ID")
    deviceGUID: str | None = Field(default=None, description="Device GUID")
    databaseName: str | None = Field(default=None, description="Database name")
    fileUploadGUID: str | None = Field(default=None, description="File upload GUID")
    status: UploadStatus | None = Field(default=None, description="Upload status")


class Backup(BaseObject):
    """Database backup model."""

    kind: Literal["Backup"] | None = "Backup"
    metadata: BaseMetadata | None = Field(default=None)
    spec: DBBackupSpec | None = Field(default=None)


class BackupList(BaseList[Backup]):
    """List of database backups."""

    pass
