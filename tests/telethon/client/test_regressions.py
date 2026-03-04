import pytest

from telethon import TelegramClient, events
from telethon.client.payments import GiftMethods
from telethon.client.protection import ScamModuleDetected
from telethon.client.users import UserMethods
from telethon.tl import functions, types
from telethon.tl.functions.account import DeleteAccountRequest
from telethon.tl.functions.auth import LogOutRequest, ResetAuthorizationsRequest


class _DummyUserClient(UserMethods):
    def __init__(self):
        self._sender = object()
        self.seen_threshold = None

    async def _call(self, sender, request, ordered=False, flood_sleep_threshold=None):
        self.seen_threshold = flood_sleep_threshold
        return "ok"


class _FailSender:
    def send(self, request, ordered=False):  # pragma: no cover - should never run
        raise AssertionError("sender.send should not be called")


class _EchoSender:
    def __init__(self):
        self.last_request = None

    def send(self, request, ordered=False):
        self.last_request = request

        async def _ok():
            return []

        if isinstance(request, list):
            return [_ok() for _ in request]
        return _ok()


class _DummyGiftClient(GiftMethods):
    def __init__(self):
        self.request_limits = []
        self.thresholds = []

    async def __call__(self, request, ordered=False, flood_sleep_threshold=None):
        self.request_limits.append(request.limit)
        self.thresholds.append(flood_sleep_threshold)

        class _Result:
            gifts = []
            next_offset = None

        return _Result()


@pytest.mark.asyncio
async def test_call_forwards_flood_sleep_threshold():
    client = _DummyUserClient()
    result = await client.__call__(object(), flood_sleep_threshold=17)
    assert result == "ok"
    assert client.seen_threshold == 17


@pytest.mark.asyncio
async def test_dangerous_request_blocked_in_batch():
    client = TelegramClient(None, 1, "1")

    with pytest.raises(ScamModuleDetected):
        await client._call(_FailSender(), [DeleteAccountRequest(reason="x")])

    with pytest.raises(ScamModuleDetected):
        await client._call(
            _FailSender(),
            (request for request in [DeleteAccountRequest(reason="x")]),
        )


@pytest.mark.asyncio
async def test_dangerous_request_blocked_when_wrapped():
    client = TelegramClient(None, 1, "1")
    wrapped = functions.InvokeWithoutUpdatesRequest(
        query=functions.InvokeWithTakeoutRequest(
            takeout_id=1,
            query=DeleteAccountRequest(reason="x"),
        )
    )

    with pytest.raises(ScamModuleDetected):
        await client._call(_FailSender(), wrapped)


@pytest.mark.asyncio
async def test_additional_dangerous_auth_methods_are_blocked():
    client = TelegramClient(None, 1, "1")

    with pytest.raises(ScamModuleDetected):
        await client._call(_FailSender(), ResetAuthorizationsRequest())

    with pytest.raises(ScamModuleDetected):
        await client._call(_FailSender(), LogOutRequest())


@pytest.mark.asyncio
async def test_generator_requests_are_not_dropped():
    client = TelegramClient(None, 1, "1")
    sender = _EchoSender()

    requests = (request for request in [functions.help.GetConfigRequest()])
    result = await client._call(sender, requests)

    assert isinstance(sender.last_request, list)
    assert len(sender.last_request) == 1
    assert len(result) == 1


@pytest.mark.asyncio
async def test_dispatch_event_matches_builder_event_class():
    client = TelegramClient(None, 1, "1")
    calls = []

    async def handler(event):
        calls.append(event)

    client.add_event_handler(handler, events.Album)

    message_1 = types.Message(
        id=1,
        peer_id=types.PeerUser(42),
        date=None,
        message="a",
        grouped_id=123,
    )
    message_2 = types.Message(
        id=2,
        peer_id=types.PeerUser(42),
        date=None,
        message="b",
        grouped_id=123,
    )
    event = events.Album.Event([message_1, message_2])

    await client._dispatch_event(event)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_get_saved_gifts_uses_page_limit_for_unbounded_fetch():
    client = _DummyGiftClient()
    gifts = [gift async for gift in client.get_saved_gifts("me", limit=0)]

    assert gifts == []
    assert client.request_limits == [100]
    assert client.thresholds == [60]


@pytest.mark.asyncio
async def test_get_saved_gifts_rejects_negative_limit():
    client = _DummyGiftClient()

    with pytest.raises(ValueError):
        _ = [gift async for gift in client.get_saved_gifts("me", limit=-1)]
