"""Collection, cursor safety, laziness, and sync/async pagination parity."""

import pytest

from rapyuta_io_sdk_v2 import AsyncPaginator, Paginator, PaginationError
from rapyuta_io_sdk_v2.models.utils import BaseList, ListMeta


def page(items, cursor=None):
    return BaseList[int](items=items, metadata=ListMeta(continue_=cursor))


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_string_cursor_from_wire_response(async_mode):
    calls = []

    def fetch(cont, limit):
        calls.append(cont)
        payload = (
            {"items": [1, 2], "metadata": {"continue": "cursor-abc"}}
            if cont == 0
            else {"items": [3], "metadata": {}}
        )
        response = BaseList[int].model_validate(payload)
        if cont == 0:
            assert response.model_dump(by_alias=True)["metadata"] == {
                "continue": "cursor-abc"
            }
        return response

    async def afetch(**kwargs):
        return fetch(**kwargs)

    paginator = (AsyncPaginator if async_mode else Paginator)(
        afetch if async_mode else fetch, limit=2
    )
    result = await paginator.all() if async_mode else paginator.all()
    assert result == [1, 2, 3]
    assert calls == [0, "cursor-abc"]


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_collection_preserves_arguments_and_starts_afresh(async_mode):
    calls = []

    def fetch(name, cont, limit, labels):
        calls.append((name, cont, limit, labels))
        return {0: page([1, 2], 2), 2: page([3], 3)}[cont]

    async def afetch(*args, **kwargs):
        return fetch(*args, **kwargs)

    paginator = (AsyncPaginator if async_mode else Paginator)(
        afetch if async_mode else fetch, "name", limit=2, labels=["env=test"]
    )
    assert not calls
    for _ in range(2):
        result = await paginator.all() if async_mode else paginator.all()
        assert result == [1, 2, 3]
    assert [call[1] for call in calls] == [0, 2, 0, 2]
    assert all(call[0] == "name" and call[2:] == (2, ["env=test"]) for call in calls)


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("terminal", [page([], 7), page([1], 7), page([1, 2])])
@pytest.mark.asyncio
async def test_terminal_pages(async_mode, terminal):
    calls = []

    def fetch(**kwargs):
        calls.append(kwargs)
        return terminal

    async def afetch(**kwargs):
        return fetch(**kwargs)

    paginator = (AsyncPaginator if async_mode else Paginator)(
        afetch if async_mode else fetch, limit=2
    )
    result = await paginator.all() if async_mode else paginator.all()
    assert result == terminal.items
    assert len(calls) == 1


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_repeated_cursor_raises(async_mode):
    def fetch(cont, limit):
        return page([1, 2], 2)

    async def afetch(**kwargs):
        return fetch(**kwargs)

    paginator = (AsyncPaginator if async_mode else Paginator)(
        afetch if async_mode else fetch, limit=2
    )
    with pytest.raises(PaginationError, match="repeated"):
        if async_mode:
            await paginator.all()
        else:
            paginator.all()


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_early_termination_does_not_prefetch(async_mode):
    calls = []

    def fetch(cont, limit):
        calls.append(cont)
        return page([1, 2], 2)

    async def afetch(**kwargs):
        return fetch(**kwargs)

    paginator = (AsyncPaginator if async_mode else Paginator)(
        afetch if async_mode else fetch, limit=2
    )
    items = paginator.items()
    if async_mode:
        assert await anext(items) == 1
        await items.aclose()
    else:
        assert next(items) == 1
        items.close()
    assert calls == [0]


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_page_sizes(limit):
    for paginator in (Paginator, AsyncPaginator):
        with pytest.raises(ValueError):
            paginator(lambda: None, limit=limit)


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_http_failure_propagates(async_mode):
    def fetch(cont, limit):
        raise RuntimeError("request failed")

    async def afetch(**kwargs):
        return fetch(**kwargs)

    paginator = (AsyncPaginator if async_mode else Paginator)(
        afetch if async_mode else fetch
    )
    with pytest.raises(RuntimeError, match="request failed"):
        if async_mode:
            await paginator.all()
        else:
            paginator.all()
