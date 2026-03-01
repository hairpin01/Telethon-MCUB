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
