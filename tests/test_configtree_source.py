"""Lazy, scoped ConfigTree Settings loading without hidden client ownership."""

import base64
import json
from types import SimpleNamespace

import pytest
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings

from rapyuta_io_sdk_v2 import Configuration
from rapyuta_io_sdk_v2.features import FeatureDisabledError
from rapyuta_io_sdk_v2.models.configtree import ConfigTree
from rapyuta_io_sdk_v2.pydantic_source import ConfigTreeSource


class Settings(BaseSettings):
    count: int
    nested: dict = Field(default_factory=dict)
    nullable: str | None = "default"


class CredentialSettings(BaseSettings):
    credentials: dict


def config():
    return Configuration(load_cli_config=False, features={"configtree_source": True})


def encoded(value):
    return base64.b64encode(json.dumps(value).encode()).decode()


def test_network_load_is_lazy_prefix_scoped_and_does_not_close_injected_client():
    calls = []

    def get_configtree(**kwargs):
        calls.append(kwargs)
        return ConfigTree(
            keys={
                "app/count": {"data": encoded(4)},
                "app/nested/name": {"data": encoded("demo")},
                "app/nullable": {"data": encoded(None)},
                "application/count": {"data": encoded(99)},
                "other/count": {"data": encoded(8)},
            }
        )

    client = SimpleNamespace(config=config(), get_configtree=get_configtree)
    source = ConfigTreeSource(
        Settings, client=client, key_prefix="app", with_project=False
    )
    assert not calls
    assert Settings.model_validate(source()).model_dump() == {
        "count": 4,
        "nested": {"name": "demo"},
        "nullable": None,
    }
    assert calls[0]["context"].with_project is False
    assert calls[0]["key_prefixes"] == ["app"]


def test_disabled_feature_precedes_file_or_network_access(tmp_path):
    source = ConfigTreeSource(
        Settings,
        Configuration(load_cli_config=False),
        local_file=tmp_path / "missing.json",
    )
    with pytest.raises(FeatureDisabledError):
        source()


def test_local_file_uses_export_stem_and_unwraps_metadata(tmp_path, monkeypatch):
    path = tmp_path / "app.json"
    path.write_text(
        json.dumps({"count": {"value": 5, "metadata": {}}, "nested": {"flag": True}})
    )
    monkeypatch.setattr(
        "rapyuta_io_sdk_v2.client.Client",
        lambda *a, **kw: pytest.fail("unexpected client construction"),
    )
    source = ConfigTreeSource(
        Settings, config(), key_prefix="app", local_file=path, local_export=True
    )
    assert Settings.model_validate(source()).count == 5


def test_yaml_local_export(tmp_path):
    path = tmp_path / "app.yaml"
    path.write_text("count: 7\n")
    assert (
        ConfigTreeSource(Settings, config(), key_prefix="app", local_file=path)()["count"]
        == 7
    )


def test_local_settings_preserve_value_and_metadata_application_fields(tmp_path):
    path = tmp_path / "app.json"
    credentials = {"value": "token", "metadata": {"scope": "reader"}}
    path.write_text(json.dumps({"credentials": credentials}))
    source = ConfigTreeSource(
        CredentialSettings, config(), key_prefix="app", local_file=path
    )
    assert CredentialSettings.model_validate(source()).credentials == credentials


def test_local_export_unwraps_record_without_unwrapping_its_application_value(tmp_path):
    path = tmp_path / "app.json"
    credentials = {"value": "token", "metadata": {"scope": "reader"}}
    path.write_text(json.dumps({"credentials": {"value": credentials, "metadata": {}}}))
    source = ConfigTreeSource(
        CredentialSettings, config(), key_prefix="app", local_file=path, local_export=True
    )
    assert CredentialSettings.model_validate(source()).credentials == credentials


def test_settings_alias_choices():
    class AliasedSettings(BaseSettings):
        count: int = Field(validation_alias=AliasChoices("wireCount", "oldCount"))

    client = SimpleNamespace(
        config=config(),
        get_configtree=lambda **kw: ConfigTree(keys={"oldCount": {"data": encoded(6)}}),
    )
    result = ConfigTreeSource(AliasedSettings, client=client)()
    assert AliasedSettings.model_validate(result).count == 6


