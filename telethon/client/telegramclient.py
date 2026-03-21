import warnings
import logging

try:
    import cryptg
except ImportError:
    cryptg = None

if cryptg is None:
    warnings.warn(
        "cryptg is not installed. For faster encryption/decryption, "
        "install it with: pip install cryptg",
        UserWarning,
        stacklevel=2,
    )

from . import (
    AccountMethods,
    AuthMethods,
    DownloadMethods,
    DialogMethods,
    ChatMethods,
    HistoryMethods,
    TopicMethods,
    BotMethods,
    MessageMethods,
    UploadMethods,
    ButtonMethods,
    UpdateMethods,
    MessageParseMethods,
    UserMethods,
    ReactionMethods,
    GiftMethods,
    TelegramBaseClient,
)


class TelegramClient(
    AccountMethods,
    AuthMethods,
    DownloadMethods,
    DialogMethods,
    ChatMethods,
    HistoryMethods,
    TopicMethods,
    BotMethods,
    MessageMethods,
    UploadMethods,
    ButtonMethods,
    UpdateMethods,
    MessageParseMethods,
    UserMethods,
    ReactionMethods,
    GiftMethods,
    TelegramBaseClient,
):
    pass
