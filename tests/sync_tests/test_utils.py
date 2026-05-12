from rapyuta_io_sdk_v2 import walk_pages


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


class TestWalkPagesWithDictResponse:
    """Tests for walk_pages when the list function returns a plain dict
    (e.g. list_configtrees, list_revisions in the configtree SDK client).
    """

    def test_single_page(self):
        calls = []

        def list_func(cont, limit):
            calls.append((cont, limit))
            return {"items": ["a", "b"], "metadata": {"continue": None}}

        pages = list(walk_pages(list_func))
        assert pages == [["a", "b"]]
        assert len(calls) == 1

    def test_multiple_pages(self):
        responses = [
            {"items": ["a", "b"], "metadata": {"continue": 2}},
            {"items": ["c", "d"], "metadata": {"continue": 4}},
            {"items": ["e"], "metadata": {"continue": None}},
        ]
        calls = []

        def list_func(cont, limit):
            calls.append(cont)
            return responses.pop(0)

        pages = list(walk_pages(list_func, limit=2))
        assert pages == [["a", "b"], ["c", "d"], ["e"]]
        assert calls == [0, 2, 4]

    def test_last_page_with_non_null_continue(self):
        """API may return a non-null continue value on the last page.

        walk_pages must stop when items count < limit to avoid infinite loops.
        """
        responses = [
            {"items": list(range(50)), "metadata": {"continue": 50}},
            {"items": list(range(5)), "metadata": {"continue": 5}},
        ]
        calls = []

        def list_func(cont, limit):
            calls.append(cont)
            return responses.pop(0)

        pages = list(walk_pages(list_func))
        assert len(pages) == 2
        assert len(pages[0]) == 50
        assert len(pages[1]) == 5
        assert calls == [0, 50]

    def test_empty_items_stops_iteration(self):
        def list_func(cont, limit):
            return {"items": [], "metadata": {"continue": 5}}

        pages = list(walk_pages(list_func))
        assert pages == []

    def test_missing_items_key_stops_iteration(self):
        def list_func(cont, limit):
            return {"metadata": {"continue": 5}}

        pages = list(walk_pages(list_func))
        assert pages == []

    def test_missing_metadata_stops_after_first_page(self):
        def list_func(cont, limit):
            return {"items": ["x"]}

        pages = list(walk_pages(list_func))
        assert pages == [["x"]]

    def test_kwargs_forwarded(self):
        received = {}

        def list_func(cont, limit, tree_name=None, label_selector=None):
            received["tree_name"] = tree_name
            received["label_selector"] = label_selector
            return {"items": ["r1"], "metadata": {}}

        list(walk_pages(list_func, tree_name="my-tree", label_selector=["env=prod"]))
        assert received["tree_name"] == "my-tree"
        assert received["label_selector"] == ["env=prod"]


class TestWalkPagesWithSdkModelResponse:
    """Tests for walk_pages when the list function returns an SDK model object
    (existing behaviour, should remain unaffected by the dict branch).
    """

    def test_single_page(self):
        def list_func(cont, limit):
            return _make_sdk_model(["a", "b"], continue_=None)

        pages = list(walk_pages(list_func))
        assert pages == [["a", "b"]]

    def test_multiple_pages(self):
        responses = [
            _make_sdk_model(["a", "b"], continue_=2),
            _make_sdk_model(["c"], continue_=None),
        ]

        def list_func(cont, limit):
            return responses.pop(0)

        pages = list(walk_pages(list_func, limit=2))
        assert pages == [["a", "b"], ["c"]]

    def test_last_page_with_non_null_continue(self):
        """SDK model response: stop when items count < limit even if continue is set."""
        responses = [
            _make_sdk_model(list(range(50)), continue_=50),
            _make_sdk_model(list(range(5)), continue_=5),
        ]

        def list_func(cont, limit):
            return responses.pop(0)

        pages = list(walk_pages(list_func))
        assert len(pages) == 2
        assert len(pages[0]) == 50
        assert len(pages[1]) == 5

    def test_empty_items_stops_iteration(self):
        def list_func(cont, limit):
            return _make_sdk_model([], continue_=5)

        pages = list(walk_pages(list_func))
        assert pages == []
