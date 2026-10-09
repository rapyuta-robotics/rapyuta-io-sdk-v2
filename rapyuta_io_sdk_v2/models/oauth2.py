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

from pydantic import BaseModel, Field


class OAuth2UpdateURI(BaseModel):
    """Redirect and logout URI updates for an OAuth2 client."""

    redirect_uris: list[str] | None = Field(alias="redirectURIs")
    post_logout_redirect_uris: list[str] | None = Field(alias="postLogoutRedirectURIs")
