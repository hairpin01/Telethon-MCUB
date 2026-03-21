import typing

from .. import helpers, hints
from ..requestiter import RequestIter
from ..tl import functions, types

_MAX_TOPICS_CHUNK_SIZE = 100

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


def get_topic_id(topic: typing.Union[int, types.TypeForumTopic]) -> int:
    if isinstance(topic, int):
        return topic

    topic_id = getattr(topic, "id", None)
    if topic_id is None:
        raise TypeError("topic must be a forum topic object or topic ID")
    return topic_id


def get_topic_top_message(topic: typing.Union[int, types.TypeForumTopic]) -> int:
    if isinstance(topic, int):
        return topic

    top_message = getattr(topic, "top_message", None)
    if top_message is None:
        raise TypeError("topic must be a forum topic object or topic top message ID")
    return top_message


def build_topic_reply_to(reply_to=None, topic=None):
    if topic is None:
        return None if reply_to is None else types.InputReplyToMessage(reply_to)

    top_msg_id = get_topic_top_message(topic)
    reply_to_msg_id = top_msg_id if reply_to is None else reply_to
    return types.InputReplyToMessage(reply_to_msg_id=reply_to_msg_id, top_msg_id=top_msg_id)


class _TopicsIter(RequestIter):
    async def _init(self, entity, search, offset_date, offset_id, offset_topic):
        if self.reverse:
            raise ValueError("Reverse topic iteration is not supported")

        self.entity = await self.client.get_input_entity(entity)
        self.request = functions.messages.GetForumTopicsRequest(
            peer=self.entity,
            q=search,
            offset_date=offset_date,
            offset_id=offset_id,
            offset_topic=offset_topic,
            limit=1,
        )

        if self.limit <= 0:
            result = await self.client(self.request)
            self.total = getattr(result, "count", len(result.topics))
            raise StopAsyncIteration

    async def _load_next_chunk(self):
        self.request.limit = min(self.left, _MAX_TOPICS_CHUNK_SIZE)
        result = await self.client(self.request)
        topics = result.topics
        self.total = getattr(result, "count", len(topics))

        if not topics:
            return True

        self.buffer.extend(topics)

        if len(topics) < self.request.limit:
            return True

        last_topic = topics[-1]
        self.request.offset_date = getattr(last_topic, "date", None)
        self.request.offset_id = getattr(last_topic, "top_message", 0)
        self.request.offset_topic = getattr(last_topic, "id", 0)
        return False


class TopicMethods:
    def iter_topics(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        limit: float = None,
        *,
        search: str = None,
        offset_date: "hints.DateLike" = None,
        offset_id: int = 0,
        offset_topic: int = 0,
    ) -> _TopicsIter:
        """
        Iterate forum topics for a channel/megagroup with forums enabled.
        """
        return _TopicsIter(
            self,
            limit,
            entity=entity,
            search=search,
            offset_date=offset_date,
            offset_id=offset_id,
            offset_topic=offset_topic,
        )

    async def get_topics(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        limit: float = None,
        *,
        search: str = None,
        offset_date: "hints.DateLike" = None,
        offset_id: int = 0,
        offset_topic: int = 0,
    ):
        return await self.iter_topics(
            entity,
            limit,
            search=search,
            offset_date=offset_date,
            offset_id=offset_id,
            offset_topic=offset_topic,
        ).collect()

    async def get_topic(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        topic: typing.Union[int, types.TypeForumTopic],
    ) -> typing.Optional[types.TypeForumTopic]:
        result = await self(
            functions.messages.GetForumTopicsByIDRequest(
                peer=entity,
                topics=[get_topic_id(topic)],
            )
        )
        return result.topics[0] if result.topics else None

    async def create_topic(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        title: str,
        *,
        icon_color: int = None,
        icon_emoji_id: int = None,
        send_as: "hints.EntityLike" = None,
    ):
        request = functions.messages.CreateForumTopicRequest(
            peer=entity,
            title=title,
            icon_color=icon_color,
            icon_emoji_id=icon_emoji_id,
            send_as=await self.get_input_entity(send_as) if send_as else None,
        )
        result = await self(request)
        return self._get_response_message(request, result, entity)

    async def edit_topic(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        topic: typing.Union[int, types.TypeForumTopic],
        *,
        title: str = None,
        icon_emoji_id: int = None,
        closed: bool = None,
        hidden: bool = None,
    ):
        request = functions.messages.EditForumTopicRequest(
            peer=entity,
            topic_id=get_topic_id(topic),
            title=title,
            icon_emoji_id=icon_emoji_id,
            closed=closed,
            hidden=hidden,
        )
        result = await self(request)
        return self._get_response_message(request, result, entity)

    async def close_topic(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        topic: typing.Union[int, types.TypeForumTopic],
    ):
        return await self.edit_topic(entity, topic, closed=True)

    async def reopen_topic(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        topic: typing.Union[int, types.TypeForumTopic],
    ):
        return await self.edit_topic(entity, topic, closed=False)

    async def delete_topic_history(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        topic: typing.Union[int, types.TypeForumTopic],
    ):
        return await self(
            functions.messages.DeleteTopicHistoryRequest(
                peer=entity,
                top_msg_id=get_topic_top_message(topic),
            )
        )

    async def pin_topic(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        topic: typing.Union[int, types.TypeForumTopic],
        *,
        pinned: bool = True,
    ):
        return await self(
            functions.messages.UpdatePinnedForumTopicRequest(
                peer=entity,
                topic_id=get_topic_id(topic),
                pinned=pinned,
            )
        )

    async def reorder_topics(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        order: typing.Sequence[typing.Union[int, types.TypeForumTopic]],
        *,
        force: bool = None,
    ):
        return await self(
            functions.messages.ReorderPinnedForumTopicsRequest(
                peer=entity,
                order=[get_topic_id(topic) for topic in order],
                force=force,
            )
        )

    def iter_topic_messages(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        topic: typing.Union[int, types.TypeForumTopic],
        *args,
        **kwargs,
    ):
        kwargs["topic"] = topic
        return self.iter_messages(entity, *args, **kwargs)

    async def send_to_topic(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        topic: typing.Union[int, types.TypeForumTopic],
        message: "hints.MessageLike" = "",
        **kwargs,
    ):
        kwargs["topic"] = topic
        return await self.send_message(entity, message, **kwargs)

    async def send_file_to_topic(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        topic: typing.Union[int, types.TypeForumTopic],
        file,
        **kwargs,
    ):
        kwargs["topic"] = topic
        return await self.send_file(entity, file, **kwargs)
