import pytest

from telethon import TelegramClient, types


def get_client():
    return TelegramClient(None, 1, '1')


@pytest.mark.asyncio
async def test_message_answer_method_exists():
    """Test that message.answer() method exists"""
    from telethon.tl.custom.message import Message
    assert hasattr(Message, 'answer')
    assert callable(getattr(Message, 'answer'))


@pytest.mark.asyncio
async def test_message_answer_is_alias_for_reply():
    """Test that answer() is an alias for reply()"""
    from telethon.tl.custom.message import Message
    assert Message.answer.__doc__ is not None
    assert "reply" in Message.answer.__doc__.lower()
