from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field
from rapyuta_io_sdk_v2.models.utils import BaseList, SDKModel


class OAuth2UpdateURI(SDKModel):
    redirect_uris: list[str] | None = Field(alias="redirectURIs")
    post_logout_redirect_uris: list[str] | None = Field(alias="postLogoutRedirectURIs")


class OAuth2ClientCreate(SDKModel):
    """OAuth2 registration body using the endpoint's standard snake_case keys."""

    model_config = ConfigDict(extra="allow")
    client_id: str | None = None
    client_name: str | None = None
    client_secret: str | None = None
    redirect_uris: list[str] | None = None
    post_logout_redirect_uris: list[str] | None = None
    grant_types: list[str] | None = None
    response_types: list[str] | None = None
    scope: str | None = None
    audience: list[str] | None = None
    token_endpoint_auth_method: str | None = None
    metadata: dict[str, Any] | None = None


class OAuth2Client(OAuth2ClientCreate):
    """Registration response, preserving additional server OAuth2 fields."""


class OAuth2ClientList(BaseList[OAuth2Client]):
    pass
