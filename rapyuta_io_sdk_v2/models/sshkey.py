"""
Pydantic models for SSH certificate signing.

This module contains Pydantic models for SSH public key signing requests
and responses, used by the /v2/certs/ssh/sign/ endpoint.
"""

from pydantic import BaseModel, Field


class SSHKeySignRequest(BaseModel):
    """Request body for signing an SSH public key."""

    public_key: str = Field(
        alias="publicKey",
        description="SSH public key to be signed (e.g., ssh-rsa AAAA...)",
    )


class SSHKeySignResponse(BaseModel):
    """Response from the SSH public key signing endpoint."""

    certificate: str = Field(
        description="Signed SSH certificate",
    )
