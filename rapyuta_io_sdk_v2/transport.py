"""Shared request codecs for synchronous and asynchronous API clients."""

from typing import Any

from pydantic import BaseModel


def require_model[ModelT: BaseModel](value: ModelT, expected_type: type[ModelT]) -> None:
    """Reject dictionaries and incorrect request types before network access."""
    if not isinstance(value, expected_type):
        raise TypeError(
            f"Expected a {expected_type.__name__} instance; "
            "use model_validate() to convert a dictionary explicitly."
        )


def serialize_model(
    value: BaseModel | None,
    *,
    exclude_none: bool = False,
    exclude_unset: bool = False,
) -> Any:
    """Encode a request with its API aliases and JSON-compatible values.

    Omission options are endpoint-specific; explicit nulls are retained by default.
    """
    if value is None:
        return None
    if not isinstance(value, BaseModel):
        raise TypeError("Request bodies must be Pydantic model instances.")
    return value.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=exclude_none,
        exclude_unset=exclude_unset,
    )


def authorization_header(token: str | None) -> str:
    """Produce one Bearer prefix for a raw or already-prefixed token."""
    token = (token or "").strip()
    if token[:7].lower() == "bearer ":
        token = token[7:].strip()
    return f"Bearer {token}"
