from fastapi import FastAPI
from typing import Type, Tuple, Any

from pydantic import Field, BaseModel
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
)

from rapyuta_io_sdk_v2 import Configuration
from rapyuta_io_sdk_v2.pydantic_source import ConfigTreeSource

app = FastAPI()

TREE_NAME = "default"
KEY_PREFIX = "default"
LOCAL_FILE = "default.json"


# Provider implementation
class AuthConfig(BaseSettings):
    # Before starting the application, you need to set the environment variables in .env.sample file and rename it to .env
    model_config = SettingsConfigDict(env_file=".env")

    env: str
    auth_token: str = Field(alias="RIO_AuthToken")
    organization_guid: str = Field(alias="RIO_ORGANIZATION_ID")
    project_guid: str = Field(alias="RIO_PROJECT_ID")

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        cls.__init__(instance, *args, **kwargs)

        return Configuration(
            auth_token=instance.auth_token.removeprefix("Bearer "),
            environment=instance.env,
            organization_guid=instance.organization_guid,
            project_guid=instance.project_guid,
        )


class NestedTree(BaseModel):
    services: Any = "default-api-services"
    host: Any = "default-api-host"


class RRTreeSource(BaseSettings):
    """
    This method fetches the configuration tree from an external API and extracts the 'apis' and 'common' sections from the config tree if they are present.
    You can specify which sections to extract from the config tree in the model_config by providing the section name as a key and the default value as the value.
    If the section is not present in the config tree, the default value will be used.

    For example, if you want to extract the 'oks' section from the config tree and the default value is "default-oks", you can define it as shown below:
    oks: Any = Field(default="default-oks")
    """

    model_config = (
        SettingsConfigDict()
    )  # Use extra='allow' in SettingsConfigDict to see full configtree.

    apis: Any = Field(default="default-rr_services")
    common: Any = Field(default="default-common")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            ConfigTreeSource(
                config=AuthConfig(),
                settings_cls=settings_cls,
                key_prefix=KEY_PREFIX,
                tree_name=TREE_NAME,
                local_file="",
                # api_with_project=False,
            ),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


class RRTreeSourceWithPrefix(BaseSettings):
    """
    This method also fetches the configuration tree from an external API and extracts the 'apis' and 'common' sections from the config tree if they are present.
    But here we define key_prefix which ignores the prefix in the config tree and extracts the 'apis' and 'common' sections directly.
    For example, if the config tree has the following structure:
    {
        "default": {
            "apis": {
                "services": "temp_services"
            },
            "common": "common"
        }
    }
    Here we will define key_prefix as "default".
    The model will come out as:
    {
        "apis": {
            "services": "temp_services"
            "host": "default-api-host"
        },
        "common": "common"
    }

    Note: Here api_host has default value because any value was not provided in the config tree.
    """

    model_config = SettingsConfigDict()

    apis: NestedTree = NestedTree()
    common: Any = Field(default="default-common")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            ConfigTreeSource(
                config=AuthConfig(),
                settings_cls=settings_cls,
                key_prefix=KEY_PREFIX,
                tree_name=TREE_NAME,
                local_file="",
                # api_with_project=False,
            ),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


class ApisNestedModel(BaseModel):
    services: Any = Field(default="default-services")


class NestedModel(BaseModel):
    apis: ApisNestedModel = ApisNestedModel()
    common: Any = Field(default="default_nested_common")


class RRTreeSourceLocal(BaseSettings):
    """
    This method reads the configuration tree from a local file and extracts the 'apis' and 'common' sections if they exist.
    You can specify which sections to extract by providing the section name and a default value in the model_config.
    If a section is missing in the config tree, the default value will be used.

    For example, if your local file (default.json) has this structure:
    {
        "default": {
            "apis": {
                "rr_services": "rr_services"
            },
            "common": "common"
        }
    }

    Without a key prefix, the model will look like this:
    {
    "default": {
        "apis": {
        "services": "services inside the local file"
        },
        "common": "common in local file"
    },
    "apis": "default_apis",
    "common": "default_common"
    }

    With a key prefix ("default"), the model will look like this:
    {
    "default": {
        "apis": {
        "services": "default-services"
        },
        "common": "default_nested_common"
    },
    "apis": {
        "services": "services inside the local file"
    },
    "common": "common in local file"
    }
    """

    model_config = SettingsConfigDict()

    default: NestedModel = NestedModel()
    apis: Any = Field(default="default_apis")
    common: Any = Field(default="default_common")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
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
async def get_full_configtree():
    """Retrieve the full configuration tree"""
    return config_tree.model_dump()


@app.get("/configtrees1")
def get_configtree1():
    return config_tree_with_prefix.model_dump()


@app.get("/configtrees_local")
def get_configtrees_local():
    return config_tree_with_file.model_dump()


# Test function
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
