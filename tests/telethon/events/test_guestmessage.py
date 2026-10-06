import pytest

from telethon.events.guestmessage import GuestMessage
from telethon.extensions import richparser
from telethon.tl import types


class MockClient:
    def __init__(self):
        self.requests = []
        self.sent = []
        self.rich = []

    async def __call__(self, request):
        self.requests.append(request)
        return request

    def build_reply_markup(self, buttons):
        return None

    async def _parse_message_text(self, text, parse_mode):
        return text, []

    async def send_message(self, entity, text, **kwargs):
        self.sent.append((entity, text, kwargs))
        return "sent"

    async def send_rich_message(self, entity, **kwargs):
        self.rich.append((entity, kwargs))
        return "rich"


def make_message(**kwargs):
    kwargs.setdefault("id", 11)
    kwargs.setdefault("peer_id", types.PeerChat(5))
    kwargs.setdefault("from_id", types.PeerUser(3))
    kwargs.setdefault("message", "hello guest")
    kwargs.setdefault("date", 1000)
    return types.Message(**kwargs)


def make_query(message=None, reference_messages=None, query_id=42, qts=3):
    return types.UpdateBotGuestChatQuery(
        query_id=query_id,
        message=message if message is not None else make_message(),
        reference_messages=reference_messages,
        qts=qts,
    )


def make_new_message(message=None):
    return types.UpdateNewMessage(
        message if message is not None else make_message(),
        pts=1,
        pts_count=1,
    )


def make_guest_posted_update(**kwargs):
    return make_new_message(make_message(guestchat_via_from=types.PeerUser(9), **kwargs))


def make_event(update):
    event = GuestMessage.build(update)
    event._client = MockClient()
    event._input_chat = types.InputPeerChat(5)
    return event


def test_build_from_guest_chat_query():
    reference = make_message(id=10, message="context")
    event = make_event(make_query(reference_messages=[reference]))

    assert event.is_query
    assert event.query_id == 42
    assert event.qts == 3
    assert event.message.id == 11
    assert event.reference_messages == [reference]
    assert event.guestchat_via_from is None
    assert event.text == "hello guest"


def test_build_ignores_regular_new_messages():
    assert GuestMessage.build(make_new_message()) is None
    assert GuestMessage.build(types.UpdateNewChannelMessage(
        make_message(), pts=1, pts_count=1
    )) is None
    assert GuestMessage.build(types.UpdateNewChannelMessage(
        make_message(guestchat_via_from=types.PeerUser(9)), pts=1, pts_count=1
    )) is not None


def test_build_from_message_posted_by_guest_bot():
    event = make_event(make_guest_posted_update())

    assert not event.is_query
    assert event.query_id is None
    assert event.qts is None
    assert event.guestchat_via_from == types.PeerUser(9)


@pytest.mark.asyncio
async def test_reply_posts_message_through_guest_query():
    event = make_event(make_query())

    await event.reply('Hi there')

    request = event._client.requests[0]
    assert request.__class__.__name__ == "SetBotGuestChatResultRequest"
    assert request.query_id == 42
    assert request.result.send_message.message == "Hi there"


@pytest.mark.asyncio
async def test_reply_with_buttons_and_title():
    event = make_event(make_query())

    await event.reply('Hi', title='Title')

    result = event._client.requests[0].result
    assert result.title == 'Title'
    assert result.send_message.message == 'Hi'


@pytest.mark.asyncio
async def test_rich_reply_uses_rich_inline_message():
    event = make_event(make_query())

    await event.rich_reply('<h1>Title</h1><p><b>body</b></p>')

    result = event._client.requests[0].result
    assert isinstance(result.send_message, types.InputBotInlineMessageRichMessage)
    rich_message = result.send_message.rich_message
    assert isinstance(rich_message, types.InputRichMessage)
    assert richparser.rich_message_to_html(rich_message) == '<h1>Title</h1><p><b>body</b></p>'


@pytest.mark.asyncio
async def test_rich_reply_rejects_html_and_markdown():
    event = make_event(make_query())

    with pytest.raises(ValueError):
        await event.rich_reply('<b>a</b>', markdown='**a**')


@pytest.mark.asyncio
async def test_query_can_only_be_answered_once():
    event = make_event(make_query())

    await event.reply('first')
    assert await event.reply('second') is None
    assert len(event._client.requests) == 1


@pytest.mark.asyncio
async def test_answer_accepts_prebuilt_result():
    event = make_event(make_query())
    result = await event.builder.article('Photo', text='caption')

    await event.answer(result)

    assert event._client.requests[0].result is result


@pytest.mark.asyncio
async def test_answer_requires_a_guest_query():
    event = make_event(make_guest_posted_update())

    with pytest.raises(RuntimeError):
        await event.answer(text='nope')


@pytest.mark.asyncio
async def test_reply_to_guest_posted_message_sends_normal_reply():
    event = make_event(make_guest_posted_update())

    await event.reply('Got it')

    assert not event._client.requests
    entity, text, kwargs = event._client.sent[0]
    assert entity == types.InputPeerChat(5)
    assert text == 'Got it'
    assert kwargs['reply_to'] == 11


@pytest.mark.asyncio
async def test_rich_reply_to_guest_posted_message_sends_normal_rich_reply():
    event = make_event(make_guest_posted_update())

    await event.rich_reply('<p>body</p>')

    assert not event._client.requests
    _, kwargs = event._client.rich[0]
    assert kwargs['html'] == '<p>body</p>'
    assert kwargs['reply_to'] == 11


@pytest.mark.asyncio
async def test_rich_reply_converts_rich_media_into_files():
    event = make_event(make_guest_posted_update())
    photo = types.InputPhoto(id=1, access_hash=2, file_reference=b'')

    await event.rich_reply(
        '<p><a href="tg://photo?id=hero">Hero</a></p>',
        rich_media={'id': 'hero', 'photo': photo},
    )

    _, kwargs = event._client.rich[0]
    assert kwargs['html'] == '<p><a href="tg://photo?id=hero">Hero</a></p>'
    assert kwargs['files'] == [types.InputRichFilePhoto('hero', photo)]


@pytest.mark.asyncio
async def test_respond_to_guest_posted_message_does_not_reply():
    event = make_event(make_guest_posted_update())

    await event.respond('Just saying')

    _, _, kwargs = event._client.sent[0]
    assert 'reply_to' not in kwargs


async def resolved_builder(client, **kwargs):
    builder = GuestMessage(**kwargs)
    await builder.resolve(client)
    return builder


@pytest.mark.asyncio
async def test_pattern_filter_matches_message_text():
    builder = await resolved_builder(MockClient(), pattern='hello')
    event = make_event(make_query())

    assert builder.filter(event)
    assert event.pattern_match.group(0) == 'hello'

    assert builder.filter(make_event(make_query(make_message(message='bye')))) is None


@pytest.mark.asyncio
async def test_from_users_filter():
    builder = await resolved_builder(MockClient(), from_users=3)

    assert builder.filter(make_event(make_query())) is not None
    assert builder.filter(make_event(make_query(make_message(from_id=types.PeerUser(4))))) is None


@pytest.mark.asyncio
async def test_chats_filter():
    builder = await resolved_builder(MockClient(), chats=5)

    assert builder.filter(make_event(make_query())) is not None
    assert (
        builder.filter(make_event(make_query(make_message(peer_id=types.PeerChat(6)))))
        is None
    )