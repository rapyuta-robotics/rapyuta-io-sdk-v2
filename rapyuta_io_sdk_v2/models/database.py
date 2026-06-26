"""
Pydantic models for Database and Backup resources.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject


class DeviceSpec(BaseModel):
    """Device placement for a Postgres instance."""

    device_name: str = Field(alias="deviceName")
    device_guid: str | None = Field(alias="deviceGuid", default=None)
    data_directory: str | None = Field(alias="dataDirectory", default=None)
    port: int | None = Field(default=None)


class Credentials(BaseModel):
    """Database credentials (password is immutable after creation)."""

    username: str
    password: str | None = Field(default=None)


class PostgresParameters(BaseModel):
    max_connections: str = Field(default="200")
    shared_buffers: str = Field(default="512MB")


class PostgresSpec(BaseModel):
    """Specification for a PostgreSQL database instance."""

    version: Literal["16", "17", "18"]
    postgres_image: str = Field(alias="postgresImage")

    primary: DeviceSpec
    credentials: Credentials
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


class PostgresStatus(BaseModel):
    """Status of the Postgres instance."""

    primary: PrimaryStatus | None = Field(default=None)


class DatabaseStatus(BaseModel):
    """Status of a Database resource."""

    phase: Literal["Pending", "Provisioning", "Running", "Degraded", "Deleting", "Failed"] | None = Field(default=None)
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
