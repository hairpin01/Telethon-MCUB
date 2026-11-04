import re
import typing

from .common import EventBuilder, EventCommon, name_inner_event, _into_id_set
from .. import utils
from ..tl import types, functions

if typing.TYPE_CHECKING:
    from ..client.telegramclient import TelegramClient


def _peer_to_id(peer) -> typing.Optional[int]:
    """Return the bare integer ID for a Peer object, or None."""
    if peer is None:
        return None
    return utils.get_peer_id(peer)


def _ephemeral_chat_peer(msg: types.EphemeralMessage):
    """
    Return the best ``chat_peer`` for an :tl:`EphemeralMessage`.

    In a group/channel the message carries ``peer_id``.
    In a DM we fall back to ``from_id`` (the sender) so EventCommon
    still has a valid peer to work with.
    """
    return msg.peer_id if msg.peer_id is not None else msg.from_id


@name_inner_event
class EphemeralMessage(EventBuilder):
    """
    Occurs whenever a new ephemeral message is received
    (:tl:`UpdateNewEphemeralMessage`).

    Ephemeral messages are messages visible only to a specific user inside
    a group or channel. The raw :tl:`EphemeralMessage` object is exposed
    via ``event.message``.

    Args:
        chats (`entity`, optional):
            One or more chats to listen in. By default all chats.

        blacklist_chats (`bool`, optional):
            Treat ``chats`` as a blacklist instead of a whitelist.

        from_users (`entity`, optional):
            Filter by the sender of the ephemeral message.

        receivers (`entity`, optional):
            Filter by the intended recipient. Only events whose
            ``receiver_id`` matches will pass.

        incoming (`bool`, optional):
            If ``True``, only messages *sent to us* pass.
            Mutually exclusive with ``outgoing``.

        outgoing (`bool`, optional):
            If ``True``, only messages *we sent* pass.
            Mutually exclusive with ``incoming``.

        pattern (`str`, `callable`, `Pattern`, optional):
            Regex / callable matched against the message text.

    Example
        .. code-block:: python

            from telethon import events

            @client.on(events.EphemeralMessage)
            async def handler(event):
                # Only we can see this — reply back ephemerally
                print('Got ephemeral from', event.sender_id,
                      'to receiver', event.receiver_id)
                await event.respond('Got it 👀')

            @client.on(events.EphemeralMessage(incoming=True, pattern='hello'))
            async def hello_handler(event):
                await event.respond('Hello back!')
    """

    def __init__(
        self,
        chats=None,
        *,
        blacklist_chats=False,
        func=None,
        from_users=None,
        receivers=None,
        incoming=None,
        outgoing=None,
        pattern=None,
    ):
        if incoming and outgoing:
            incoming = outgoing = None
        elif incoming is not None and outgoing is None:
            outgoing = not incoming
        elif outgoing is not None and incoming is None:
            incoming = not outgoing
        elif all(x is not None and not x for x in (incoming, outgoing)):
            raise ValueError(
                "Don't create an event handler if you don't want "
                "neither incoming nor outgoing!"
            )

        super().__init__(chats, blacklist_chats=blacklist_chats, func=func)
        self.from_users = from_users
        self.receivers = receivers
        self.incoming = incoming
        self.outgoing = outgoing

        if isinstance(pattern, str):
            self.pattern = re.compile(pattern).match
        elif not pattern or callable(pattern):
            self.pattern = pattern
        elif hasattr(pattern, "match") and callable(pattern.match):
            self.pattern = pattern.match
        else:
            raise TypeError("Invalid pattern type given")

        self._no_check = all(
            x is None
            for x in (
                self.chats,
                self.from_users,
                self.receivers,
                self.incoming,
                self.outgoing,
                self.pattern,
                self.func,
            )
        )

    async def _resolve(self, client):
        await super()._resolve(client)
        self.from_users = await _into_id_set(client, self.from_users)
        self.receivers = await _into_id_set(client, self.receivers)

    @classmethod
    def build(cls, update, others=None, self_id=None):
        if isinstance(update, types.UpdateNewEphemeralMessage):
            if not isinstance(update.message, types.EphemeralMessage):
                return
            return cls.Event(update.message, edited=False)
        return None

    def filter(self, event):
        if self._no_check:
            return event

        msg = event.message
        if self.incoming and msg.out:
            return
        if self.outgoing and not msg.out:
            return

        if self.from_users is not None:
            sid = _peer_to_id(msg.from_id)
            if sid not in self.from_users:
                return

        if self.receivers is not None:
            # receiver_id is a bare long (not a Peer)
            receiver_peer_id = utils.get_peer_id(
                types.PeerUser(msg.receiver_id)
            )
            if receiver_peer_id not in self.receivers:
                return

        if self.pattern:
            match = self.pattern(msg.message or "")
            if not match:
                return
            event.pattern_match = match

        return super().filter(event)

    class Event(EventCommon):
        """
        Represents the event of a new ephemeral message.

        Members:
            message (:tl:`EphemeralMessage`):
                The raw ephemeral message object.

            edited (`bool`):
                ``True`` when this event was fired for an edit
                (:tl:`UpdateEditEphemeralMessage`).

            pattern_match (`obj`):
                Result of the ``pattern`` callable, when set.

        The most useful properties are available directly on the event:

        - ``event.text`` / ``event.raw_text`` — message text
        - ``event.sender_id`` — bare user/chat ID of the sender
        - ``event.receiver_id`` — bare user ID of the recipient
        - ``event.chat_id`` — the group/channel (or sender for DMs)
        - ``event.is_out`` — whether *we* sent this message
        - ``event.is_welcome`` — welcome-template flag
        """

        def __init__(self, message: types.EphemeralMessage, *, edited: bool = False):
            self.__dict__["_init"] = False
            chat_peer = _ephemeral_chat_peer(message)
            super().__init__(
                chat_peer=chat_peer,
                msg_id=message.id,
                broadcast=False,
            )
            self.message = message
            self.edited = edited
            self.pattern_match = None

        def _set_client(self, client: "TelegramClient"):
            super()._set_client(client)
            self.__dict__["_init"] = True

        # ------------------------------------------------------------------ #
        # Convenience properties                                               #
        # ------------------------------------------------------------------ #

        @property
        def raw_text(self) -> str:
            """The plain text of the ephemeral message."""
            return self.message.message or ""

        @property
        def text(self) -> str:
            """Alias for `raw_text`."""
            return self.raw_text

        @property
        def sender_id(self) -> typing.Optional[int]:
            """Bare integer ID of the sender."""
            return _peer_to_id(self.message.from_id)

        @property
        def receiver_id(self) -> int:
            """Bare integer ID of the user this message was addressed to."""
            return self.message.receiver_id

        @property
        def is_out(self) -> bool:
            """``True`` if *we* sent this ephemeral message."""
            return bool(self.message.out)

        @property
        def is_welcome(self) -> bool:
            """``True`` if this message is a welcome-template message."""
            return bool(self.message.welcome_template)

        @property
        def id(self) -> int:
            """The message ID."""
            return self.message.id

        # ------------------------------------------------------------------ #
        # Actions                                                              #
        # ------------------------------------------------------------------ #

        async def respond(
            self,
            text: str,
            *,
            receiver=None,
            **kwargs,
        ) -> "types.Message":
            """
            Sends a new ephemeral message to the same chat.

            By default the reply is addressed to the same receiver as the
            incoming message.  Pass ``receiver=`` to override.

            Args:
                text (`str`): Message text.
                receiver (`entity`, optional): Override recipient.
                **kwargs: Forwarded to `~telethon.client.messages.MessageMethods.send_ephemeral_message`.

            Returns:
                The sent `~telethon.tl.custom.message.Message`.
            """
            target_receiver = receiver if receiver is not None else self.message.receiver_id
            chat = await self.get_input_chat()
            return await self._client.send_ephemeral_message(
                chat, target_receiver, text, **kwargs
            )

        async def delete(self) -> bool:
            """
            Deletes this ephemeral message.

            Returns:
                ``True`` on success.
            """
            chat = await self.get_input_chat()
            return await self._client.delete_ephemeral_message(
                chat,
                self.message.receiver_id,
                self.message.id,
            )

        async def edit(
            self,
            text: str,
            **kwargs,
        ):
            """
            Edits this ephemeral message.

            Args:
                text (`str`): New message text.
                **kwargs: Forwarded to `~telethon.client.messages.MessageMethods.edit_ephemeral_message`.

            Returns:
                The :tl:`Updates` result.
            """
            chat = await self.get_input_chat()
            return await self._client.edit_ephemeral_message(
                chat,
                self.message.receiver_id,
                self.message.id,
                text=text,
                **kwargs,
            )


@name_inner_event
class EphemeralMessageEdited(EphemeralMessage):
    """
    Occurs whenever an ephemeral message is edited
    (:tl:`UpdateEditEphemeralMessage`).

    Identical interface to `EphemeralMessage`; ``event.edited`` is always
    ``True``.

    Example
        .. code-block:: python

            from telethon import events

            @client.on(events.EphemeralMessageEdited)
            async def handler(event):
                print('Ephemeral message', event.id, 'was edited')
    """

    @classmethod
    def build(cls, update, others=None, self_id=None):
        if isinstance(update, types.UpdateEditEphemeralMessage):
            if not isinstance(update.message, types.EphemeralMessage):
                return
            return cls.Event(update.message, edited=True)
        return None
