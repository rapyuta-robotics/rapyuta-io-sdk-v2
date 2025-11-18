"""
Pydantic models for Daemon resource validation.

This module contains Pydantic models that correspond to the Daemon JSON schema,
providing validation for Daemon resources to help users identify missing or
incorrect fields.
"""

from typing import Literal
from pydantic import BaseModel, Field

from rapyuta_io_sdk_v2.models.utils import BaseMetadata


# --- Daemon Status Types ---
DaemonStatusType = Literal["error", "running", "pending", "terminating", "terminated"]


# --- Configuration Models ---
class TracingConfig(BaseModel):
    """Tracing configuration for daemons."""

    enable: bool = Field(description="Enable tracing")
    collector_endpoint: str | None = Field(
        default=None, description="Collector endpoint for tracing"
    )


class AuthConfig(BaseModel):
    """Authentication configuration for pull secrets."""

    # This is a simplified AuthConfig for daemon pull secrets
    # Add specific fields as needed based on actual requirements
    username: str | None = Field(default=None, description="Username for authentication")
    password: str | None = Field(default=None, description="Password for authentication")
    registry: str | None = Field(default=None, description="Registry URL")


class VPNConfig(BaseModel):
    """VPN configuration for daemons."""

    enable: bool = Field(description="Enable VPN")
    headscale_pre_auth_key: str | None = Field(
        default=None, description="Headscale pre-authentication key"
    )
    headscale_url: str | None = Field(default=None, description="Headscale URL")
    headscale_acl_tag: str | None = Field(default=None, description="Headscale ACL tag")
    advertise_routes: str | None = Field(default=None, description="Routes to advertise")


class TelegrafConfig(BaseModel):
    """Telegraf configuration for daemons."""

    enable: bool = Field(description="Enable Telegraf")


class DockerProxyConfig(BaseModel):
    """Docker proxy configuration."""

    registry: str | None = Field(default=None, description="Registry URL")
    username: str | None = Field(
        default=None, description="Username for proxy authentication"
    )
    password: str | None = Field(
        default=None, description="Password for proxy authentication"
    )
    dataDirectory: str | None = Field(default=None, description="Data directory path")


class DockerMirrorConfig(BaseModel):
    """Docker mirror configuration."""

    url: str | None = Field(default=None, description="Mirror URL")


class DockerCacheConfig(BaseModel):
    """Docker cache configuration for daemons."""

    enable: bool = Field(description="Enable Docker cache")
    proxy: DockerProxyConfig | None = Field(
        default=None, description="Docker proxy configuration"
    )
    mirror: DockerMirrorConfig | None = Field(
        default=None, description="Docker mirror configuration"
    )


# --- Daemon Specification ---
class DaemonSpec(BaseModel):
    """Specification for Daemon resource."""

    tracing_config: TracingConfig | None = Field(
        default=None, description="Tracing configuration"
    )
    pull_secret: AuthConfig | None = Field(
        default=None, description="Pull secret configuration"
    )
    vpn_config: VPNConfig | None = Field(default=None, description="VPN configuration")
    telegraf_config: TelegrafConfig | None = Field(
        default=None, description="Telegraf configuration"
    )
    docker_cache_config: DockerCacheConfig | None = Field(
        default=None, description="Docker cache configuration"
    )


# --- Daemon Status ---
class DaemonStatus(BaseModel):
    """Status information for a daemon."""

    enable: bool = Field(description="Whether daemon is enabled or not")
    status: DaemonStatusType | None = Field(
        default=None,
        description="Status of the daemon (pending, running, error, terminating, terminated)",
    )
    error_code: str | None = Field(
        default=None, description="Error code associated with the daemon"
    )
    reason: str | None = Field(
        default=None, description="Reason for the status of the daemon"
    )
    restart_count: int = Field(
        default=0, description="Number of times the daemon has been restarted"
    )
    exit_code: int = Field(
        default=0, description="Exit status code from the termination of the daemon"
    )


# --- Main Daemon Model ---
class Daemon(BaseModel):
    """Daemon model."""

    # TypeMeta fields (inline)
    apiVersion: str | None = Field(
        default="api.rapyuta.io/v2",
        description="APIVersion defines the versioned schema of this representation of an object",
    )
    kind: str = Field(
        default="Daemon",
        description="Kind is a string value representing the REST resource this object represents",
    )

    # ObjectMeta
    metadata: BaseMetadata

    # Daemon-specific fields
    spec: DaemonSpec = Field(default=None, description="Daemon specification")
    status: dict[str, DaemonStatus | None] | None = Field(
        default=None, description="Status of the daemon by component"
    )
