import pytest

from telethon import TelegramClient, events
from telethon.client.payments import GiftMethods
from telethon.client.protection import (
    ProtectionPolicy,
    ScamModuleDetected,
    find_dangerous_request,
)
from telethon.client.users import UserMethods
from telethon.tl import TLRequest, functions, types
from telethon.tl.functions.account import DeleteAccountRequest, GetAuthorizationsRequest
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
        self.last_ordered = None

    def send(self, request, ordered=False):
        self.last_request = request
        self.last_ordered = ordered

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


class _WrapperRequest(TLRequest):
    CONSTRUCTOR_ID = 0x77AACC11
    SUBCLASS_OF_ID = 0

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_dict(self):
        return {"_": "_WrapperRequest"}


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


def test_find_dangerous_request_ignores_non_request_input():
    assert find_dangerous_request(None) is None
    assert find_dangerous_request(object()) is None


@pytest.mark.asyncio
async def test_dangerous_request_blocked_inside_generator_container():
    client = TelegramClient(None, 1, "1")
    wrapped = _WrapperRequest(
        requests=(request for request in [DeleteAccountRequest(reason="x")]),
    )

    with pytest.raises(ScamModuleDetected):
        await client._call(_FailSender(), wrapped)


@pytest.mark.asyncio
async def test_dangerous_request_blocked_inside_mapping_container():
    client = TelegramClient(None, 1, "1")
    wrapped = _WrapperRequest(
        requests={"danger": DeleteAccountRequest(reason="x")},
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
async def test_safe_profile_allows_read_only_authorizations_requests():
    client = TelegramClient(None, 1, "1")
    sender = _EchoSender()

    policy = client.set_protection_mode("safe")
    result = await client._call(sender, GetAuthorizationsRequest())

    assert policy.mode == "safe"
    assert sender.last_request.__class__ is GetAuthorizationsRequest
    assert result == []


@pytest.mark.asyncio
async def test_off_profile_disables_blocking():
    client = TelegramClient(None, 1, "1")
    sender = _EchoSender()

    policy = client.set_protection_mode("off")
    result = await client._call(sender, DeleteAccountRequest(reason="x"))

    assert policy.mode == "off"
    assert sender.last_request.__class__ is DeleteAccountRequest
    assert result == []


@pytest.mark.asyncio
async def test_custom_policy_can_allow_strictly_blocked_request():
    client = TelegramClient(None, 1, "1")
    sender = _EchoSender()

    policy = client.set_protection_mode(
        "custom",
        allowed_requests=(DeleteAccountRequest,),
    )
    result = await client._call(sender, DeleteAccountRequest(reason="x"))

    assert policy.mode == "custom"
    assert sender.last_request.__class__ is DeleteAccountRequest
    assert result == []


@pytest.mark.asyncio
async def test_dry_run_reports_but_does_not_block():
    client = TelegramClient(None, 1, "1")
    sender = _EchoSender()
    seen = []

    @client.on_blocked_request
    async def _capture(violation):
        seen.append(violation)

    policy = client.set_protection_mode("strict", dry_run=True)
    result = await client._call(sender, DeleteAccountRequest(reason="x"))

    assert policy.dry_run is True
    assert sender.last_request.__class__ is DeleteAccountRequest
    assert result == []
    assert len(seen) == 1
    assert seen[0].policy.mode == "strict"
    assert seen[0].dangerous_request.__class__ is DeleteAccountRequest


def test_set_protection_policy_accepts_policy_instance():
    client = TelegramClient(None, 1, "1")
    policy = ProtectionPolicy(
        mode="custom",
        blocked_requests=(DeleteAccountRequest,),
        raise_on_blocked=False,
    )

    applied = client.set_protection_policy(policy)

    assert applied is policy
    assert client.get_protection_policy() is policy
    assert client.protection_mode == "custom"


def test_invalid_protection_mode_is_rejected():
    client = TelegramClient(None, 1, "1")

    with pytest.raises(ValueError):
        client.set_protection_mode("paranoid")


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
async def test_request_middleware_can_short_circuit_call():
    client = TelegramClient(None, 1, "1")
    sender = _FailSender()
    seen = []

    @client.request_middleware
    async def _middleware(request, ctx, next):
        seen.append(
            (
                request.__class__,
                ctx.attempt,
                ctx.ordered,
                ctx.flood_sleep_threshold,
                ctx.is_batch,
                ctx.original_request.__class__,
            )
        )
        return "short-circuit"

    result = await client._call(
        sender,
        functions.help.GetConfigRequest(),
        ordered=True,
        flood_sleep_threshold=17,
    )

    assert result == "short-circuit"
    assert seen == [(functions.help.GetConfigRequest, 1, True, 17, False, functions.help.GetConfigRequest)]


@pytest.mark.asyncio
async def test_request_middleware_wraps_sender_send():
    client = TelegramClient(None, 1, "1")
    sender = _EchoSender()
    calls = []

    async def first(request, ctx, next):
        calls.append(("first-before", ctx.attempt, ctx.is_batch))
        result = await next()
        calls.append(("first-after", ctx.attempt, ctx.is_batch))
        return result

    async def second(request, ctx, next):
        calls.append(("second-before", ctx.attempt, ctx.is_batch))
        result = await next()
        calls.append(("second-after", ctx.attempt, ctx.is_batch))
        return result

    client.add_request_middleware(first)
    client.add_request_middleware(second)
    result = await client._call(sender, [functions.help.GetConfigRequest()], ordered=True)

    assert result == [[]]
    assert calls == [
        ("first-before", 1, True),
        ("second-before", 1, True),
        ("second-after", 1, True),
        ("first-after", 1, True),
    ]
    assert sender.last_ordered is True
    assert isinstance(sender.last_request, list)
    assert len(sender.last_request) == 1

    client.remove_request_middleware(second)
    calls.clear()
    await client._call(sender, functions.help.GetConfigRequest())
    assert calls == [
        ("first-before", 1, False),
        ("first-after", 1, False),
    ]


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
