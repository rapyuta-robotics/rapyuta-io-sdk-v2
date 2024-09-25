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
import asyncio
from typing import Any, Optional, Tuple, Type
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from rapyuta_io_sdk_v2.config import Configuration


class RRConfigSettingsSource(PydanticBaseSettingsSource):
    def __init__(
        self,
        settings_cls: Type[BaseSettings],
        client_config: Configuration,
        config_tree_name: str,
        config_tree_revision: Optional[str] = None,
    ):
        self._config_tree = None
        self.config_tree_aysnc_client = client_config.async_client()
        self.config_tree_name = config_tree_name
        self.config_tree_revision = config_tree_revision

        current_loop = asyncio.get_event_loop()
        current_loop.run_until_complete(
            self._retrieve_config_tree()
        )

        super().__init__(
            settings_cls,
        )

    async def _retrieve_config_tree(self) -> None:
        res = await self.config_tree_aysnc_client.get_config_tree(
            tree_name=self.config_tree_name,
            rev_id=self.config_tree_revision,
            include_data=True
        )
        self._config_tree = res

    def get_field_value(
        self,
        field: FieldInfo,
        field_name: str,
    ) -> Tuple[Any, str]:
        return "str","str"

    def get_value(self, key: str) -> Optional[Any]:
        keys = key.split('.')
        value = self._config_tree

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return None

    def __call__(self):
        return self._config_tree