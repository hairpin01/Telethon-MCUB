import asyncio
from types import SimpleNamespace

import pytest

from telethon.events.callbackquery import CallbackQuery
from telethon.tl import types


class MockClient:
    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self.rich_calls = []
        self.requests = []

    async def __call__(self, request):
        self.requests.append(request)
        return request

    async def edit_rich_message(self, *args, **kwargs):
        self.rich_calls.append((args, kwargs))
        return True


@pytest.mark.asyncio
async def test_callback_query_edit_rich_uses_inline_msg_id():
    inline_id = types.InputBotInlineMessageID(1, 2, 3)
    event = CallbackQuery.Event(
        SimpleNamespace(query_id=123, user_id=456, msg_id=inline_id),
        types.PeerUser(456),
        0,
    )
    event._client = MockClient()

    await event.edit_rich("<h1>Title</h1>")

    args, kwargs = event._client.rich_calls[0]
    assert args[:2] == (inline_id, "<h1>Title</h1>")
    assert kwargs["fallback"] is False
