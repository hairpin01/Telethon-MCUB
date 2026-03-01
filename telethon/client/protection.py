from telethon.tl.functions.account import (
    DeleteAccountRequest,
    ResetAuthorizationRequest,
    ResetPasswordRequest,
    ChangePhoneRequest,
    UpdatePasswordSettingsRequest,
    ResetWebAuthorizationsRequest,
    FinishTakeoutSessionRequest,
)


class ScamModuleDetected(Exception):
    pass


DANGEROUS_REQUESTS = (
    DeleteAccountRequest,
    ResetAuthorizationRequest,
    ResetPasswordRequest,
    ChangePhoneRequest,
    UpdatePasswordSettingsRequest,
    ResetWebAuthorizationsRequest,
    FinishTakeoutSessionRequest,
)

DANGEROUS_REQUEST_IDS = frozenset({
    DeleteAccountRequest.CONSTRUCTOR_ID,
    ResetAuthorizationRequest.CONSTRUCTOR_ID,
    ResetPasswordRequest.CONSTRUCTOR_ID,
    ChangePhoneRequest.CONSTRUCTOR_ID,
    UpdatePasswordSettingsRequest.CONSTRUCTOR_ID,
    ResetWebAuthorizationsRequest.CONSTRUCTOR_ID,
    FinishTakeoutSessionRequest.CONSTRUCTOR_ID,
})
