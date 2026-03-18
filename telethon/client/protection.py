from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Optional

from telethon.tl import TLRequest
from telethon.tl.functions.account import (
    DeleteAccountRequest,
    InitTakeoutSessionRequest,
    ResetAuthorizationRequest,
    ResetPasswordRequest,
    ChangePhoneRequest,
    UpdatePasswordSettingsRequest,
    ResetWebAuthorizationsRequest,
    FinishTakeoutSessionRequest,
    GetAuthorizationsRequest,
    GetWebAuthorizationsRequest,
)
from telethon.tl.functions.auth import (
    LogOutRequest,
    ResetAuthorizationsRequest,
    BindTempAuthKeyRequest,
    ExportAuthorizationRequest,
    ImportAuthorizationRequest,
    ImportBotAuthorizationRequest,
)

logger = logging.getLogger(__name__)

MAX_NESTING_DEPTH = 20


class ScamModuleDetected(Exception):
    """Raised when a dangerous or blacklisted Telegram API request is detected."""
    pass

# Single source of truth — DANGEROUS_REQUEST_IDS is derived automatically.
DANGEROUS_REQUESTS: tuple[type[TLRequest], ...] = (
    DeleteAccountRequest,
    ResetAuthorizationRequest,       # terminate a specific session
    ResetAuthorizationsRequest,      # terminate ALL other sessions
    ResetWebAuthorizationsRequest,   # terminate all web (widget) sessions
    BindTempAuthKeyRequest,          # bind temporary auth key
    # ExportAuthorizationRequest,    # export auth to another DC
    ImportAuthorizationRequest,      # import exported auth bytes
    # ImportBotAuthorizationRequest,   # hijack via bot token
    # log:
    # ERROR:kernel:Inline bot handler registration failed: Method 'ImportBotAuthorizationRequest' blocked!

    # ExportLoginTokenRequest,         # QR-login token export
    # ImportLoginTokenRequest,         # QR-login token import
    # AcceptLoginTokenRequest,         # approve QR-login
    # Why #? Well, how will you register via QR in the web panel? :)
    InitTakeoutSessionRequest,
    FinishTakeoutSessionRequest,
    ResetPasswordRequest,
    ChangePhoneRequest,
    UpdatePasswordSettingsRequest,
    LogOutRequest,
    GetWebAuthorizationsRequest,
    GetAuthorizationsRequest # hmmmm, Are you sure I won't break anything?
)

# Derived automatically — no manual sync needed.
DANGEROUS_REQUEST_IDS: frozenset[int] = frozenset(
    r.CONSTRUCTOR_ID for r in DANGEROUS_REQUESTS
)


def find_dangerous_request(
    request: TLRequest,
) -> Optional[TLRequest]:
    """
    Find a blacklisted request even when it is wrapped inside ``Invoke*``
    containers (iterative DFS, cycle-safe).

    Parameters
    ----------
    request:
        The top-level TLRequest to inspect.

    Returns
    -------
    The first dangerous TLRequest found, or ``None``.

    Raises
    ------
    ScamModuleDetected
        If the nesting depth exceeds ``MAX_NESTING_DEPTH`` — a possible
        evasion attempt via deeply nested wrappers.
    """
    if not isinstance(request, TLRequest):
        return None

    stack: list[tuple[int, TLRequest]] = [(0, request)]
    # id()-based deduplication безопасна здесь: объекты держатся живыми стеком,
    # поэтому GC не переиспользует их адреса в течение всего обхода.
    seen: set[int] = set()

    while stack:
        depth, current = stack.pop()

        if depth >= MAX_NESTING_DEPTH:
            raise ScamModuleDetected(
                f"Request nesting depth exceeds {MAX_NESTING_DEPTH} — "
                "possible evasion attempt via deeply nested wrappers."
            )

        current_oid = id(current)
        if current_oid in seen:
            continue
        seen.add(current_oid)

        if current.CONSTRUCTOR_ID in DANGEROUS_REQUEST_IDS:
            logger.warning(
                "Blocked dangerous request: %s (constructor_id=0x%X)",
                type(current).__name__,
                current.CONSTRUCTOR_ID,
            )
            return current

        next_depth = depth + 1

        # Single-request wrapper attributes (e.g. InvokeWithLayer.query)
        for attr in ("query", "request"):
            value = getattr(current, attr, None)
            if isinstance(value, TLRequest):
                stack.append((next_depth, value))

        # Batch-request wrapper attributes (e.g. InvokeMultiMedia.requests)
        for attr in ("queries", "requests"):
            value = getattr(current, attr, None)
            if isinstance(value, Mapping):
                value = value.values()
            elif isinstance(value, (str, bytes, bytearray)) or not isinstance(
                value, Iterable
            ):
                continue

            for inner in value:
                if isinstance(inner, TLRequest):
                    stack.append((next_depth, inner))

    return None


def assert_safe(request: TLRequest) -> None:
    """
    Raise :class:`ScamModuleDetected` if *request* (or any request nested
    inside it) is on the blacklist, or if the nesting depth exceeds
    ``MAX_NESTING_DEPTH`` (possible evasion attempt).

    Use this as the single call-site guard instead of checking the return
    value of :func:`find_dangerous_request` manually.

    Example
    -------
    ::

        async def invoke(self, request):
            assert_safe(request)
            return await self.client(request)
    """
    dangerous = find_dangerous_request(request)
    if dangerous is not None:
        raise ScamModuleDetected(
            f"Blocked dangerous Telegram request: {type(dangerous).__name__} "
            f"(constructor_id=0x{dangerous.CONSTRUCTOR_ID:08X})"
        )
