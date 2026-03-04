from collections.abc import Iterable, Mapping

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
)
from telethon.tl.functions.auth import LogOutRequest, ResetAuthorizationsRequest


class ScamModuleDetected(Exception):
    pass


DANGEROUS_REQUESTS = (
    DeleteAccountRequest,
    InitTakeoutSessionRequest,
    ResetAuthorizationRequest,
    ResetAuthorizationsRequest,
    ResetPasswordRequest,
    ChangePhoneRequest,
    UpdatePasswordSettingsRequest,
    ResetWebAuthorizationsRequest,
    FinishTakeoutSessionRequest,
    LogOutRequest,
)

DANGEROUS_REQUEST_IDS = frozenset(
    {
        DeleteAccountRequest.CONSTRUCTOR_ID,
        InitTakeoutSessionRequest.CONSTRUCTOR_ID,
        ResetAuthorizationRequest.CONSTRUCTOR_ID,
        ResetAuthorizationsRequest.CONSTRUCTOR_ID,
        ResetPasswordRequest.CONSTRUCTOR_ID,
        ChangePhoneRequest.CONSTRUCTOR_ID,
        UpdatePasswordSettingsRequest.CONSTRUCTOR_ID,
        ResetWebAuthorizationsRequest.CONSTRUCTOR_ID,
        FinishTakeoutSessionRequest.CONSTRUCTOR_ID,
        LogOutRequest.CONSTRUCTOR_ID,
    }
)


def find_dangerous_request(request: TLRequest):
    """
    Find blocked requests even when they are wrapped with `Invoke*` containers.
    """
    if not isinstance(request, TLRequest):
        return None

    stack = [request]
    seen = set()

    while stack:
        current = stack.pop()
        current_id = id(current)
        if current_id in seen:
            continue
        seen.add(current_id)

        if current.CONSTRUCTOR_ID in DANGEROUS_REQUEST_IDS:
            return current

        for attr in ("query", "request"):
            value = getattr(current, attr, None)
            if isinstance(value, TLRequest):
                stack.append(value)

        for attr in ("queries", "requests"):
            value = getattr(current, attr, None)
            if isinstance(value, Mapping):
                value = value.values()
            elif isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Iterable):
                continue

            for inner in value:
                if isinstance(inner, TLRequest):
                    stack.append(inner)

    return None
