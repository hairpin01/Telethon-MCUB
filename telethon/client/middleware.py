import asyncio
import typing

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient

# Type for middleware function: async def mw(event, next) -> None
MiddlewareFunc = typing.Callable[
    [typing.Any, typing.Callable],
    typing.Awaitable[None]
]


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
                # end of chain — call the actual handler
                return await handler(event)

            async def call_next():
                return await build_chain(index + 1)

            return await self._middlewares[index](event, call_next)

        return await build_chain(0)
