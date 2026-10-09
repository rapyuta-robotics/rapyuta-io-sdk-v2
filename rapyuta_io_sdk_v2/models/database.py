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


"""Pydantic models for Database and Backup resources."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    SecretKeyRef,
)


class DeviceSpec(SDKModel):
    """Device placement for a Postgres instance."""

    device_name: str = Field(alias="deviceName")
    device_guid: str | None = Field(alias="deviceGuid", default=None)
    data_directory: str | None = Field(alias="dataDirectory", default=None)
    port: int | None = Field(default=None)


class Credentials(SDKModel):
    """References to Postgres username and password secret keys.

    Only ``name``+``key`` are sent on create; the apiserver resolves
    ``value`` onto the device-facing copy and never persists it. Immutable after
    creation.
    """

    username: SecretKeyRef | None = Field(default=None)
    password: SecretKeyRef | None = Field(default=None)


class PostgresUsers(SDKModel):
    """Secret references for Postgres users."""

    primary: Credentials | None = Field(default=None)
    backup: Credentials | None = Field(default=None)
    # Streaming-replication user consumed by standbys. Server-generated into the
    # managed secret on create; read-only, with ``value`` blanked on read.
    replication: Credentials | None = Field(default=None)


class StandbySpec(SDKModel):
    """Optional hot-standby topology.

    Each standby sits on a distinct device from the primary and other standbys.
    """

    primary_interface: str | None = Field(alias="primaryInterface", default=None)
    # Server-managed: resolved from the primary device record; consumed by
    # standby devices as the replication host.
    primary_host: str | None = Field(alias="primaryHost", default=None)
    # Network the primary trusts for replication in its pg_hba.conf. Defaults
    # server-side to 10.0.0.0/8 (the postgres image's own default) when omitted;
    # set it when the fleet sits on a different network.
    cidr: str | None = Field(default=None)
    devices: list[DeviceSpec] | None = Field(default=None)


class PostgresParameters(SDKModel):
    """Tunable ``postgresql.conf`` parameters.

    Omitted fields keep the Postgres defaults.
    """

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


class PostgresSpec(SDKModel):
    """Specification for a PostgreSQL database instance."""

    version: Literal["16", "17", "18"]
    postgres_image: str | None = Field(alias="postgresImage", default=None)

    primary: DeviceSpec
    standby: StandbySpec | None = Field(default=None)
    users: PostgresUsers | None = Field(default=None)
    multiple_database: list[str] | None = Field(default=None, alias="multipleDatabase")
    parameters: PostgresParameters | None = Field(default=None)


class DatabaseSpec(SDKModel):
    """Specification for a Database resource."""

    type: Literal["postgres"] = Field(default="postgres")
    postgres: PostgresSpec | None = Field(default=None)


class ContainerState(SDKModel):
    """Container state details."""

    status: str | None = Field(
        default=None, description="running | terminated | waiting"
    )
    started_at: str | None = Field(default=None, alias="startedAt")


class InstanceStatus(SDKModel):
    """Status of one Postgres instance on one device.

    Primary and standby instances report the same shape. The aliases keep names at
    the call sites self-describing.
    """

    device_name: str = Field(alias="deviceName")
    port: int
    phase: str | None = Field(
        default=None,
        description="provisioning | starting | running | stopped | failed",
    )
    message: str | None = Field(default=None)
    state: ContainerState | None = Field(default=None)
    last_state: ContainerState | None = Field(default=None, alias="lastState")
    restart_count: int | None = Field(default=None, alias="restartCount")
    last_updated: str | None = Field(default=None, alias="lastUpdated")

    @field_validator("state", "last_state", mode="before")
    @staticmethod
    def normalize_container_state(value: object) -> object:
        """Normalize empty container states returned by the API.

        Args:
            value: Raw API state value.
        """
        if isinstance(value, dict) and not value:
            return None
        return value


PrimaryStatus = InstanceStatus
StandbyStatus = InstanceStatus


class PostgresStatus(SDKModel):
    """Status of the Postgres instance."""

    primary: PrimaryStatus | None = Field(default=None)
    standby: list[StandbyStatus] | None = Field(default=None)


class DatabaseStatus(SDKModel):
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
