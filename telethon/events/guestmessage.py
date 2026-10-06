import inspect
import re

from .common import EventBuilder, EventCommon, name_inner_event, _into_id_set
from ..tl import types, functions, custom
from ..extensions import richparser


# Telegram requires a non-empty title for the result of a guest chat query
# (`ArticleTitleEmptyError`), even though guest bots only post the message
# body, so we derive a title from the message text when none is given.
_DEFAULT_TITLE = "Guest message"
_TITLE_MAX_LENGTH = 64
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _default_title(*candidates) -> str:
    for candidate in candidates:
        if not candidate:
            continue

        if isinstance(candidate, str):
            title = candidate
        else:
            # Already-built rich message.
            title = richparser.rich_message_to_text(candidate) or ""

        title = " ".join(_HTML_TAG_RE.sub(" ", title).split())
        if title:
            return title[:_TITLE_MAX_LENGTH]

    return _DEFAULT_TITLE


@name_inner_event
class GuestMessage(EventBuilder):
    """
    Occurs whenever a guest bot is invoked in a chat
    (:tl:`UpdateBotGuestChatQuery`), or whenever a message posted by a guest
    bot arrives (a message with ``guestchat_via_from`` set).

    Guest bots are bots that can be queried by ``@username`` from any
    non-secret chat, group or supergroup, even if they are not members of it.
    See https://core.telegram.org/api/bots/guest-mode for the details.

    The event can be built from two different updates, and both of them
    expose the same "triggering" message:

    - :tl:`UpdateBotGuestChatQuery` (what a bot account receives). The bot
      answers it with `messages.setBotGuestChatResult
      <telethon.tl.functions.messages.SetBotGuestChatResultRequest>`, which is
      what `Event.reply` and `Event.rich_reply` do for you. The query id,
      the ``qts`` and the ``reference_messages`` sent by Telegram are
      available in the event as well.

    - A new message posted by a guest bot (``message.guestchat_via_from`` is
      set). This is what userbots receive, and `Event.reply` /
      `Event.rich_reply` simply send a normal (rich) message to the chat.

    Args:
        chats (`entity`, optional):
            May be one or more entities (username/peer/etc.), preferably IDs.
            By default, only matching chats will be handled.

        blacklist_chats (`bool`, optional):
            Whether to treat the chats as a blacklist instead of
            as a whitelist (default).

        from_users (`entity`, optional):
            Filters by the *sender* of the message that triggered the guest
            bot (or of the message posted by it).

        pattern (`str`, `callable`, `Pattern`, optional):
            If set, only messages matching this pattern will be handled.
            You can specify a regex-like string which will be matched
            against the message text, a callable function that returns `True`
            if a message is acceptable, or a compiled regex pattern.

    Example
        .. code-block:: python

            from telethon import events

            @bot.on(events.GuestMessage)
            async def handler(event):
                # Answer the guest query, the bot posts this into the chat
                await event.reply(f'Hello, {event.text}!')

                # A rich message can be sent with rich_reply
                await event.rich_reply('<h1>Hello!</h1><p>Rich body</p>')

            @client.on(events.GuestMessage(pattern='(?i)guest'))
            async def userbot_handler(event):
                # Guest bot messages are regular messages, reply to them
                print(event.guestchat_via_from, event.text)
                await event.reply('Got it')
    """

    def __init__(
        self,
        chats=None,
        *,
        blacklist_chats=False,
        func=None,
        from_users=None,
        pattern=None,
    ):
        super().__init__(chats, blacklist_chats=blacklist_chats, func=func)
        self.from_users = from_users
        if isinstance(pattern, str):
            self.pattern = re.compile(pattern).match
        elif not pattern or callable(pattern):
            self.pattern = pattern
        elif hasattr(pattern, "match") and callable(pattern.match):
            self.pattern = pattern.match
        else:
            raise TypeError("Invalid pattern type given")

        # Should we short-circuit? E.g. perform no check at all
        self._no_check = all(
            x is None
            for x in (
                self.chats,
                self.from_users,
                self.pattern,
                self.func,
            )
        )

    async def _resolve(self, client):
        await super()._resolve(client)
        self.from_users = await _into_id_set(client, self.from_users)

    @classmethod
    def build(cls, update, others=None, self_id=None):
        if isinstance(update, types.UpdateBotGuestChatQuery):
            if not isinstance(update.message, types.Message):
                return  # Nothing to reply to
            return cls.Event(update.message, query=update)

        if isinstance(update, (types.UpdateNewMessage, types.UpdateNewChannelMessage)):
            if not isinstance(update.message, types.Message):
                return
            if not update.message.guestchat_via_from:
                return  # Not posted by a guest bot
            return cls.Event(update.message)

    def filter(self, event):
        if self._no_check:
            return event

        if self.from_users is not None:
            if event.message.sender_id not in self.from_users:
                return

        if self.pattern:
            match = self.pattern(event.message.raw_text or "")
            if not match:
                return
            event.pattern_match = match

        return super().filter(event)

    class Event(EventCommon):
        """
        Represents a guest bot query or a message posted by a guest bot.

        This event can be treated to all effects as a `Message
        <telethon.tl.custom.message.Message>`: any attribute the underlying
        message has (``text``, ``sender_id``, ``media``, …) is accessible
        directly on the event.

        Members:
            message (`Message <telethon.tl.custom.message.Message>`):
                The message that triggered the guest bot, or the message
                posted by the guest bot.

            query (:tl:`UpdateBotGuestChatQuery`, optional):
                The original update, when the event was built from a guest
                bot query. `None` for messages posted by a guest bot.

            reference_messages (`list`, optional):
                Extra context messages referenced by the triggering message
                (for example, replied-to messages), only sent with guest bot
                queries.

            pattern_match (`obj`):
                The resulting object from calling the passed ``pattern``
                function, when the event builder was given a ``pattern``.

            guestchat_via_from (:tl:`Peer`, optional):
                The peer that invoked the guest bot, as set by Telegram on
                the messages posted by guest bots. `None` for the message
                that triggered the query.
        """

        def __init__(self, message, query=None):
            self.__dict__["_init"] = False
            super().__init__(
                chat_peer=message.peer_id, msg_id=message.id, broadcast=bool(message.post)
            )

            self.message = message
            self.query = query
            self.reference_messages = list(query.reference_messages or ()) if query else []
            self.pattern_match = None
            self._answered = False

        def _set_client(self, client):
            super()._set_client(client)
            self.message._finish_init(client, self._entities, None)
            for reference in self.reference_messages:
                if hasattr(reference, "_finish_init"):
                    reference._finish_init(client, self._entities, None)
            self.__dict__["_init"] = True  # No new attributes can be set

        def __getattr__(self, item):
            # `message` and `_init` must never be delegated, otherwise
            # accessing them would recurse into this very method.
            if item in ("message", "_init"):
                raise AttributeError(item)
            return getattr(self.message, item)

        def __setattr__(self, name, value):
            if not self.__dict__["_init"] or name in self.__dict__:
                self.__dict__[name] = value
            else:
                setattr(self.message, name, value)

        @property
        def is_query(self):
            """
            `True` if this event was built from a guest bot query
            (:tl:`UpdateBotGuestChatQuery`), that is, if the event should be
            answered with `messages.setBotGuestChatResult`.
            """
            return self.query is not None

        @property
        def query_id(self):
            """
            The unique identifier of the guest bot query, to be passed back
            when answering it. `None` if this is not a query.
            """
            return self.query.query_id if self.query else None

        @property
        def qts(self):
            """
            The ``qts`` of the guest bot query, if any.
            """
            return self.query.qts if self.query else None

        @property
        def text(self):
            """
            The text of the message, formatted as markdown.
            """
            return self.message.text

        @property
        def guestchat_via_from(self):
            """
            The peer that invoked the guest bot, if Telegram set it on the
            message (messages *posted* by guest bots).
            """
            return self.message.guestchat_via_from

        @property
        def builder(self):
            """
            Returns a new `InlineBuilder
            <telethon.tl.custom.inlinebuilder.InlineBuilder>` instance, which
            you can use to create the :tl:`InputBotInlineResult` to answer a
            guest bot query with.
            """
            return custom.InlineBuilder(self._client)

        async def answer(self, result=None, *, title=None, **kwargs):
            """
            Answers the guest bot query, which makes the bot post the given
            message into the chat where it was invoked.

            Args:
                result (:tl:`InputBotInlineResult`, optional):
                    An already-built result to post. You can create one with
                    `builder`, and it may be a coroutine.

                title (`str`, optional):
                    The title of the result, if ``result`` was not given.
                    Telegram rejects empty titles
                    (`ArticleTitleEmptyError`), so when it's not given it is
                    derived from the message text (trimmed to 64
                    characters), falling back to ``'Guest message'``.

                kwargs:
                    Any other argument is forwarded to `InlineBuilder.article
                    <telethon.tl.custom.inlinebuilder.InlineBuilder.article>`,
                    for example ``text``, ``parse_mode``, ``buttons``,
                    ``rich_text`` or ``rich_message``.

            Returns:
                The :tl:`InputBotInlineMessageID` of the posted message, or
                `None` if the query was already answered.

            Example
                .. code-block:: python

                    @bot.on(events.GuestMessage)
                    async def handler(event):
                        await event.answer(event.builder.photo('photo.jpg'))
            """
            if not self.is_query:
                raise RuntimeError(
                    'This GuestMessage is a message posted by a guest bot, not a '
                    'query. Use reply()/rich_reply() to send a message instead.'
                )

            if self._answered:
                return

            if result is None:
                if title is None:
                    title = _default_title(
                        kwargs.get("text"),
                        kwargs.get("rich_text"),
                        kwargs.get("rich_message"),
                    )
                result = self.builder.article(title, **kwargs)
            if inspect.isawaitable(result):
                result = await result

            self._answered = True
            return await self._client(
                functions.messages.SetBotGuestChatResultRequest(
                    query_id=self.query_id,
                    result=result,
                )
            )

        async def reply(self, text="", **kwargs):
            """
            Replies to the message.

            For guest bot queries, this makes the bot post ``text`` into the
            chat (the only thing a guest bot may do), by answering the query
            with `messages.setBotGuestChatResult
            <telethon.tl.functions.messages.SetBotGuestChatResultRequest>`.

            For messages posted by a guest bot, this is a normal reply to
            that message.

            Args:
                text (`str`):
                    The text of the message.

                kwargs:
                    `parse_mode`, `buttons`, `link_preview`, `title` for
                    guest bot queries, or any argument accepted by
                    `client.send_message
                    <telethon.client.messages.MessageMethods.send_message>`
                    for messages posted by a guest bot.

                The result title defaults to the text of the message, since
                Telegram does not accept empty titles for guest results.

            Example
                .. code-block:: python

                    @bot.on(events.GuestMessage)
                    async def handler(event):
                        await event.reply('Hello!', buttons=Button.url('https://example.com'))
            """
            if self.is_query:
                return await self.answer(text=text, **kwargs)

            return await self._reply_to_message(text, **kwargs)

        async def rich_reply(
            self,
            html=None,
            *,
            markdown=None,
            rich_message=None,
            title=None,
            buttons=None,
            rtl=None,
            noautolink=None,
            files=None,
            rich_media=None,
            **kwargs,
        ):
            """
            Replies to the message with a Telegram rich message.

            For guest bot queries, this answers the query with a result
            backed by :tl:`InputBotInlineMessageRichMessage`. For messages
            posted by a guest bot, this is a normal reply with
            `client.send_rich_message
            <telethon.client.messages.MessageMethods.send_rich_message>`.

            Args:
                html (`str`, optional):
                    The rich message source in HTML format.

                markdown (`str`, optional):
                    The rich message source in Markdown format. Cannot be
                    used together with ``html``.

                rich_message (:tl:`InputRichMessage`, optional):
                    An already-built rich message, if you need full control
                    over the rich blocks and their files.

                title (`str`, optional):
                    The title of the result, only used for guest bot queries.

                buttons:
                    The inline keyboard attached to the message.

                rtl (`bool`, optional):
                    Whether Telegram should render the rich message
                    right-to-left.

                noautolink (`bool`, optional):
                    Whether Telegram should avoid automatic link detection.

                files (:list`, optional):
                    :tl:`InputRichFile` items referenced by the rich message.

                rich_media (`dict` | `list`, optional):
                    Convenience mapping/list of media converted into
                    ``files``.

            Example
                .. code-block:: python

                    @bot.on(events.GuestMessage)
                    async def handler(event):
                        await event.rich_reply('<h1>Title</h1><p><b>Rich</b> body</p>')
            """
            if html is not None and markdown is not None:
                raise ValueError("Cannot set both html and markdown")

            if self.is_query:
                rich_text = html if html is not None else markdown
                parse_mode = "html" if html is not None else "markdown"

                return await self.answer(
                    title=title,
                    rich_text=rich_text,
                    rich_parse_mode=parse_mode,
                    rich_message=rich_message,
                    rich_rtl=rtl,
                    rich_noautolink=noautolink,
                    rich_files=files,
                    rich_media=rich_media,
                    buttons=buttons,
                    **kwargs,
                )

            return await self._rich_reply_to_message(
                html=html,
                markdown=markdown,
                rich_message=rich_message,
                rich_media=rich_media,
                buttons=buttons,
                rtl=rtl,
                noautolink=noautolink,
                files=files,
                **kwargs,
            )

        async def respond(self, text="", **kwargs):
            """
            Same as `reply`, but the message is not sent as a reply to the
            message that triggered the guest bot.

            Only makes sense for messages posted by a guest bot; for guest
            bot queries the result is always posted as a reply.
            """
            if self.is_query:
                return await self.reply(text, **kwargs)

            return await self._reply_to_message(text, reply=False, **kwargs)

        async def rich_respond(
            self, html=None, *, markdown=None, rich_message=None, **kwargs
        ):
            """
            Same as `rich_reply`, but the rich message is not sent as a reply
            to the message that triggered the guest bot.
            """
            if self.is_query:
                return await self.rich_reply(
                    html, markdown=markdown, rich_message=rich_message, **kwargs
                )

            return await self._rich_reply_to_message(
                html=html,
                markdown=markdown,
                rich_message=rich_message,
                reply=False,
                **kwargs,
            )

        async def _reply_to_message(self, text, reply=True, **kwargs):
            """Normal message to the chat of a message posted by a guest bot."""
            kwargs.pop("title", None)
            if reply:
                kwargs.setdefault("reply_to", self.message.id)
            return await self._client.send_message(
                await self.get_input_chat(), text, **kwargs
            )

        async def _rich_reply_to_message(
            self,
            html=None,
            markdown=None,
            rich_message=None,
            rich_media=None,
            files=None,
            reply=True,
            **kwargs,
        ):
            """Normal rich message to the chat of a message posted by a guest bot."""
            kwargs.pop("title", None)

            if rich_media is not None:
                # `send_rich_message` only takes rich files, so reuse the
                # inline builder to turn `rich_media` into them.
                rich_text, files = await custom.InlineBuilder(
                    self._client
                )._normalize_rich_media_for_message(
                    rich_media=rich_media,
                    rich_files=files,
                    rich_text=html if html is not None else markdown,
                )
                if html is not None:
                    html = rich_text
                else:
                    markdown = rich_text

            if reply:
                kwargs.setdefault("reply_to", self.message.id)

            return await self._client.send_rich_message(
                await self.get_input_chat(),
                html=html,
                markdown=markdown,
                rich_message=rich_message,
                files=files,
                **kwargs,
            )