from .common import EventBuilder, EventCommon, name_inner_event
from .. import utils
from ..tl import types, functions


@name_inner_event
class JoinRequest(EventBuilder):
    """
    Occurs when someone requests to join a chat that has join request enabled.

    Note that this event only works for
    `channels <https://core.telegram.org/api/channel>`_ (megagroups)
    with ``join_request`` permission.

    Example
        .. code-block:: python

            from telethon import events

            @client.on(events.JoinRequest)
            async def handler(event):
                # Approve the user
                await event.approve()
                # Or reject:
                # await event.reject()
    """

    @classmethod
    def build(cls, update, others=None, self_id=None):
        if isinstance(update, types.UpdatePendingJoinRequests):
            return cls.Event(update)
        return None

    async def _resolve(self, client):
        await super()._resolve(client)
        self.users = []
        self.requests = []
        for user_id in update.recent_requesters:
            user = await client.get_entity(user_id)
            self.users.append(user)
        self._update = update

    class Event(EventCommon):
        def __init__(self, update):
            self.original_update = update
            peer = update.peer
            super().__init__(chat_peer=peer)
            self.peer = peer
            self.requests_pending = update.requests_pending
            self.recent_requesters = update.recent_requesters
            self._users = {}
            self._user_ids = update.recent_requesters

        async def get_user(self):
            """Returns the first user who requested to join."""
            if self._users:
                return next(iter(self._users.values()))
            if self.recent_requesters:
                user_id = self.recent_requesters[0]
                user = await self._client.get_entity(user_id)
                self._users[user_id] = user
                return user
            return None

        async def get_users(self):
            """Returns all users who requested to join."""
            if not self._users:
                for user_id in self.recent_requesters:
                    user = await self._client.get_entity(user_id)
                    self._users[user_id] = user
            return list(self._users.values())

        async def approve(self, blocked=False):
            """
            Approve the join request.

            Args:
                blocked: Whether to block the user after approving.
            """
            from ..tl.functions.messages import HideChatJoinRequestRequest

            user = await self.get_user()
            if not user:
                return

            peer = await self._client.get_input_entity(self.peer)
            user_peer = await self._client.get_input_entity(user)

            return await self._client(HideChatJoinRequestRequest(
                peer=peer,
                user_id=user_peer,
                approved=True
            ))

        async def reject(self, blocked=False):
            """
            Reject the join request.

            Args:
                blocked: Whether to block the user after rejecting.
            """
            from ..tl.functions.messages import HideChatJoinRequestRequest

            user = await self.get_user()
            if not user:
                return

            peer = await self._client.get_input_entity(self.peer)
            user_peer = await self._client.get_input_entity(user)

            return await self._client(HideChatJoinRequestRequest(
                peer=peer,
                user_id=user_peer,
                approved=False
            ))

        async def approve_all(self):
            """
            Approve all pending join requests in the chat.
            """
            from ..tl.functions.messages import HideAllChatJoinRequestsRequest

            peer = await self._client.get_input_entity(self.peer)

            return await self._client(HideAllChatJoinRequestsRequest(
                peer=peer,
                approved=True
            ))

        async def reject_all(self):
            """
            Reject all pending join requests in the chat.
            """
            from ..tl.functions.messages import HideAllChatJoinRequestsRequest

            peer = await self._client.get_input_entity(self.peer)

            return await self._client(HideAllChatJoinRequestsRequest(
                peer=peer,
                approved=False
            ))
