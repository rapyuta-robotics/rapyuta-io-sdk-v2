"""Shared Pydantic data model without resource operations."""

from pydantic import BaseModel, ConfigDict


class SDKModel(BaseModel):
    """Common data model accepting Python names and explicit API aliases."""

    model_config = ConfigDict(populate_by_name=True)
