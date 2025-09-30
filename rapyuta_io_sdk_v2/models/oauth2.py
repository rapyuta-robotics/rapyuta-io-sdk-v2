from pydantic import BaseModel, Field


class OAuth2UpdateURI(BaseModel):
    redirect_uris: list[str] | None = Field(serialization_alias="redirectURIs")
    post_logout_redirect_uris: list[str] | None = Field(
        serialization_alias="postLogoutRedirectURIs"
    )
