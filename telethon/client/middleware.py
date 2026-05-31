import asyncio
from dataclasses import dataclass
import typing

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient

# Type for middleware function: async def mw(event, next) -> None
MiddlewareFunc = typing.Callable[[typing.Any, typing.Callable], typing.Awaitable[None]]
RequestNext = typing.Callable[[], typing.Awaitable[typing.Any]]
RequestMiddlewareFunc = typing.Callable[
    [typing.Any, "RequestContext", RequestNext], typing.Awaitable[typing.Any]
]


@dataclass
class RequestContext:
    sender: typing.Any
    ordered: bool
    flood_sleep_threshold: typing.Optional[float]
    started_at: float
    attempt: int
    is_batch: bool
    original_request: typing.Any
    request: typing.Any


class MiddlewareManager:
    def __init__(self):
        self._middlewares: list[MiddlewareFunc] = []

    def add(self, func: MiddlewareFunc) -> MiddlewareFunc:
        self._middlewares.append(func)
        return func

    def remove(self, func: MiddlewareFunc) -> None:
        self._middlewares.remove(func)

    async def process(self, event, handler: typing.Callable) -> None:
        """
        Run event through middleware chain, then call the handler.
        Each middleware receives (event, next) and must call await next()
        to pass control further.
        """

        async def build_chain(index: int):
            if index >= len(self._middlewares):
                # end of chain - call the actual handler
                return await handler(event)

            async def call_next():
                return await build_chain(index + 1)

            return await self._middlewares[index](event, call_next)

        return await build_chain(0)


class RequestMiddlewareManager:
    def __init__(self):
        self._middlewares: list[RequestMiddlewareFunc] = []

    def add(self, func: RequestMiddlewareFunc) -> RequestMiddlewareFunc:
        self._middlewares.append(func)
        return func

    def remove(self, func: RequestMiddlewareFunc) -> None:
        self._middlewares.remove(func)

    async def process(
        self,
        request,
        context: RequestContext,
        handler: typing.Callable[[typing.Any, RequestContext], typing.Awaitable[typing.Any]],
    ):
        context.request = request

        async def build_chain(index: int):
            current_request = context.request
            if index >= len(self._middlewares):
                return await handler(current_request, context)

            async def call_next():
                return await build_chain(index + 1)

            return await self._middlewares[index](current_request, context, call_next)

        return await build_chain(0)
