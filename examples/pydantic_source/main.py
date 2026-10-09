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

"""Serve configuration tree settings with FastAPI."""

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from rapyuta_io_sdk_v2 import Configuration
from rapyuta_io_sdk_v2.pydantic_source import ConfigTreeSource

app = FastAPI()

TREE_NAME = "default"
KEY_PREFIX = "default"
LOCAL_FILE = "default.json"


# Provider implementation
class AuthConfig(BaseSettings):
    # Copy .env.sample to .env and supply the authentication settings.
    """Authentication settings read from the application environment."""

    model_config = SettingsConfigDict(env_file=".env")

    env: str
    auth_token: str = Field(alias="RIO_AuthToken")
    organization_guid: str = Field(alias="RIO_ORGANIZATION_ID")
    project_guid: str = Field(alias="RIO_PROJECT_ID")

    def __new__(cls, *args: object, **kwargs: object) -> Configuration:
        """Build an SDK configuration from environment settings.

        Args:
            *args: Positional settings arguments forwarded to BaseSettings.
            **kwargs: Keyword settings values forwarded to BaseSettings.
        """
        instance = super().__new__(cls)
        cls.__init__(instance, *args, **kwargs)

        return Configuration(
            auth_token=instance.auth_token.removeprefix("Bearer "),
            environment=instance.env,
            organization_guid=instance.organization_guid,
            project_guid=instance.project_guid,
        )


class NestedTree(BaseModel):
    """Default values for the API services and host settings."""

    services: Any = "default-api-services"
    host: Any = "default-api-host"


class RRTreeSource(BaseSettings):
    """Load named settings sections from a remote configuration tree."""

    model_config = (
        SettingsConfigDict()
    )  # Use extra='allow' in SettingsConfigDict to see full configtree.

    apis: Any = Field(default="default-rr_services")
    common: Any = Field(default="default-common")

    # Pydantic requires this positional hook signature.
    @classmethod
    def settings_customise_sources(  # noqa: PLR0917
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Load the configuration tree before environment and file settings.

        Args:
            settings_cls: Settings cls.
            init_settings: Init settings.
            env_settings: Env settings.
            dotenv_settings: Dotenv settings.
            file_secret_settings: File secret settings.
        """
        return (
            init_settings,
            ConfigTreeSource(
                config=AuthConfig(),
                settings_cls=settings_cls,
                key_prefix=KEY_PREFIX,
                tree_name=TREE_NAME,
                local_file="",
            ),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


class RRTreeSourceWithPrefix(BaseSettings):
    """Load settings from a tree after removing its top-level key prefix."""

    model_config = SettingsConfigDict()

    apis: NestedTree = NestedTree()
    common: Any = Field(default="default-common")

    # Pydantic requires this positional hook signature.
    @classmethod
    def settings_customise_sources(  # noqa: PLR0917
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Load the configuration tree before environment and file settings.

        Args:
            settings_cls: Settings cls.
            init_settings: Init settings.
            env_settings: Env settings.
            dotenv_settings: Dotenv settings.
            file_secret_settings: File secret settings.
        """
        return (
            init_settings,
            ConfigTreeSource(
                config=AuthConfig(),
                settings_cls=settings_cls,
                key_prefix=KEY_PREFIX,
                tree_name=TREE_NAME,
                local_file="",
            ),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


class ApisNestedModel(BaseModel):
    """Default service setting within a local API configuration section."""

    services: Any = Field(default="default-services")


class NestedModel(BaseModel):
    """Local API and common configuration defaults."""

    apis: ApisNestedModel = ApisNestedModel()
    common: Any = Field(default="default_nested_common")


class RRTreeSourceLocal(BaseSettings):
    """Load settings sections from the local configuration tree file."""

    model_config = SettingsConfigDict()

    default: NestedModel = NestedModel()
    apis: Any = Field(default="default_apis")
    common: Any = Field(default="default_common")

    # Pydantic requires this positional hook signature.
    @classmethod
    def settings_customise_sources(  # noqa: PLR0917
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Load the configuration tree before environment and file settings.

        Args:
            settings_cls: Settings cls.
            init_settings: Init settings.
            env_settings: Env settings.
            dotenv_settings: Dotenv settings.
            file_secret_settings: File secret settings.
        """
        return (
            init_settings,
            ConfigTreeSource(
                config=AuthConfig(),
                settings_cls=settings_cls,
                key_prefix="",
                tree_name="",
                local_file=LOCAL_FILE,
            ),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


# Initialize config tree source
config_tree = RRTreeSource()
config_tree_with_prefix = RRTreeSourceWithPrefix()
config_tree_with_file = RRTreeSourceLocal()


@app.get("/configtrees")
async def get_full_configtree() -> dict[str, Any]:
    """Retrieve the full configuration tree."""
    return config_tree.model_dump()


@app.get("/configtrees1")
def get_configtree1() -> dict[str, Any]:
    """Get configtree1."""
    return config_tree_with_prefix.model_dump()


@app.get("/configtrees_local")
def get_configtrees_local() -> dict[str, Any]:
    """Get configtrees local."""
    return config_tree_with_file.model_dump()


# Test function
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
