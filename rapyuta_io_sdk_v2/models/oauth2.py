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

"""Resource validation models for oauth2."""

from datetime import datetime

from pydantic import ConfigDict, Field, JsonValue

from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.utils import BaseList


class OAuth2UpdateURI(SDKModel):
    """Redirect and logout URI updates for an OAuth2 client."""

    redirect_uris: list[str] | None = Field(alias="redirectURIs")
    post_logout_redirect_uris: list[str] | None = Field(alias="postLogoutRedirectURIs")


class JsonWebKeySet(SDKModel):
    """JSON Web Key Set with provider-defined cryptographic key parameters."""

    keys: list[dict[str, JsonValue]]


class OAuth2Client(SDKModel):
    """Hydra OAuth2 client using its existing snake_case JSON schema.

    Matches ory/hydra-client-go's OAuth2Client used by the v2 server.
    Provider extensions are retained when loading and serializing clients.
    """

    model_config = ConfigDict(extra="allow")

    access_token_strategy: str | None = None
    allowed_cors_origins: list[str] | None = None
    audience: list[str] | None = None
    authorization_code_grant_access_token_lifespan: str | None = None
    authorization_code_grant_id_token_lifespan: str | None = None
    authorization_code_grant_refresh_token_lifespan: str | None = None
    backchannel_logout_session_required: bool | None = None
    backchannel_logout_uri: str | None = None
    client_credentials_grant_access_token_lifespan: str | None = None
    client_id: str | None = None
    client_name: str | None = None
    client_secret: str | None = None
    client_secret_expires_at: int | None = None
    client_uri: str | None = None
    contacts: list[str] | None = None
    created_at: datetime | None = None
    device_authorization_grant_access_token_lifespan: str | None = None
    device_authorization_grant_id_token_lifespan: str | None = None
    device_authorization_grant_refresh_token_lifespan: str | None = None
    frontchannel_logout_session_required: bool | None = None
    frontchannel_logout_uri: str | None = None
    grant_types: list[str] | None = None
    implicit_grant_access_token_lifespan: str | None = None
    implicit_grant_id_token_lifespan: str | None = None
    jwks: JsonWebKeySet | None = None
    jwks_uri: str | None = None
    jwt_bearer_grant_access_token_lifespan: str | None = None
    logo_uri: str | None = None
    metadata: JsonValue | None = None
    owner: str | None = None
    policy_uri: str | None = None
    post_logout_redirect_uris: list[str] | None = None
    redirect_uris: list[str] | None = None
    refresh_token_grant_access_token_lifespan: str | None = None
    refresh_token_grant_id_token_lifespan: str | None = None
    refresh_token_grant_refresh_token_lifespan: str | None = None
    registration_access_token: str | None = None
    registration_client_uri: str | None = None
    request_object_signing_alg: str | None = None
    request_uris: list[str] | None = None
    response_types: list[str] | None = None
    scope: str | None = None
    sector_identifier_uri: str | None = None
    skip_consent: bool | None = None
    skip_logout_consent: bool | None = None
    subject_type: str | None = None
    token_endpoint_auth_method: str | None = None
    token_endpoint_auth_signing_alg: str | None = None
    tos_uri: str | None = None
    updated_at: datetime | None = None
    userinfo_signed_response_alg: str | None = None


class OAuth2ClientList(BaseList[OAuth2Client]):
    """Paginated OAuth2 clients."""
