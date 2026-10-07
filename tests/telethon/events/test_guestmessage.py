import pytest

from telethon._updates.entitycache import EntityCache
from telethon.events.guestmessage import GuestMessage
from telethon.extensions import richparser
from telethon.tl import types


class MockClient:
    _self_id = 1
    _mb_entity_cache = EntityCache()

    def __init__(self):
        self.requests = []
        self.sent = []
        self.rich = []
        self.inline_id = None

    async def __call__(self, request):
        self.requests.append(request)
        return self.inline_id if self.inline_id is not None else request

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
async def test_reply_derives_title_from_text():
    event = make_event(make_query())

    await event.reply('Hi there')

    result = event._client.requests[0].result
    assert result.title == 'Hi there'
    assert result.send_message.message == 'Hi there'


@pytest.mark.asyncio
async def test_reply_with_buttons_and_title():
    event = make_event(make_query())

    await event.reply('Hi', title='Title')

    result = event._client.requests[0].result
    assert result.title == 'Title'
    assert result.send_message.message == 'Hi'


@pytest.mark.asyncio
async def test_reply_title_is_never_empty():
    event = make_event(make_query())

    await event.reply('')

    assert event._client.requests[0].result.title == 'Guest message'


@pytest.mark.asyncio
async def test_reply_trims_long_title():
    event = make_event(make_query())

    await event.reply('x' * 200)

    assert len(event._client.requests[0].result.title) == 64


@pytest.mark.asyncio
async def test_rich_reply_wraps_plain_text_into_a_paragraph():
    """Plain text used to produce no blocks and RICH_MESSAGE_EMPTY."""
    event = make_event(make_query())

    await event.rich_reply('hui')

    result = event._client.requests[0].result
    rich_message = result.send_message.rich_message
    assert rich_message.blocks
    assert richparser.rich_message_to_html(rich_message) == '<p>hui</p>'


@pytest.mark.asyncio
async def test_rich_reply_detects_markdown():
    event = make_event(make_query())

    await event.rich_reply('**bold** text')

    rich_message = event._client.requests[0].result.send_message.rich_message
    assert isinstance(rich_message, types.InputRichMessageMarkdown)
    assert rich_message.markdown == '**bold** text'


@pytest.mark.asyncio
async def test_rich_reply_detects_html():
    event = make_event(make_query())

    await event.rich_reply('<h1>Title</h1>')

    rich_message = event._client.requests[0].result.send_message.rich_message
    assert richparser.rich_message_to_html(rich_message) == '<h1>Title</h1>'


@pytest.mark.asyncio
async def test_rich_reply_parse_mode_forces_format():
    event = make_event(make_query())

    # Forced HTML, so the Markdown delimiters are plain text.
    await event.rich_reply('**bold**', parse_mode='html')
    rich_message = event._client.requests[0].result.send_message.rich_message
    assert richparser.rich_message_to_html(rich_message) == '<p>**bold**</p>'

    # Forced Markdown, so the HTML is sent as Markdown text.
    event = make_event(make_query())
    await event.rich_reply('<b>x</b>', parse_mode='markdown')
    rich_message = event._client.requests[0].result.send_message.rich_message
    assert isinstance(rich_message, types.InputRichMessageMarkdown)
    assert rich_message.markdown == '<b>x</b>'


@pytest.mark.asyncio
async def test_rich_reply_rejects_text_with_html():
    event = make_event(make_query())

    with pytest.raises(ValueError):
        await event.rich_reply('text', html='<b>html</b>')


@pytest.mark.asyncio
async def test_rich_reply_escapes_plain_text():
    event = make_event(make_query())

    await event.rich_reply('a < b & c')

    rich_message = event._client.requests[0].result.send_message.rich_message
    assert richparser.rich_message_to_html(rich_message) == '<p>a &lt; b &amp; c</p>'


@pytest.mark.asyncio
async def test_reply_rich_is_alias_for_rich_reply():
    event = make_event(make_query())

    await event.reply_rich('<p>body</p>')

    result = event._client.requests[0].result
    assert isinstance(result.send_message, types.InputBotInlineMessageRichMessage)


@pytest.mark.asyncio
async def test_reply_returns_posted_message():
    event = make_event(make_query())
    event._client.inline_id = types.InputBotInlineMessageID64(
        dc_id=2, owner_id=3, id=77, access_hash=9
    )

    message = await event.reply('Hi there')

    assert isinstance(message, types.Message)
    assert message.id == 77
    assert message.chat_id == event.chat_id
    assert message.text == 'Hi there'
    assert message.reply_to.reply_to_msg_id == 11
    # Kept so `edit`/`edit_rich` know they must use the inline id.
    assert isinstance(message._inline_msg_id, types.InputBotInlineMessageID64)


@pytest.mark.asyncio
async def test_posted_message_is_edited_through_inline_id():
    event = make_event(make_query())
    event._client.inline_id = types.InputBotInlineMessageID64(
        dc_id=2, owner_id=3, id=77, access_hash=9
    )
    event._client.edited = []

    message = await event.rich_reply('<p>body</p>')

    async def edit_rich_message(entity, message_id, *args, **kwargs):
        event._client.edited.append((entity, message_id, args, kwargs))
        return 'edited'

    event._client.edit_rich_message = edit_rich_message
    await message.edit_rich('<p>new body</p>')

    entity, message_id, _, _ = event._client.edited[0]
    assert entity is message._inline_msg_id
    assert message_id == 77


@pytest.mark.asyncio
async def test_posted_message_plain_edit_uses_edit_message():
    event = make_event(make_query())
    event._client.inline_id = types.InputBotInlineMessageID64(
        dc_id=2, owner_id=3, id=77, access_hash=9
    )
    event._client.edits = []

    message = await event.reply('body')

    async def edit_message(entity, message=None, **kwargs):
        event._client.edits.append((entity, message, kwargs))
        return 'edited'

    event._client.edit_message = edit_message
    await message.edit('new body')

    entity, text, _ = event._client.edits[0]
    assert entity is message._inline_msg_id
    assert text == 'new body'


@pytest.mark.asyncio
async def test_rich_reply_uses_rich_inline_message():
    event = make_event(make_query())

    await event.rich_reply('<h1>Title</h1><p><b>body</b></p>')

    result = event._client.requests[0].result
    assert isinstance(result.send_message, types.InputBotInlineMessageRichMessage)
    rich_message = result.send_message.rich_message
    assert isinstance(rich_message, types.InputRichMessage)
    assert richparser.rich_message_to_html(rich_message) == '<h1>Title</h1><p><b>body</b></p>'
    # Telegram rejects empty article titles, so it is derived from the text.
    assert result.title == 'Title body'


@pytest.mark.asyncio
async def test_rich_reply_derives_title_from_markdown():
    event = make_event(make_query())

    await event.rich_reply(markdown='**bold** title')

    assert event._client.requests[0].result.title == '**bold** title'


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