import inspect
from unittest import mock
from unittest.mock import MagicMock

import pytest

from telethon import TelegramClient, errors
from telethon.client import MessageMethods
from telethon.tl import functions, types
from telethon.tl.tlobject import DUMMY_MESSAGE_KWARGS
from telethon.tl.types import PeerChat, PeerUser, MessageMediaDocument, Message, MessageEntityBold


@pytest.mark.asyncio
async def test_send_message_with_file_forwards_args():
    arguments = {}
    sentinel = object()

    for value, name in enumerate(inspect.signature(TelegramClient.send_message).parameters):
        if name in {'self', 'entity', 'file'}:
            continue  # positional

        if name in {'message'}:
            continue  # renamed

        if name in {'link_preview'}:
            continue  # make no sense in send_file

        arguments[name] = value

    class MockedClient(TelegramClient):
        # noinspection PyMissingConstructor
        def __init__(self):
            pass

        async def send_file(self, entity, file, **kwargs):
            assert entity == 'a'
            assert file == 'b'
            for k, v in arguments.items():
                assert k in kwargs
                assert kwargs[k] == v

            return sentinel

    client = MockedClient()
    assert (await client.send_message('a', file='b', **arguments)) == sentinel


class TestMessageMethods:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        'formatting_entities',
        ([MessageEntityBold(offset=0, length=0)], None)
    )
    async def test_send_msg_and_file(self, formatting_entities):
        async def async_func(result): # AsyncMock was added only in 3.8
            return result
        msg_methods = MessageMethods()
        expected_result = Message(
            id=0, peer_id=PeerChat(chat_id=0), message='', date=None,
        )
        entity = 'test_entity'
        message = Message(
            id=1, peer_id=PeerChat(chat_id=0), message='expected_caption', date=None,
            entities=[MessageEntityBold(offset=9, length=9)],
        )
        media_file = MessageMediaDocument()

        with mock.patch.object(
            target=MessageMethods, attribute='send_file',
            new=MagicMock(return_value=async_func(expected_result)), create=True,
        ) as mock_obj:
            result = await msg_methods.send_message(
                entity=entity, message=message, file=media_file,
                formatting_entities=formatting_entities,
            )
            mock_obj.assert_called_once_with(
                entity, media_file, caption=message.message,
                formatting_entities=formatting_entities or message.entities,
                reply_to=None, topic=None, silent=None, attributes=None, parse_mode=(),
                force_document=False, thumb=None, buttons=None,
                clear_draft=False, schedule=None, supports_streaming=False,
                comment_to=None, background=None, nosound_video=None,
                resume=False, resume_key=None, state_store=None,
                send_as=None, message_effect_id=None,
                invert_media=False,
            )
            assert result == expected_result


class _RestrictedForwardClient(MessageMethods):
    def __init__(self):
        self.sent_requests = []

    async def get_input_entity(self, entity):
        return entity

    async def get_peer_id(self, peer):
        return peer

    async def __call__(self, request):
        self.sent_requests.append(request)
        return object()

    def _get_response_message(self, *args, **kwargs):
        return []


@pytest.mark.asyncio
@pytest.mark.parametrize("restricted_id", [777000, 489000, 4245000])
async def test_forward_messages_blocks_restricted_from_peer(restricted_id):
    client = _RestrictedForwardClient()

    with pytest.raises(ValueError, match="Forwarding from this peer is forbidden"):
        await client.forward_messages("target", [1], from_peer=restricted_id)

    assert client.sent_requests == []


@pytest.mark.asyncio
async def test_forward_messages_blocks_restricted_sender_message():
    client = _RestrictedForwardClient()
    restricted_message = Message(
        id=1,
        peer_id=PeerUser(42),
        from_id=PeerUser(777000),
        date=None,
        message="secret",
    )

    with pytest.raises(ValueError, match="Forwarding messages from this user is forbidden"):
        await client.forward_messages("target", [restricted_message])

    assert client.sent_requests == []


def test_message_content_is_masked_for_restricted_sender():
    visible_reply_markup = object()
    restricted_message = Message(
        id=1,
        peer_id=PeerUser(42),
        from_id=PeerUser(777000),
        date=None,
        message="secret",
        reply_markup=visible_reply_markup,
    )

    assert restricted_message.message == DUMMY_MESSAGE_KWARGS["message"]
    assert restricted_message.reply_markup is None


def test_message_content_is_masked_for_restricted_peer_without_from_id():
    visible_reply_markup = object()
    restricted_message = Message(
        id=1,
        peer_id=PeerUser(777000),
        from_id=None,
        date=None,
        message="secret",
        reply_markup=visible_reply_markup,
    )

    assert restricted_message.message == DUMMY_MESSAGE_KWARGS["message"]
    assert restricted_message.reply_markup is None


