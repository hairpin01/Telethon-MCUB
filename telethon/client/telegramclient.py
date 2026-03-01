from . import (
    AccountMethods, AuthMethods, DownloadMethods, DialogMethods, ChatMethods,
    BotMethods, MessageMethods, UploadMethods, ButtonMethods, UpdateMethods,
    MessageParseMethods, UserMethods, ReactionMethods, TelegramBaseClient
)


class TelegramClient(
    AccountMethods, AuthMethods, DownloadMethods, DialogMethods, ChatMethods,
    BotMethods, MessageMethods, UploadMethods, ButtonMethods, UpdateMethods,
    MessageParseMethods, UserMethods, ReactionMethods, TelegramBaseClient
):
    pass
