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


from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from rapyuta_io_sdk_v2.utils import walk_pages_async

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _make_sdk_model(items: list[Any], continue_: int | None = None) -> SimpleNamespace:
    """Simulate an SDK response with item and metadata attributes."""
    return SimpleNamespace(items=items, metadata=SimpleNamespace(continue_=continue_))


async def _collect(gen: AsyncIterator[list[Any]]) -> list[list[Any]]:
    return [page async for page in gen]


class TestWalkPagesAsyncWithDictResponse:
    """Verify pagination of dictionary responses."""

    @pytest.mark.asyncio
    async def test_single_page(self) -> None:
        """Yield the items from a single page."""

        async def list_func(**_pagination: int) -> dict[str, Any]:
            return {"items": ["a", "b"], "metadata": {"continue": None}}

        pages = await _collect(walk_pages_async(list_func))
        assert pages == [["a", "b"]]

    @pytest.mark.asyncio
    async def test_multiple_pages(self) -> None:
        """Follow continuation tokens across multiple pages."""
        responses = [
            {"items": ["a", "b"], "metadata": {"continue": 2}},
            {"items": ["c", "d"], "metadata": {"continue": 4}},
            {"items": ["e"], "metadata": {"continue": None}},
        ]
        calls = []

        async def list_func(*, cont: int, **_pagination: int) -> dict[str, Any]:
            calls.append(cont)
            return responses.pop(0)

        pages = await _collect(walk_pages_async(list_func, limit=2))
        assert pages == [["a", "b"], ["c", "d"], ["e"]]
        assert calls == [0, 2, 4]

    @pytest.mark.asyncio
    async def test_last_page_with_non_null_continue(self) -> None:
        """API may return a non-null continue value on the last page.

        walk_pages_async must stop when items count < limit to avoid infinite loops.
        """
        full_page_size = 50
        final_page_size = 5
        expected_page_count = 2
        responses = [
            {
                "items": list(range(full_page_size)),
                "metadata": {"continue": full_page_size},
            },
            {
                "items": list(range(final_page_size)),
                "metadata": {"continue": final_page_size},
            },
        ]
        calls = []

        async def list_func(*, cont: int, **_pagination: int) -> dict[str, Any]:
            calls.append(cont)
            return responses.pop(0)

        pages = await _collect(walk_pages_async(list_func))
        assert len(pages) == expected_page_count
        assert len(pages[0]) == full_page_size
        assert len(pages[1]) == final_page_size
        assert calls == [0, full_page_size]

    @pytest.mark.asyncio
    async def test_empty_items_stops_iteration(self) -> None:
        """Stop when the server returns an empty page."""

        async def list_func(**_pagination: int) -> dict[str, Any]:
            return {"items": [], "metadata": {"continue": 5}}

        pages = await _collect(walk_pages_async(list_func))
        assert pages == []

    @pytest.mark.asyncio
    async def test_missing_items_key_stops_iteration(self) -> None:
        """Treat a response without items as an empty page."""

        async def list_func(**_pagination: int) -> dict[str, Any]:
            return {"metadata": {"continue": 5}}

        pages = await _collect(walk_pages_async(list_func))
        assert pages == []

    @pytest.mark.asyncio
    async def test_missing_metadata_stops_after_first_page(self) -> None:
        """Stop after a page without a continuation token."""

        async def list_func(**_pagination: int) -> dict[str, Any]:
            return {"items": ["x"]}

        pages = await _collect(walk_pages_async(list_func))
        assert pages == [["x"]]

    @pytest.mark.asyncio
    async def test_kwargs_forwarded(self) -> None:
        """Forward resource filters to the API function."""
        received = {}

        async def list_func(
            *,
            tree_name: str | None = None,
            label_selector: list[str] | None = None,
            **_pagination: int,
        ) -> dict[str, Any]:
            received["tree_name"] = tree_name
            received["label_selector"] = label_selector
            return {"items": ["r1"], "metadata": {}}

        await _collect(
            walk_pages_async(
                list_func, tree_name="my-tree", label_selector=["env=prod"]
            )
        )
        assert received["tree_name"] == "my-tree"
        assert received["label_selector"] == ["env=prod"]


class TestWalkPagesAsyncWithSdkModelResponse:
    """Verify pagination of SDK model responses."""

    @pytest.mark.asyncio
    async def test_single_page(self) -> None:
        """Yield the items from a single page."""

        async def list_func(**_pagination: int) -> SimpleNamespace:
            return _make_sdk_model(["a", "b"], continue_=None)

        pages = await _collect(walk_pages_async(list_func))
        assert pages == [["a", "b"]]

    @pytest.mark.asyncio
    async def test_multiple_pages(self) -> None:
        """Follow continuation tokens across multiple pages."""
        responses = [
            _make_sdk_model(["a", "b"], continue_=2),
            _make_sdk_model(["c"], continue_=None),
        ]

        async def list_func(**_pagination: int) -> SimpleNamespace:
            return responses.pop(0)

        pages = await _collect(walk_pages_async(list_func, limit=2))
        assert pages == [["a", "b"], ["c"]]

    @pytest.mark.asyncio
    async def test_last_page_with_non_null_continue(self) -> None:
        """SDK model response: stop when items count < limit even if continue is set."""
        full_page_size = 50
        final_page_size = 5
        expected_page_count = 2
        responses = [
            _make_sdk_model(list(range(full_page_size)), continue_=full_page_size),
            _make_sdk_model(list(range(final_page_size)), continue_=final_page_size),
        ]

        async def list_func(**_pagination: int) -> SimpleNamespace:
            return responses.pop(0)

        pages = await _collect(walk_pages_async(list_func))
        assert len(pages) == expected_page_count
        assert len(pages[0]) == full_page_size
        assert len(pages[1]) == final_page_size

    @pytest.mark.asyncio
    async def test_empty_items_stops_iteration(self) -> None:
        """Stop when the server returns an empty page."""

        async def list_func(**_pagination: int) -> SimpleNamespace:
            return _make_sdk_model([], continue_=5)

        pages = await _collect(walk_pages_async(list_func))
        assert pages == []
