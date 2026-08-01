from types import SimpleNamespace

import pytest

from telethon.events.inlinequery import InlineQuery
from telethon.tl import types


class MockClient:
    def __init__(self):
        self.requests = []

    async def __call__(self, request):
        self.requests.append(request)
        return request

    def build_reply_markup(self, buttons):
        return None

    async def _parse_message_text(self, text, parse_mode):
        return text, []


def make_event(offset=""):
    event = InlineQuery.Event(
        SimpleNamespace(query_id=123, user_id=456, query="query", offset=offset, geo=None)
    )
    event._client = MockClient()
    return event


def test_inline_query_paginate_uses_event_offset():
    event = make_event(offset="2")

    page, next_offset = event.paginate([1, 2, 3, 4, 5], limit=2)

    assert page == [3, 4]
    assert next_offset == "4"


def test_inline_query_paginate_clamps_invalid_offset():
    event = make_event(offset="bad")

    page, next_offset = event.paginate([1, 2, 3], limit=50)

    assert page == [1, 2, 3]
    assert next_offset == ""


@pytest.mark.asyncio
async def test_inline_query_answer_article_builds_single_article():
    event = make_event()

    await event.answer_article("Title", "Body", description="Desc")

    request = event._client.requests[0]
    assert request.query_id == 123
    assert len(request.results) == 1
    assert request.results[0].title == "Title"
    assert request.results[0].description == "Desc"
    assert request.results[0].send_message.message == "Body"


@pytest.mark.asyncio
async def test_inline_query_answer_article_supports_rich_text():
    event = make_event()

    await event.answer_article("Rich", rich_text="<h1>Title</h1>")

    request = event._client.requests[0]
    send_message = request.results[0].send_message
    assert isinstance(send_message, types.InputBotInlineMessageRichMessage)
    assert isinstance(send_message.rich_message, types.InputRichMessageHTML)
    assert send_message.rich_message.html == "<h1>Title</h1>"


@pytest.mark.asyncio
async def test_inline_query_answer_text_alias():
    event = make_event()

    await event.answer_text("Title", "Body")

    request = event._client.requests[0]
    assert request.results[0].title == "Title"
    assert request.results[0].send_message.message == "Body"


@pytest.mark.asyncio
async def test_inline_query_answer_rich_alias():
    event = make_event()

    await event.answer_rich("Rich", "<h1>Title</h1>")

    send_message = event._client.requests[0].results[0].send_message
    assert isinstance(send_message, types.InputBotInlineMessageRichMessage)
    assert send_message.rich_message.html == "<h1>Title</h1>"


@pytest.mark.asyncio
async def test_inline_query_answer_page_sets_next_offset():
    event = make_event()
    results = [await event.builder.article(str(i), text=str(i)) for i in range(3)]

    await event.answer_page(results, limit=2)

    request = event._client.requests[0]
    assert len(request.results) == 2
    assert request.next_offset == "2"
