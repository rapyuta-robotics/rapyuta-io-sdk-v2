import pytest
from rapyuta_io_sdk_v2.utils import walk_pages_async


def _make_sdk_model(items, continue_=None):
    """Simulate an SDK model response (object with attributes)."""

    class Metadata:
        pass

    class Response:
        pass

    meta = Metadata()
    meta.continue_ = continue_

    resp = Response()
    resp.items = items
    resp.metadata = meta
    return resp


async def _collect(gen):
    pages = []
    async for page in gen:
        pages.append(page)
    return pages


class TestWalkPagesAsyncWithDictResponse:
    """Tests for walk_pages_async when the list function returns a plain dict
    (e.g. list_configtrees, list_revisions in the configtree SDK client).
    """

    @pytest.mark.asyncio
    async def test_single_page(self):
        async def list_func(cont, limit):
            return {"items": ["a", "b"], "metadata": {"continue": None}}

        pages = await _collect(walk_pages_async(list_func))
        assert pages == [["a", "b"]]

    @pytest.mark.asyncio
    async def test_multiple_pages(self):
        responses = [
            {"items": ["a", "b"], "metadata": {"continue": 2}},
            {"items": ["c", "d"], "metadata": {"continue": 4}},
            {"items": ["e"], "metadata": {"continue": None}},
        ]
        calls = []

        async def list_func(cont, limit):
            calls.append(cont)
            return responses.pop(0)

        pages = await _collect(walk_pages_async(list_func, limit=2))
        assert pages == [["a", "b"], ["c", "d"], ["e"]]
        assert calls == [0, 2, 4]

    @pytest.mark.asyncio
    async def test_last_page_with_non_null_continue(self):
        """API may return a non-null continue value on the last page.

        walk_pages_async must stop when items count < limit to avoid infinite loops.
        """
        responses = [
            {"items": list(range(50)), "metadata": {"continue": 50}},
            {"items": list(range(5)), "metadata": {"continue": 5}},
        ]
        calls = []

        async def list_func(cont, limit):
            calls.append(cont)
            return responses.pop(0)

        pages = await _collect(walk_pages_async(list_func))
        assert len(pages) == 2
        assert len(pages[0]) == 50
        assert len(pages[1]) == 5
        assert calls == [0, 50]

    @pytest.mark.asyncio
    async def test_empty_items_stops_iteration(self):
        async def list_func(cont, limit):
            return {"items": [], "metadata": {"continue": 5}}

        pages = await _collect(walk_pages_async(list_func))
        assert pages == []

    @pytest.mark.asyncio
    async def test_missing_items_key_stops_iteration(self):
        async def list_func(cont, limit):
            return {"metadata": {"continue": 5}}

        pages = await _collect(walk_pages_async(list_func))
        assert pages == []

    @pytest.mark.asyncio
    async def test_missing_metadata_stops_after_first_page(self):
        async def list_func(cont, limit):
            return {"items": ["x"]}

        pages = await _collect(walk_pages_async(list_func))
        assert pages == [["x"]]

    @pytest.mark.asyncio
    async def test_kwargs_forwarded(self):
        received = {}

        async def list_func(cont, limit, tree_name=None, label_selector=None):
            received["tree_name"] = tree_name
            received["label_selector"] = label_selector
            return {"items": ["r1"], "metadata": {}}

        await _collect(
            walk_pages_async(list_func, tree_name="my-tree", label_selector=["env=prod"])
        )
        assert received["tree_name"] == "my-tree"
        assert received["label_selector"] == ["env=prod"]


class TestWalkPagesAsyncWithSdkModelResponse:
    """Tests for walk_pages_async when the list function returns an SDK model object
    (existing behaviour, should remain unaffected by the dict branch).
    """

    @pytest.mark.asyncio
    async def test_single_page(self):
        async def list_func(cont, limit):
            return _make_sdk_model(["a", "b"], continue_=None)

        pages = await _collect(walk_pages_async(list_func))
        assert pages == [["a", "b"]]

    @pytest.mark.asyncio
    async def test_multiple_pages(self):
        responses = [
            _make_sdk_model(["a", "b"], continue_=2),
            _make_sdk_model(["c"], continue_=None),
        ]

        async def list_func(cont, limit):
            return responses.pop(0)

        pages = await _collect(walk_pages_async(list_func, limit=2))
        assert pages == [["a", "b"], ["c"]]

    @pytest.mark.asyncio
    async def test_last_page_with_non_null_continue(self):
        """SDK model response: stop when items count < limit even if continue is set."""
        responses = [
            _make_sdk_model(list(range(50)), continue_=50),
            _make_sdk_model(list(range(5)), continue_=5),
        ]

        async def list_func(cont, limit):
            return responses.pop(0)

        pages = await _collect(walk_pages_async(list_func))
        assert len(pages) == 2
        assert len(pages[0]) == 50
        assert len(pages[1]) == 5

    @pytest.mark.asyncio
    async def test_empty_items_stops_iteration(self):
        async def list_func(cont, limit):
            return _make_sdk_model([], continue_=5)

        pages = await _collect(walk_pages_async(list_func))
        assert pages == []
