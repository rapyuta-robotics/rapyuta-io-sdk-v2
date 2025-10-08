from pydantic import BaseModel, Field


class OAuth2UpdateURI(BaseModel):
    redirect_uris: list[str] | None = Field(alias="redirectURIs")
    post_logout_redirect_uris: list[str] | None = Field(alias="postLogoutRedirectURIs")
