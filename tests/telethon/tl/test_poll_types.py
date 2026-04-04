import pytest
from telethon.tl import types, functions


def test_user_basic_creation():
    """Test basic User creation"""
    user = types.User(id=123, bot=True, bot_info_version=1)
    assert user.id == 123
    assert user.bot is True
    assert user.bot_info_version == 1


def test_poll_basic_creation():
    """Test basic Poll creation"""
    poll = types.Poll(
        id=1,
        question=types.TextWithEntities(text='What is your favorite color?', entities=[]),
        answers=[]
    )
    assert poll.id == 1
    assert poll.question.text == 'What is your favorite color?'
    assert poll.answers == []


def test_poll_answer():
    """Test PollAnswer creation"""
    answer = types.PollAnswer(
        text=types.TextWithEntities(text='Red', entities=[]),
        option=b'\x00'
    )
    assert answer.text.text == 'Red'
    assert answer.option == b'\x00'


def test_keyboard_button_creation():
    """Test KeyboardButton creation"""
    btn = types.KeyboardButton(text='Click me')
    assert btn.text == 'Click me'


def test_message_media_poll():
    """Test MessageMediaPoll creation"""
    poll = types.Poll(
        id=1,
        question=types.TextWithEntities(text='Test?', entities=[]),
        answers=[]
    )
    results = types.PollResults()
    media = types.MessageMediaPoll(poll=poll, results=results)
    assert media.poll.id == 1


def test_message_action_managed_bot_created():
    """Test MessageActionManagedBotCreated creation (Bot API 9.6)"""
    action = types.MessageActionManagedBotCreated(bot_id=123456)
    assert action.bot_id == 123456


def test_message_action_poll_append_answer():
    """Test MessageActionPollAppendAnswer creation (Bot API 9.6)"""
    answer = types.PollAnswer(
        text=types.TextWithEntities(text='New option', entities=[]),
        option=b'\x01'
    )
    action = types.MessageActionPollAppendAnswer(answer=answer)
    assert action.answer.text.text == 'New option'


def test_message_action_poll_delete_answer():
    """Test MessageActionPollDeleteAnswer creation (Bot API 9.6)"""
    answer = types.PollAnswer(
        text=types.TextWithEntities(text='Deleted', entities=[]),
        option=b'\x01'
    )
    action = types.MessageActionPollDeleteAnswer(answer=answer)
    assert action.answer.option == b'\x01'


def test_update_managed_bot():
    """Test UpdateManagedBot creation (Bot API 9.6)"""
    update = types.UpdateManagedBot(user_id=100, bot_id=200, qts=123)
    assert update.user_id == 100
    assert update.bot_id == 200
    assert update.qts == 123


def test_request_peer_type_create_bot():
    """Test RequestPeerTypeCreateBot creation (Bot API 9.6)"""
    peer_type = types.RequestPeerTypeCreateBot(
        bot_managed=True,
        suggested_name="My Bot",
        suggested_username="my_bot"
    )
    assert peer_type.bot_managed is True
    assert peer_type.suggested_name == "My Bot"
    assert peer_type.suggested_username == "my_bot"


def test_button_request_managed_bot():
    """Test Button.request_managed_bot creation (Bot API 9.6)"""
    from telethon.tl.custom.button import Button
    
    btn = Button.request_managed_bot(
        text="Create a bot",
        suggested_name="Test Bot",
        suggested_username="test_bot"
    )
    
    assert isinstance(btn.button, types.KeyboardButtonRequestPeer)
    assert btn.button.text == "Create a bot"
    assert btn.button.peer_type.bot_managed is True
    assert btn.button.peer_type.suggested_name == "Test Bot"
    assert btn.button.peer_type.suggested_username == "test_bot"


def test_bot_update_event():
    """Test BotUpdate event creation (Bot API 9.6)"""
    from telethon.events.botupdate import BotUpdate
    
    update = types.UpdateManagedBot(user_id=100, bot_id=200, qts=123)
    event = BotUpdate.build(update)
    
    assert event.user_id == 100
    assert event.bot_id == 200
    assert event.qts == 123
    assert event.is_creation is True


def test_add_poll_answer_request():
    """Test AddPollAnswerRequest creation (Bot API 9.6)"""
    from telethon.tl.functions.messages import AddPollAnswerRequest
    
    answer = types.PollAnswer(
        text=types.TextWithEntities(text='New answer', entities=[]),
        option=b'\x03'
    )
    request = AddPollAnswerRequest(
        peer=None,  # Would be InputPeer in real usage
        msg_id=123,
        answer=answer
    )
    assert request.msg_id == 123
    assert request.answer.text.text == 'New answer'


def test_delete_poll_answer_request():
    """Test DeletePollAnswerRequest creation (Bot API 9.6)"""
    from telethon.tl.functions.messages import DeletePollAnswerRequest
    
    request = DeletePollAnswerRequest(
        peer=None,  # Would be InputPeer in real usage
        msg_id=123,
        option=b'\x02'
    )
    assert request.msg_id == 123
    assert request.option == b'\x02'
