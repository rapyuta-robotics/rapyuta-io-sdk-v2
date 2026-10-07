"""Validated SDK settings composed from arguments, environment, and rio-cli."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    SettingsError,
)

from rapyuta_io_sdk_v2.constants import (
    APP_NAME,
    NAMED_ENVIRONMENTS,
    STAGING_ENVIRONMENT_SUBDOMAIN,
)
from rapyuta_io_sdk_v2.features import FeatureFlags
from rapyuta_io_sdk_v2.utils import get_default_app_dir

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.context import RequestContext


class RioCliSettingsSource(JsonConfigSettingsSource):
    """Use Pydantic's JSON reader, normalizing only rio-cli's key names."""

    KEY_NAMES = {
        "email_id": "email",
        "project_id": "project_guid",
        "organization_id": "organization_guid",
        "v2api_host": "v2_api_host",
    }

    def _read_file(self, file_path: Path) -> dict[str, Any]:
        data = super()._read_file(file_path)
        if not isinstance(data, dict):
            raise ValueError("rio-cli configuration must be a JSON object")
        return data

    def __call__(self) -> dict[str, Any]:
        data = super().__call__()
        for cli_name, sdk_name in self.KEY_NAMES.items():
            if cli_name in data:
                data.setdefault(sdk_name, data.pop(cli_name))
        return data


class Configuration(BaseSettings):
    """Settings priority: arguments, RIO_ variables, rio-cli JSON, defaults.

    Set ``load_cli_config=False`` to disable file loading. ``config_file`` or
    ``RIO_CONFIG`` selects a required file; the implicit default file is optional.
    Construction performs no network requests and never writes the file.
    """

    model_config = SettingsConfigDict(
        env_prefix="RIO_",
        env_nested_delimiter="__",
        extra="ignore",
        validate_assignment=True,
    )

    email: str | None = None
    password: str | None = Field(default=None, repr=False)
    auth_token: str | None = Field(default=None, repr=False)
    project_guid: str | None = None
    organization_guid: str | None = None
    project_name: str | None = None
    organization_name: str | None = None
    organization_short_id: str | None = None
    environment: str = "ga"
    v2_api_host: str | None = None
    core_api_host: str | None = None
    rip_host: str | None = None
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    config_file: Path | None = Field(default=None, exclude=True)
    load_cli_config: bool = Field(default=True, exclude=True)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        selected = {**env_settings(), **init_settings()}
        load_file = selected.get("load_cli_config", True)
        if isinstance(load_file, str):
            load_file = load_file.lower() not in ("false", "0", "no", "off")
        if not load_file:
            return init_settings, env_settings
        explicit_path = selected.get("config_file") or os.getenv("RIO_CONFIG")
        path = Path(explicit_path or Path(get_default_app_dir(APP_NAME)) / "config.json")
        if explicit_path and not path.is_file():
            raise SettingsError(f"rio-cli configuration file not found: {path}")
        try:
            source = RioCliSettingsSource(settings_cls, json_file=path)
        except (OSError, ValueError, TypeError) as exc:
            raise SettingsError(
                f"cannot read rio-cli configuration file {path}: {exc}"
            ) from exc
        return init_settings, env_settings, source

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, value):
        value = value or "ga"
        if not isinstance(value, str) or (
            value not in (*NAMED_ENVIRONMENTS, "local") and not value.startswith("pr")
        ):
            raise ValueError("invalid environment")
        return value

    @field_validator("v2_api_host", "core_api_host", "rip_host", mode="before")
    @classmethod
    def normalize_host(cls, value):
        if isinstance(value, str):
            return value.strip().rstrip("/") or None
        return value

    @property
    def resolved_v2_api_host(self) -> str:
        if self.v2_api_host:
            return self.v2_api_host
        if self.environment == "local":
            return os.getenv("LOCAL_V2API_HOST") or "http://gateway/io"
        if self.environment == "ga":
            return "https://api.rapyuta.io"
        return f"https://{self.environment}api.{STAGING_ENVIRONMENT_SUBDOMAIN}"

    @property
    def resolved_core_api_host(self) -> str:
        """Server for the legacy Parameter and Device Management APIs."""
        if self.core_api_host:
            return self.core_api_host
        if self.environment == "local":
            return os.getenv("LOCAL_CORE_API_HOST") or "http://apiserver"
        if self.environment == "ga":
            return "https://gaapiserver.apps.okd4v2.prod.rapyuta.io"
        return f"https://{self.environment}apiserver.{STAGING_ENVIRONMENT_SUBDOMAIN}"

    @property
    def resolved_rip_host(self) -> str:
        if self.rip_host:
            return self.rip_host
        if self.environment == "local":
            return os.getenv("LOCAL_RIP_HOST") or "http://rip"
        if self.environment == "ga":
            return "https://garip.apps.okd4v2.prod.rapyuta.io"
        return f"https://{self.environment}rip.{STAGING_ENVIRONMENT_SUBDOMAIN}"

    def get_headers(
        self,
        *,
        with_organization: bool = True,
        organization_guid: str | None = None,
        with_project: bool = True,
        project_guid: str | None = None,
        with_group: bool = False,
        group_guid: str | None = None,
        context: RequestContext | None = None,
        request_id: str | None = None,
        x_checksum: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, str]:
        """Build per-request headers without changing shared settings."""
        if context is not None:
            context_data = context.model_dump(exclude_none=True)
            with_organization = context_data.get("with_organization", with_organization)
            with_project = context_data.get("with_project", with_project)
            with_group = context_data.get("with_group", with_group)
            organization_guid = context_data.get("organization_guid", organization_guid)
            project_guid = context_data.get("project_guid", project_guid)
            group_guid = context_data.get("group_guid", group_guid)
            request_id = context_data.get("request_id", request_id)
            x_checksum = context_data.get("x_checksum", x_checksum)
            content_type = context_data.get("content_type", content_type)
        headers: dict[str, str] = {}
        token = self.auth_token.strip() if self.auth_token else ""
        if token:
            headers["Authorization"] = (
                token if token.lower().startswith("bearer ") else f"Bearer {token}"
            )
        organization_guid = (
            organization_guid if organization_guid is not None else self.organization_guid
        )
        project_guid = project_guid if project_guid is not None else self.project_guid
        if with_organization and organization_guid:
            headers["organizationguid"] = organization_guid
        if with_project and project_guid:
            headers["project"] = project_guid
        if with_group and group_guid:
            headers["groupguid"] = group_guid
        request_id = request_id or os.getenv("REQUEST_ID")
        if request_id:
            headers["X-Request-ID"] = request_id
        for value, wire_name in (
            (x_checksum, "X-Checksum"),
            (content_type, "Content-Type"),
        ):
            if value:
                headers[wire_name] = value
        if context is not None:
            headers.update(context.headers)
        return headers
