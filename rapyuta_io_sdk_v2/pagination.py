"""Reusable collection and streaming for typed list API methods."""

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

from rapyuta_io_sdk_v2.models.utils import BaseList

type Cursor = int | str


class PaginationError(RuntimeError):
    """An API returned a continuation token that would repeat a page."""


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("pagination limit must be a positive integer")


def _next_cursor[T](page: BaseList[T], limit: int, seen: set[Cursor]) -> Cursor | None:
    cursor = page.metadata.continue_ if page.metadata else None
    # These offset APIs may emit a non-null token on a terminal short page.
    if not page.items or len(page.items) < limit or cursor is None:
        return None
    if cursor in seen:
        raise PaginationError(f"repeated continuation token: {cursor}")
    seen.add(cursor)
    return cursor


class Paginator[T]:
    """Each traversal starts afresh; construction performs no requests."""

    def __init__(
        self,
        method: Callable[..., BaseList[T]],
        *args,
        limit: int = 50,
        cont: Cursor = 0,
        **kwargs,
    ):
        _validate_limit(limit)
        self.method = method
        self.args = args
        self.limit = limit
        self.cont = cont
        self.kwargs = dict(kwargs)

    def pages(self) -> Iterator[BaseList[T]]:
        cursor = self.cont
        seen = {cursor}
        while True:
            page = self.method(*self.args, **self.kwargs, cont=cursor, limit=self.limit)
            if not isinstance(page, BaseList):
                raise TypeError("pagination methods must return a BaseList model")
            yield page
            cursor = _next_cursor(page, self.limit, seen)
            if cursor is None:
                return

    def items(self) -> Iterator[T]:
        for page in self.pages():
            yield from page.items

    def all(self) -> list[T]:
        return list(self.items())


class AsyncPaginator[T]:
    """Async counterpart with lazy requests and no background prefetching."""

    def __init__(
        self,
        method: Callable[..., Awaitable[BaseList[T]]],
        *args,
        limit: int = 50,
        cont: Cursor = 0,
        **kwargs,
    ):
        _validate_limit(limit)
        self.method = method
        self.args = args
        self.limit = limit
        self.cont = cont
        self.kwargs = dict(kwargs)

    async def pages(self) -> AsyncIterator[BaseList[T]]:
        cursor = self.cont
        seen = {cursor}
        while True:
            page = await self.method(
                *self.args, **self.kwargs, cont=cursor, limit=self.limit
            )
            if not isinstance(page, BaseList):
                raise TypeError("pagination methods must return a BaseList model")
            yield page
            cursor = _next_cursor(page, self.limit, seen)
            if cursor is None:
                return

    async def items(self) -> AsyncIterator[T]:
        async for page in self.pages():
            for item in page.items:
                yield item

    async def all(self) -> list[T]:
        return [item async for item in self.items()]