class _RichMessageClient(MessageMethods):
    def __init__(self, *, fail=False):
        self.fail = fail
        self.requests = []
        self.fallback_call = None
        self.edit_fallback_call = None

    async def get_input_entity(self, entity):
        return entity

    async def __call__(self, request):
        self.requests.append(request)
        if self.fail:
            raise errors.BadRequestError(request, "RICH_MESSAGE_UNSUPPORTED", 400)
        return object()

    def build_reply_markup(self, buttons):
        return buttons

    def _get_response_message(self, request, result, entity):
        return request

    async def send_message(self, *args, **kwargs):
        self.fallback_call = args, kwargs
        return "send fallback"

    async def edit_message(self, *args, **kwargs):
        self.edit_fallback_call = args, kwargs
        return "edit fallback"


@pytest.mark.asyncio
async def test_send_rich_message_uses_input_rich_message_html():
    client = _RichMessageClient()

    request = await client.send_rich_message(
        "peer",
        "<b>hello</b>",
        message="plain",
        buttons="markup",
    )

    assert isinstance(request, functions.messages.SendMessageRequest)
    assert request.peer == "peer"
    assert request.message == "plain"
    assert request.reply_markup == "markup"
    assert isinstance(request.rich_message, types.InputRichMessageHTML)
    assert request.rich_message.html == "<b>hello</b>"


@pytest.mark.asyncio
async def test_send_rich_message_falls_back_when_peer_rejects_rich_message():
    client = _RichMessageClient(fail=True)

    result = await client.send_rich_message("peer", "<b>hello</b>")

    assert result == "send fallback"
    args, kwargs = client.fallback_call
    assert args == ("peer", "<b>hello</b>")
    assert kwargs["parse_mode"] == "html"
    assert kwargs["link_preview"] is False


@pytest.mark.asyncio
async def test_edit_rich_message_uses_edit_message_request():
    client = _RichMessageClient()

    request = await client.edit_rich_message(
        "peer",
        123,
        "<b>edited</b>",
        text="plain",
    )

    assert isinstance(request, functions.messages.EditMessageRequest)
    assert request.peer == "peer"
    assert request.id == 123
    assert request.message == "plain"
    assert isinstance(request.rich_message, types.InputRichMessageHTML)
    assert request.rich_message.html == "<b>edited</b>"


@pytest.mark.asyncio
async def test_edit_rich_message_falls_back_when_peer_rejects_rich_message():
    client = _RichMessageClient(fail=True)

    result = await client.edit_rich_message("peer", 123, "<b>edited</b>")

    assert result == "edit fallback"
    args, kwargs = client.edit_fallback_call
    assert args == ("peer", 123, "<b>edited</b>")
    assert kwargs["parse_mode"] == "html"
    assert kwargs["link_preview"] is False


@pytest.mark.asyncio
async def test_message_edit_rich_delegates_to_client_edit_rich_message():
    message = Message(
        id=123,
        peer_id=PeerChat(chat_id=1),
        date=None,
        message="old",
        invert_media=False,
    )
    client = _RichMessageClient()
    message._client = client

    async def get_input_chat():
        return "peer"

    message.get_input_chat = get_input_chat

    result = await message.edit_rich("<b>edited</b>", link_preview=False)

    assert isinstance(result, functions.messages.EditMessageRequest)
    assert result.peer == "peer"
    assert result.id == 123
    assert result.rich_message.html == "<b>edited</b>"


def test_message_text_uses_markdown_formatting():
    message = Message(
        id=1,
        peer_id=PeerChat(chat_id=0),
        date=None,
        message="Hello world",
        entities=[MessageEntityBold(offset=6, length=5)],
    )

    assert message.text == "Hello **world**"


def test_message_html_text_uses_html_formatting():
    message = Message(
        id=1,
        peer_id=PeerChat(chat_id=0),
        date=None,
        message="Hello world",
        entities=[MessageEntityBold(offset=6, length=5)],
    )

    assert message.html_text == "Hello <strong>world</strong>"


def test_message_text_setter_parses_markdown():
    message = Message(
        id=1,
        peer_id=PeerChat(chat_id=0),
        date=None,
        message="",
        entities=[],
    )

    message.text = "Hello **world**"
    assert message.message == "Hello world"
    assert message.text == "Hello **world**"
    assert message.html_text == "Hello <strong>world</strong>"


def test_message_html_text_setter_parses_html():
    message = Message(
        id=1,
        peer_id=PeerChat(chat_id=0),
        date=None,
        message="",
        entities=[],
    )

    message.html_text = "Hello <strong>world</strong>"
    assert message.message == "Hello world"
    assert message.html_text == "Hello <strong>world</strong>"
    assert message.text == "Hello **world**"


class TestPollMethods:
    def test_add_poll_answer_method_exists(self):
        """Test that add_poll_answer method exists (Bot API 9.6)"""
        from telethon.client.messages import MessageMethods
        assert hasattr(MessageMethods, 'add_poll_answer')

    def test_delete_poll_answer_method_exists(self):
        """Test that delete_poll_answer method exists (Bot API 9.6)"""
        from telethon.client.messages import MessageMethods
        assert hasattr(MessageMethods, 'delete_poll_answer')
