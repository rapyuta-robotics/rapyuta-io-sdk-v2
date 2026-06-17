"""
Pydantic models for Database and Backup resources.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject


class DeviceSpec(BaseModel):
    """Device placement for a Postgres instance."""

    device_name: str = Field(alias="deviceName")
    data_directory: str = Field(alias="dataDirectory")
    port: int = Field(default=5432)


class Credentials(BaseModel):
    """Database credentials (password is immutable after creation)."""

    username: str
    password: str | None = Field(default=None)


class PostgresSpec(BaseModel):
    """Specification for a PostgreSQL database instance."""

    version: str
    primary: DeviceSpec
    credentials: Credentials
    multiple_database: list[str] | None = Field(
        default=None, alias="multipleDatabase"
    )
    parameters: dict[str, str] | None = Field(default=None)


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


class Condition(BaseModel):
    """Kubernetes-style condition."""

    type: str
    status: Literal["True", "False", "Unknown"]
    reason: str | None = Field(default=None)
    message: str | None = Field(default=None)
    last_transition_time: str | None = Field(
        default=None, alias="lastTransitionTime"
    )


class PrimaryStatus(BaseModel):
    """Status of the Postgres primary container."""

    device_name: str = Field(alias="deviceName")
    port: int
    phase: str | None = Field(default=None)
    message: str | None = Field(default=None)
    state: ContainerState | None = Field(default=None)
    last_state: ContainerState | None = Field(default=None, alias="lastState")
    restart_count: int | None = Field(default=None, alias="restartCount")
    conditions: list[Condition] | None = Field(default=None)
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

    phase: str | None = Field(default=None)
    message: str | None = Field(default=None)
    postgres: PostgresStatus | None = Field(default=None)
    conditions: list[Condition] | None = Field(default=None)


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
