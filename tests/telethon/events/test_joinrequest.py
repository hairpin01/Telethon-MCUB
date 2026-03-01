import pytest

from telethon import TelegramClient, events, types


def get_client():
    return TelegramClient(None, 1, '1')


def test_join_request_event_exists():
    """Test that JoinRequest event class exists"""
    assert hasattr(events, 'JoinRequest')


def test_join_request_build():
    """Test that JoinRequest event builds from UpdatePendingJoinRequests"""
    update = types.UpdatePendingJoinRequests(
        peer=types.PeerChannel(123),
        requests_pending=5,
        recent_requesters=[456, 789]
    )
    event = events.JoinRequest.build(update)
    assert event is not None
    assert isinstance(event, events.JoinRequest.Event)


def test_join_request_not_build_from_other():
    """Test that JoinRequest doesn't build from other updates"""
    from telethon import types
    update = types.UpdateNewMessage(
        message=types.Message(
            id=1,
            peer_id=types.PeerUser(123),
            date=0,
            message="test"
        ),
        pts=1,
        pts_count=1
    )
    event = events.JoinRequest.build(update)
    assert event is None


@pytest.mark.asyncio
async def test_join_request_event_has_approve_method():
    """Test that JoinRequest.Event has approve method"""
    update = types.UpdatePendingJoinRequests(
        peer=types.PeerChannel(123),
        requests_pending=5,
        recent_requesters=[456]
    )
    event = events.JoinRequest.build(update)
    assert hasattr(event, 'approve')
    assert callable(event.approve)


@pytest.mark.asyncio
async def test_join_request_event_has_reject_method():
    """Test that JoinRequest.Event has reject method"""
    update = types.UpdatePendingJoinRequests(
        peer=types.PeerChannel(123),
        requests_pending=5,
        recent_requesters=[456]
    )
    event = events.JoinRequest.build(update)
    assert hasattr(event, 'reject')
    assert callable(event.reject)


@pytest.mark.asyncio
async def test_join_request_event_has_approve_all_method():
    """Test that JoinRequest.Event has approve_all method"""
    update = types.UpdatePendingJoinRequests(
        peer=types.PeerChannel(123),
        requests_pending=5,
        recent_requesters=[456]
    )
    event = events.JoinRequest.build(update)
    assert hasattr(event, 'approve_all')
    assert callable(event.approve_all)


@pytest.mark.asyncio
async def test_join_request_event_has_reject_all_method():
    """Test that JoinRequest.Event has reject_all method"""
    update = types.UpdatePendingJoinRequests(
        peer=types.PeerChannel(123),
        requests_pending=5,
        recent_requesters=[456]
    )
    event = events.JoinRequest.build(update)
    assert hasattr(event, 'reject_all')
    assert callable(event.reject_all)


@pytest.mark.asyncio
async def test_join_request_event_has_get_user_method():
    """Test that JoinRequest.Event has get_user method"""
    update = types.UpdatePendingJoinRequests(
        peer=types.PeerChannel(123),
        requests_pending=5,
        recent_requesters=[456]
    )
    event = events.JoinRequest.build(update)
    assert hasattr(event, 'get_user')
    assert callable(event.get_user)


@pytest.mark.asyncio
async def test_join_request_event_has_get_users_method():
    """Test that JoinRequest.Event has get_users method"""
    update = types.UpdatePendingJoinRequests(
        peer=types.PeerChannel(123),
        requests_pending=5,
        recent_requesters=[456, 789]
    )
    event = events.JoinRequest.build(update)
    assert hasattr(event, 'get_users')
    assert callable(event.get_users)
