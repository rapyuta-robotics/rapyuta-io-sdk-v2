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

"""Authentication payloads and identity-provider response models."""

from pydantic import Field

from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.responses import APIResponse


class LoginRequest(SDKModel):
    """Credentials sent to the identity provider."""

    email: str
    password: str


class TokenRequest(SDKModel):
    """Token submitted for refresh."""

    token: str | None


class TokenData(SDKModel):
    """Authentication token returned by the identity provider."""

    token: str


class TokenResponse(APIResponse):
    """Identity-provider token response envelope."""

    data: TokenData


class AuthSubject(SDKModel):
    """User or service-account identity returned by the identity provider."""

    email: str | None = None
    guid: str
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    is_verified: bool | None = Field(default=None, alias="isVerified")
    country_code: str | None = Field(default=None, alias="countryCode")
    phone_number: str | None = Field(default=None, alias="phoneNumber")


class AuthSubjectResponse(APIResponse):
    """Identity-provider subject response envelope."""

    data: AuthSubject
