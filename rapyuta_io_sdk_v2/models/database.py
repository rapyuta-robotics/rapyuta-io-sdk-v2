"""
Pydantic models for Database and Backup resources.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    SecretKeyRef,
)


class DeviceSpec(BaseModel):
    """Device placement for a Postgres instance."""

    device_name: str = Field(alias="deviceName")
    device_guid: str | None = Field(alias="deviceGuid", default=None)
    data_directory: str | None = Field(alias="dataDirectory", default=None)
    port: int | None = Field(default=None)


class Credentials(BaseModel):
    """References to the secret keys holding a Postgres user's username and
    password. Only ``name``+``key`` are sent on create; the apiserver resolves
    ``value`` onto the device-facing copy and never persists it. Immutable after
    creation."""

    username: SecretKeyRef | None = Field(default=None)
    password: SecretKeyRef | None = Field(default=None)


class ReplicationCredentials(BaseModel):
    """Streaming-replication user consumed by standbys. Server-generated and
    redacted on read (password blanked), so these are plain resolved strings
    rather than secret refs. Read-only."""

    username: str | None = Field(default=None)
    password: str | None = Field(default=None)


class PostgresUsers(BaseModel):
    primary: Credentials | None = Field(default=None)
    backup: Credentials | None = Field(default=None)
    replication: ReplicationCredentials | None = Field(default=None)


class StandbySpec(BaseModel):
    """Optional hot-standby topology. Each standby sits on a device distinct from
    the primary and from every other standby."""

    primary_interface: str | None = Field(alias="primaryInterface", default=None)
    # Server-managed: resolved from the primary device record; consumed by
    # standby devices as the replication host.
    primary_host: str | None = Field(alias="primaryHost", default=None)
    devices: list[DeviceSpec] | None = Field(default=None)


class PostgresParameters(BaseModel):
    """Tunable ``postgresql.conf`` parameters. Omitted fields keep the Postgres
    defaults."""

    # YAML manifests naturally write `max_connections: 200` unquoted, so coerce
    # numbers to strings here rather than rejecting them. The wire payload must
    # carry a string either way — see the field comment below.
    model_config = ConfigDict(coerce_numbers_to_str=True)

    # Both values are strings on the wire, matching postgresql.conf itself. Sending
    # max_connections as a JSON number breaks devices that still model parameters
    # as a string map, so it stays a decimal string here, e.g. "200".
    max_connections: str | None = Field(default=None, pattern=r"^[1-9][0-9]*$")
    # A positive integer, optionally suffixed with a unit. A bare number is a
    # count of 8kB blocks.
    shared_buffers: str | None = Field(
        default=None, pattern=r"^[1-9][0-9]*(kB|MB|GB|TB)?$"
    )


class PostgresSpec(BaseModel):
    """Specification for a PostgreSQL database instance."""

    version: Literal["16", "17", "18"]
    postgres_image: str | None = Field(alias="postgresImage", default=None)

    primary: DeviceSpec
    standby: StandbySpec | None = Field(default=None)
    users: PostgresUsers | None = Field(default=None)
    multiple_database: list[str] | None = Field(default=None, alias="multipleDatabase")
    parameters: PostgresParameters | None = Field(default=None)


class DatabaseSpec(BaseModel):
    """Specification for a Database resource."""

    type: Literal["postgres"] = Field(default="postgres")
    postgres: PostgresSpec | None = Field(default=None)


class ContainerState(BaseModel):
    """Container state details."""

    started_at: str | None = Field(default=None, alias="startedAt")
    finished_at: str | None = Field(default=None, alias="finishedAt")
    exit_code: int | None = Field(default=None, alias="exitCode")
    reason: str | None = Field(default=None)
    message: str | None = Field(default=None)


class PrimaryStatus(BaseModel):
    """Status of the Postgres primary container."""

    device_name: str = Field(alias="deviceName")
    port: int
    phase: str | None = Field(default=None)
    message: str | None = Field(default=None)
    state: ContainerState | None = Field(default=None)
    last_state: ContainerState | None = Field(default=None, alias="lastState")
    restart_count: int | None = Field(default=None, alias="restartCount")
    last_updated: str | None = Field(default=None, alias="lastUpdated")

    @field_validator("state", "last_state", mode="before")
    @staticmethod
    def normalize_container_state(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict) and not value:
            return None
        return value


class StandbyStatus(BaseModel):
    """Status of a Postgres standby container, reported per standby device."""

    device_name: str = Field(alias="deviceName")
    port: int
    phase: str | None = Field(default=None)
    message: str | None = Field(default=None)
    state: ContainerState | None = Field(default=None)
    last_state: ContainerState | None = Field(default=None, alias="lastState")
    restart_count: int | None = Field(default=None, alias="restartCount")
    last_updated: str | None = Field(default=None, alias="lastUpdated")

    @field_validator("state", "last_state", mode="before")
    @staticmethod
    def normalize_container_state(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict) and not value:
            return None
        return value


class PostgresStatus(BaseModel):
    """Status of the Postgres instance."""

    primary: PrimaryStatus | None = Field(default=None)
    standby: list[StandbyStatus] | None = Field(default=None)


class DatabaseStatus(BaseModel):
    """Status of a Database resource."""

    phase: (
        Literal["Pending", "Provisioning", "Running", "Degraded", "Deleting", "Failed"]
        | None
    ) = Field(default=None)
    message: str | None = Field(default=None)
    postgres: PostgresStatus | None = Field(default=None)


class Database(BaseObject):
    """Database resource model."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["Database"] | None = "Database"
    metadata: BaseMetadata = Field(description="Metadata for the Database resource")
    spec: DatabaseSpec = Field(description="Specification for the Database resource")
    status: DatabaseStatus | None = Field(default=None)


class DatabaseList(BaseList[Database]):
    """Paginated list of Database resources."""

    pass
