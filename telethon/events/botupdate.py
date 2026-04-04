from .common import EventBuilder, EventCommon, name_inner_event
from ..tl import types


@name_inner_event
class BotUpdate(EventBuilder):
    """
    Occurs when a managed bot is created or its token changes.
    (Bot API 9.6 - Managed Bots)

    Example
        .. code-block:: python

            from telethon import events

            @client.on(events.BotUpdate)
            async def handler(event):
                print(f'User {event.user_id} created bot {event.bot_id}')
    """

    @classmethod
    def build(cls, update, others=None, self_id=None):
        if isinstance(update, types.UpdateManagedBot):
            return cls.Event(user_id=update.user_id, bot_id=update.bot_id, qts=update.qts)
        elif isinstance(update, types.UpdateBotStopped):
            return cls.Event(user_id=update.user_id, date=update.date, stopped=update.stopped, qts=update.qts)
        return None

    class Event(EventCommon):
        """
        Represents the event of a bot update.

        Members:
            user_id (`int`):
                The user ID who owns/manages the bot.

            bot_id (`int`):
                The bot ID that was created or updated.

            qts (`int`):
                The QTS (quick test suffix) for this update.
        """

        def __init__(self, user_id=None, bot_id=None, qts=None, date=None, stopped=None):
            super().__init__()
            self.user_id = user_id
            self.bot_id = bot_id
            self.qts = qts
            self.date = date
            self.stopped = stopped

        @property
        def is_creation(self):
            """
            `True` if this event is about a new bot being created.
            This is the case when ``UpdateManagedBot`` is received.
            """
            return self.date is None and self.stopped is None

        @property
        def is_stopped(self):
            """
            `True` if this event is about a bot being stopped.
            This is the case when ``UpdateBotStopped`` is received with ``stopped=True``.
            """
            return self.stopped is True

        def _get_bot_id(self):
            return self.bot_id
