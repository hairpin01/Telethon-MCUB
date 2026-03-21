import types as py_types

import pytest

from telethon.client import MessageMethods, TopicMethods, UploadMethods
from telethon.tl import functions, types


class _TopicRef:
    def __init__(self, *, id, top_message, date=None):
        self.id = id
        self.top_message = top_message
        self.date = date


class _TopicResult:
    def __init__(self, topics):
        self.topics = topics
        self.count = len(topics)
        self.messages = []
        self.chats = []
        self.users = []


class _TopicClient(TopicMethods):
    def __init__(self, result):
        self.requests = []
        self.result = result

    async def get_input_entity(self, entity):
        return types.InputPeerChannel(100, 200)

    async def __call__(self, request):
        self.requests.append(request)
        return self.result

    def _get_response_message(self, request, result, entity):
        return ("mapped", request, result, entity)


class _TopicMessageClient(MessageMethods):
    def __init__(self):
        self.last_request = None
        self._parse_mode = None

    async def get_input_entity(self, entity):
        return types.InputPeerChannel(100, 200)

    async def __call__(self, request):
        self.last_request = request
        return py_types.SimpleNamespace(count=0, messages=[], chats=[], users=[])

    async def _parse_message_text(self, message, parse_mode):
        return message, []

    def build_reply_markup(self, buttons):
        return None

    def _get_response_message(self, request, result, entity):
        return request


class _TopicUploadClient(UploadMethods):
    def __init__(self):
        self.album_calls = []

    async def get_input_entity(self, entity):
        return types.InputPeerChannel(100, 200)

    async def _send_album(self, entity, files, **kwargs):
        self.album_calls.append((entity, files, kwargs))
        return []


@pytest.mark.asyncio
async def test_get_topics_uses_forum_topics_request():
    topic = _TopicRef(id=10, top_message=100)
    client = _TopicClient(_TopicResult([topic]))

    topics = await client.get_topics("forum", limit=1)

    assert topics == [topic]
    assert isinstance(client.requests[0], functions.messages.GetForumTopicsRequest)
    assert client.requests[0].limit == 1


@pytest.mark.asyncio
async def test_get_topic_uses_get_forum_topics_by_id():
    topic = _TopicRef(id=10, top_message=100)
    client = _TopicClient(_TopicResult([topic]))

    result = await client.get_topic("forum", 10)

    assert result is topic
    assert isinstance(client.requests[0], functions.messages.GetForumTopicsByIDRequest)
    assert client.requests[0].topics == [10]


@pytest.mark.asyncio
async def test_iter_messages_with_topic_uses_replies_request():
    client = _TopicMessageClient()

    result = await client.iter_messages("forum", limit=0, topic=321).collect()

    assert result == []
    assert isinstance(client.last_request, functions.messages.GetRepliesRequest)
    assert client.last_request.msg_id == 321


@pytest.mark.asyncio
async def test_iter_messages_with_topic_uses_top_msg_id_on_search_request():
    client = _TopicMessageClient()

    result = await client.iter_messages("forum", limit=0, topic=321, search="hello").collect()

    assert result == []
    assert isinstance(client.last_request, functions.messages.SearchRequest)
    assert client.last_request.top_msg_id == 321


@pytest.mark.asyncio
async def test_send_message_to_topic_builds_reply_to_with_top_msg_id():
    client = _TopicMessageClient()

    request = await client.send_message("forum", "hello", topic=321)

    assert isinstance(request, functions.messages.SendMessageRequest)
    assert request.reply_to.reply_to_msg_id == 321
    assert request.reply_to.top_msg_id == 321


@pytest.mark.asyncio
async def test_send_message_reply_inside_topic_uses_topic_top_message():
    client = _TopicMessageClient()
    topic = _TopicRef(id=10, top_message=321)

    request = await client.send_message("forum", "hello", topic=topic, reply_to=55)

    assert isinstance(request, functions.messages.SendMessageRequest)
    assert request.reply_to.reply_to_msg_id == 55
    assert request.reply_to.top_msg_id == 321


@pytest.mark.asyncio
async def test_send_file_album_forwards_topic_to_album_sender():
    client = _TopicUploadClient()

    result = await client.send_file("forum", ["one.jpg"], topic=321)

    assert result == []
    assert len(client.album_calls) == 1
    _, files, kwargs = client.album_calls[0]
    assert files == ["one.jpg"]
    assert kwargs["topic"] == 321
