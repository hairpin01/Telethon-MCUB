import typing

from ..tl import functions, types
from .. import hints

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


class ReactionMethods:
    async def send_reaction(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        message: typing.Union[int, "types.Message"],
        reaction: typing.Union[str, typing.List[str]] = "👍",
        big: bool = False,
        add_to_recent: bool = True
    ):
        """
        Send a reaction to a message.

        Args:
            entity: The chat or channel to send the reaction to.
            message: The message ID or Message object.
            reaction: Emoji reaction (string) or list of emojis.
            big: Use big reaction.
            add_to_recent: Add to recent reactions.

        Returns:
            Updates with the result.

        Examples:
            >>> await client.send_reaction(chat, message, "🔥")
            >>> await client.send_reaction(chat, message, ["👍", "❤️"])
        """
        peer = await self.get_input_entity(entity)
        msg_id = message.id if hasattr(message, 'id') else message

        reactions = []
        if isinstance(reaction, str):
            reactions.append(types.ReactionEmoji(emoticon=reaction))
        elif isinstance(reaction, list):
            for r in reaction:
                reactions.append(types.ReactionEmoji(emoticon=r))

        return await self(functions.messages.SendReactionRequest(
            peer=peer,
            msg_id=msg_id,
            big=big,
            add_to_recent=add_to_recent,
            reaction=reactions
        ))

    async def get_message_reactions_list(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        message: typing.Union[int, "types.Message"],
        reaction: typing.Optional[str] = None,
        limit: int = 100
    ):
        """
        Get the list of users who reacted to a message.

        Args:
            entity: The chat or channel.
            message: The message ID or Message object.
            reaction: Filter by specific reaction.
            limit: Number of results.

        Returns:
            MessageReactionsList with users and reactions.
        """
        peer = await self.get_input_entity(entity)
        msg_id = message.id if hasattr(message, 'id') else message

        reaction_obj = None
        if reaction:
            reaction_obj = types.ReactionEmoji(emoticon=reaction)

        return await self(functions.messages.GetMessageReactionsListRequest(
            peer=peer,
            id=msg_id,
            reaction=reaction_obj,
            limit=limit
        ))

    async def set_default_reaction(
        self: "TelegramClient",
        reaction: str = "👍"
    ):
        """
        Set the default reaction for new messages.

        Args:
            reaction: Emoji reaction.
        """
        reaction_obj = types.ReactionEmoji(emoticon=reaction)
        return await self(functions.messages.SetDefaultReactionRequest(
            reaction=reaction_obj
        ))

    async def set_chat_available_reactions(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        reactions: typing.List[str],
        reactions_limit: typing.Optional[int] = None,
        paid_enabled: typing.Optional[bool] = None
    ):
        """
        Set available reactions for a chat/channel.

        Args:
            entity: The chat or channel.
            reactions: List of available emojis.
            reactions_limit: Reactions limit.
            paid_enabled: Enable paid reactions.
        """
        peer = await self.get_input_entity(entity)

        reaction_objects = []
        for r in reactions:
            reaction_objects.append(types.ReactionEmoji(emoticon=r))

        chat_reactions = types.ChatReactionsSome(reactions=reaction_objects)

        return await self(functions.messages.SetChatAvailableReactionsRequest(
            peer=peer,
            available_reactions=chat_reactions,
            reactions_limit=reactions_limit,
            paid_enabled=paid_enabled
        ))

    async def send_photo_as_private(
        self: "TelegramClient",
        entity: "hints.EntityLike",
        photo: typing.Union[str, bytes, "types.InputPhoto"],
        caption: typing.Optional[str] = None,
        **kwargs
    ):
        """
        Send a photo as a private message to the user.
        
        This sends the photo directly to the user's private chat (saved messages).

        Args:
            entity: The user to send the photo to.
            photo: The photo to send (file path, bytes, or InputPhoto).
            caption: Optional caption for the photo.
            **kwargs: Additional arguments for send_file.

        Returns:
            The sent message.
        """
        return await self.send_file(
            entity,
            photo,
            caption=caption,
            **kwargs
        )
