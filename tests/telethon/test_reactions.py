import pytest

from telethon import TelegramClient, types


def get_client():
    return TelegramClient(None, 1, '1')


def test_reaction_methods_exist():
    """Test that ReactionMethods class exists and has required methods"""
    assert hasattr(TelegramClient, 'send_reaction')
    assert hasattr(TelegramClient, 'get_message_reactions_list')
    assert hasattr(TelegramClient, 'set_default_reaction')
    assert hasattr(TelegramClient, 'set_chat_available_reactions')
    assert hasattr(TelegramClient, 'send_photo_as_private')


def test_send_reaction_is_async():
    """Test that send_reaction is an async method"""
    client = get_client()
    import inspect
    assert inspect.iscoroutinefunction(client.send_reaction)


def test_get_message_reactions_list_is_async():
    """Test that get_message_reactions_list is an async method"""
    client = get_client()
    import inspect
    assert inspect.iscoroutinefunction(client.get_message_reactions_list)


def test_set_default_reaction_is_async():
    """Test that set_default_reaction is an async method"""
    client = get_client()
    import inspect
    assert inspect.iscoroutinefunction(client.set_default_reaction)


def test_set_chat_available_reactions_is_async():
    """Test that set_chat_available_reactions is an async method"""
    client = get_client()
    import inspect
    assert inspect.iscoroutinefunction(client.set_chat_available_reactions)


def test_send_photo_as_private_is_async():
    """Test that send_photo_as_private is an async method"""
    client = get_client()
    import inspect
    assert inspect.iscoroutinefunction(client.send_photo_as_private)


def test_reaction_method_signatures():
    """Test that methods have correct signatures"""
    import inspect
    
    send_reaction_sig = inspect.signature(TelegramClient.send_reaction)
    params = list(send_reaction_sig.parameters.keys())
    assert 'entity' in params
    assert 'message' in params
    assert 'reaction' in params
    
    get_reactions_sig = inspect.signature(TelegramClient.get_message_reactions_list)
    params = list(get_reactions_sig.parameters.keys())
    assert 'entity' in params
    assert 'message' in params
    
    set_default_sig = inspect.signature(TelegramClient.set_default_reaction)
    params = list(set_default_sig.parameters.keys())
    assert 'reaction' in params
    
    set_chat_sig = inspect.signature(TelegramClient.set_chat_available_reactions)
    params = list(set_chat_sig.parameters.keys())
    assert 'entity' in params
    assert 'reactions' in params
    
    send_photo_sig = inspect.signature(TelegramClient.send_photo_as_private)
    params = list(send_photo_sig.parameters.keys())
    assert 'entity' in params
    assert 'photo' in params
