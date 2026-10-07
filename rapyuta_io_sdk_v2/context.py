"""Per-request scope and additional HTTP headers."""

from pydantic import BaseModel, ConfigDict, Field


class RequestContext(BaseModel):
    """Override the configured resource scope for a single request.

    Additional headers are applied last and may override generated headers.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_guid: str | None = None
    project_guid: str | None = None
    group_guid: str | None = None
    with_organization: bool | None = None
    with_project: bool | None = None
    with_group: bool | None = None
    request_id: str | None = None
    x_checksum: str | None = None
    content_type: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