def test_base64_and_path_conflicts_fail_explicitly():
    source = ConfigTreeSource(
        Settings,
        config(),
        client=SimpleNamespace(
            get_configtree=lambda **kw: ConfigTree(keys={"count": {"data": "!"}})
        ),
    )
    with pytest.raises(ValueError):
        source()
    client = SimpleNamespace(
        config=config(),
        get_configtree=lambda **kw: ConfigTree(
            keys={"nested": {"data": encoded(1)}, "nested/name": {"data": encoded(2)}}
        ),
    )
    with pytest.raises(ValueError, match="conflicting"):
        ConfigTreeSource(Settings, client=client)()


def test_owned_client_closed_on_fetch_failure(monkeypatch):
    calls = []

    class OwnedClient:
        def __init__(self, config):
            pass

        def get_configtree(self, **kwargs):
            raise RuntimeError("fetch failed")

        def close(self):
            calls.append("close")

    monkeypatch.setattr("rapyuta_io_sdk_v2.client.Client", OwnedClient)
    with pytest.raises(RuntimeError, match="fetch failed"):
        ConfigTreeSource(Settings, config())()
    assert calls == ["close"]


def test_snake_field_input_is_emitted_under_settings_alias_including_null():
    class AliasedSettings(BaseSettings):
        count: int | None = Field(validation_alias="wireCount")

    for value in (6, None):
        client = SimpleNamespace(
            config=config(),
            get_configtree=lambda value=value, **kw: ConfigTree(
                keys={"count": {"data": encoded(value)}}
            ),
        )
        source = ConfigTreeSource(AliasedSettings, client=client)
        assert AliasedSettings.model_validate(source()).count == value


def test_empty_remote_configtree_is_an_empty_source():
    client = SimpleNamespace(config=config(), get_configtree=lambda **kw: ConfigTree())
    assert ConfigTreeSource(Settings, client=client)() == {}


def test_alias_paths_share_namespace_and_accept_null_field_names():
    from pydantic import AliasPath

    class NestedAliases(BaseSettings):
        count: int | None = Field(validation_alias=AliasPath("service", "count"))
        name: str = Field(validation_alias=AliasPath("service", "name"))
        flag: bool = Field(validation_alias=AliasPath("flags", 0))

    client = SimpleNamespace(
        config=config(),
        get_configtree=lambda **kw: ConfigTree(
            keys={
                "count": {"data": encoded(None)},
                "name": {"data": encoded("demo")},
                "flag": {"data": encoded(True)},
            }
        ),
    )
    source = ConfigTreeSource(NestedAliases, client=client)
    settings = NestedAliases.model_validate(source())
    assert settings.count is None
    assert settings.name == "demo"
    assert settings.flag is True


def test_dictionary_leaf_cannot_also_be_a_path_parent():
    client = SimpleNamespace(
        config=config(),
        get_configtree=lambda **kw: ConfigTree(
            keys={
                "nested": {"data": encoded({"name": "one"})},
                "nested/other": {"data": encoded("two")},
            }
        ),
    )
    with pytest.raises(ValueError, match="conflicting"):
        ConfigTreeSource(Settings, client=client)()


def test_sibling_alias_list_positions_preserve_explicit_null():
    from pydantic import AliasPath

    class ListAliases(BaseSettings):
        first: bool | None = Field(validation_alias=AliasPath("flags", 0))
        second: bool = Field(validation_alias=AliasPath("flags", 1))

    client = SimpleNamespace(
        config=config(),
        get_configtree=lambda **kw: ConfigTree(
            keys={
                "first": {"data": encoded(None)},
                "second": {"data": encoded(False)},
            }
        ),
    )
    settings = ListAliases.model_validate(ConfigTreeSource(ListAliases, client=client)())
    assert settings.first is None
    assert settings.second is False
