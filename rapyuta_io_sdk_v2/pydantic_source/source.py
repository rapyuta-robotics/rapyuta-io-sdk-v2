import ast
from typing import Any, Type, Dict, Iterable
from benedict import benedict
from pathlib import Path

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource
from pydantic.fields import FieldInfo

from rapyuta_io_sdk_v2 import Client, Configuration
import base64


class ConfigTreeSource(PydanticBaseSettingsSource):
    def __init__(
        self,
        settings_cls: Type["BaseSettings"],
        config: Configuration,
        tree_name: str = "default",
        key_prefix: str = "",
        with_project: bool = True,
        local_file: str = None,
    ):
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
    def _fetch_from_api(self):
        """
        Load the configuration tree from an external API.
        """
        response = self._client.get_configtree(
            name=self._tree_name,
            include_data=True,
            content_types="kv",
            key_prefixes=[self._top_prefix],
            with_project=self._with_project,
        )
        if "keys" not in response:
            raise KeyError(
                f"'keys' not found in response for config tree '{self._tree_name}' "
                f"with prefix '{self._top_prefix}'"
            )
        return self._extract_data_api(input_data=response["keys"].toDict())

    def _load_from_local_file(self):
        """
        Load the configuration tree from a local JSON or YAML file.
        """
        data = {}
        file_prefix = Path(self._local_file).stem
        file_suffix = Path(self._local_file).suffix[1:]

        if file_suffix not in ["json", "yaml", "yml"]:
            raise ValueError("Unsupported file format. Use .json or .yaml/.yml.")

        data[file_prefix] = benedict(self._local_file, format=file_suffix)
        content = self._split_metadata(data)
        return benedict(content).flatten(separator="/")

    def _load_config_tree(self):
        if self._local_file:
            self.config_tree = self._load_from_local_file()

        else:
            self.config_tree = self._fetch_from_api()

        processed_data = self._process_config_tree(raw_data=self.config_tree)

        if processed_data is None:
            raise ValueError("processed_data cannot be None")
        return processed_data

    # * Methods to process the tree
    def _extract_data_api(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: self._decode_value(value.get("data"))
            for key, value in input_data.items()
            if "data" in value
        }

    def _decode_value(self, encoded_data: str) -> Any:
        decoded_data = base64.b64decode(encoded_data).decode("utf-8")

        try:
            # Safely evaluate the decoded string to Python data structures (e.g., lists, dicts)
            return ast.literal_eval(decoded_data)
        except (ValueError, SyntaxError):
            return decoded_data

    def _split_metadata(self, data: Iterable) -> Iterable:
        """Helper function to split data and metadata from the input data."""
        if not isinstance(data, dict):
            return data

        content = {}

        for key, value in data.items():
            if not isinstance(value, dict):
                content[key] = value
                continue

            potential_content = value.get("value")
            potential_meta = value.get("metadata")

            if (
                len(value) == 2
                and potential_content is not None
                and potential_meta is not None
                and isinstance(potential_meta, dict)
            ):
                content[key] = potential_content
                continue

            content[key] = self._split_metadata(value)

        return content

    # * This method is extracting the data from the raw data and removing the top level prefix
    def _process_config_tree(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        prefix_length = len(self._top_prefix)

        if prefix_length == 0:
            return raw_data

        for key in raw_data:
            processed_key = key[prefix_length + 1 :]
            d[processed_key] = raw_data[key]

        return d

    def __call__(self) -> dict[str, Any]:
        if self.settings_cls.model_config.get("extra") == "allow":
            return self._configtree_data
        d: Dict[str, Any] = {}

        for field_name, field in self.settings_cls.model_fields.items():
            field_value, field_key, value_is_complex = self.get_field_value(
                field=field, field_name=field_name
            )

            if field_value is not None:
                d[field_key] = field_value
        return d

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        value = self._configtree_data.get(field_name)
        if value is None:
            return None, field_name, False

        if isinstance(value, list) or isinstance(value, dict):
            return value, field_name, True

        return value, field_name, False
