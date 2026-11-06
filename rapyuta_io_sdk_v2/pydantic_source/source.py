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

"""Pydantic settings source backed by configuration trees."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from benedict import benedict
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from rapyuta_io_sdk_v2 import Client, Configuration

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from rapyuta_io_sdk_v2.models.configtree import ConfigValue


class ConfigTreeSource(PydanticBaseSettingsSource):
    """Load Pydantic settings from a remote or local configuration tree."""

    # Keep the positional signature accepted by existing SDK callers.
    def __init__(  # noqa: PLR0913, PLR0917
        self,
        settings_cls: type[BaseSettings],
        config: Configuration,
        tree_name: str = "default",
        key_prefix: str = "",
        with_project: bool = True,  # noqa: FBT001, FBT002
        local_file: str | None = None,
    ) -> None:
        """Initialize the instance with the supplied configuration.

        Args:
            settings_cls: Pydantic settings model receiving the tree values.
            config: SDK authentication and environment configuration.
            tree_name: Remote configuration tree to load.
            key_prefix: Top-level tree prefix removed from settings keys.
            with_project: Load the tree in the configured project scope.
            local_file: JSON or YAML file to load instead of the remote tree.
        """
        super().__init__(settings_cls)
        self._client = Client(config=config)
        self._tree_name = tree_name
        self._local_file = local_file
        self._top_prefix = key_prefix
        self._with_project = with_project

        self._configtree_data = benedict(self._load_config_tree()).unflatten(
            separator="/"
        )

    # * Methods to fetch Configtree
    def _fetch_from_api(self) -> dict[str, Any]:
        """Load the configuration tree from an external API."""
        response = self._client.get_configtree(
            name=self._tree_name,
            include_data=True,
            content_types=["kv"],
            key_prefixes=[self._top_prefix],
            with_project=self._with_project,
        )
        if response.keys is None:
            message = (
                f"'keys' not found in response for config tree '{self._tree_name}' "
                f"with prefix '{self._top_prefix}'"
            )
            raise KeyError(message)

        return self._extract_data_api(input_data=response.keys)

    def _load_from_local_file(self) -> dict[str, Any]:
        """Load the configuration tree from a local JSON or YAML file."""
        data = {}
        file_prefix = Path(self._local_file).stem
        file_suffix = Path(self._local_file).suffix[1:]

        if file_suffix not in ["json", "yaml", "yml"]:
            message = "Unsupported file format. Use .json or .yaml/.yml."
            raise ValueError(message)

        content = Path(self._local_file).read_text(encoding="utf-8")
        data[file_prefix] = benedict(content, format=file_suffix)
        content = self._split_metadata(data)
        return benedict(content).flatten(separator="/")

    def _load_config_tree(self) -> dict[str, Any]:
        """Load config tree."""
        if self._local_file:
            self.config_tree = self._load_from_local_file()

        else:
            self.config_tree = self._fetch_from_api()

        processed_data = self._process_config_tree(raw_data=self.config_tree)

        if processed_data is None:
            message = "processed_data cannot be None"
            raise ValueError(message)
        return processed_data

    # * Methods to process the tree
    def _extract_data_api(self, input_data: dict[str, ConfigValue]) -> dict[str, Any]:
        """Extract data api.

        Args:
            input_data: Input data.
        """
        return {
            key: self._decode_value(value.data)
            for key, value in input_data.items()
            if value.data is not None
        }

    def _decode_value(self, encoded_data: str) -> object:
        """Decode value.

        Args:
            encoded_data: Encoded data.
        """
        decoded_data = base64.b64decode(encoded_data).decode("utf-8")

        try:
            return json.loads(decoded_data)
        except (ValueError, SyntaxError):
            return decoded_data

    def _split_metadata(self, data: object) -> object:
        """Remove metadata wrappers while preserving scalar and collection values."""
        if not isinstance(data, dict):
            return data
        content = {}
        for key, value in data.items():
            if isinstance(value, dict) and self._is_metadata_wrapper(value):
                content[key] = value["value"]
            else:
                content[key] = self._split_metadata(value)
        return content

    @staticmethod
    def _is_metadata_wrapper(value: dict[str, Any]) -> bool:
        return set(value) == {"value", "metadata"} and isinstance(
            value["metadata"], dict
        )

    def _process_config_tree(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Remove the configured tree prefix from flattened keys."""
        prefix_length = len(self._top_prefix)
        if prefix_length == 0:
            return raw_data
        return {key[prefix_length + 1 :]: value for key, value in raw_data.items()}

    def __call__(self) -> dict[str, Any]:
        """Return configuration values for the declared settings fields."""
        if self.settings_cls.model_config.get("extra") == "allow":
            return self._configtree_data
        d: dict[str, Any] = {}

        for field_name, field in self.settings_cls.model_fields.items():
            field_value, field_key, _value_is_complex = self.get_field_value(
                field=field, field_name=field_name
            )

            if field_value is not None:
                d[field_key] = field_value
        return d

    # Pydantic requires the field argument; lookup only uses its name.
    def get_field_value(
        self,
        field: FieldInfo,  # noqa: ARG002
        field_name: str,
    ) -> tuple[Any, str, bool]:
        """Return a settings value, its key, and whether it is a collection.

        Args:
            field: Pydantic field descriptor required by the settings source interface.
            field_name: Key to look up in the configuration tree.
        """
        value = self._configtree_data.get(field_name)
        return value, field_name, isinstance(value, (list, dict))
