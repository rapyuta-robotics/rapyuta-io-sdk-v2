# -*- coding: utf-8 -*-
# Copyright 2024 Rapyuta Robotics
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
from typing import Optional, Tuple, Type

from pydantic_settings import (
    BaseSettings,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from pydantic_configs.app_config_source import RRConfigSettingsSource
from rapyuta_io_sdk_v2 import Configuration


class RIOAuthCredentials(BaseSettings):
    rio_auth_token: str = ""
    rio_organisation_guid: str = ""
    rio_project_id: str = ""


class RIOConfigTree(BaseSettings):
    config_tree_name: str = ""
    config_tree_revision: Optional[str] = None


class RRSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="allow")

    rio_auth_token: str = ""
    config_tree_name: str
    config_tree_version: Optional[str] = None
    rio_organisation_guid: str = ""
    rio_project_id: str = ""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: InitSettingsSource,  # overriding the default init settings
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:

        rio_auth_creds = RIOAuthCredentials()
        rio_config_tree = RIOConfigTree()

        rio_auth_token = init_settings.init_kwargs.get(
            "rio_auth_token", rio_auth_creds.rio_auth_token
        )
        rio_organisation_guid = init_settings.init_kwargs.get(
            "rio_organisation_guid", rio_auth_creds.rio_organisation_guid
        )
        rio_project_id = init_settings.init_kwargs.get(
            "rio_project_id", rio_auth_creds.rio_project_id
        )
        config_tree_name = init_settings.init_kwargs.get(
            "config_tree_name", rio_config_tree.config_tree_name
        )
        config_tree_revision = init_settings.init_kwargs.get(
            "config_tree_version", rio_config_tree.config_tree_revision
        )

        _client_config = Configuration(
            auth_token=rio_auth_token,
            project_guid=rio_project_id,
            organization_guid=rio_organisation_guid
        )

        rr_config_settings_source = RRConfigSettingsSource(
            settings_cls,
            client_config=_client_config,
            config_tree_name=config_tree_name,
            config_tree_revision=config_tree_revision,
        )

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            rr_config_settings_source,
        )