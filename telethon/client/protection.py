from telethon.tl.functions.account import (
    DeleteAccountRequest,
    ResetAuthorizationRequest,
    ChangePhoneRequest,
    ChangePasswordRequest,
    ResetPasswordRequest,
)
from telethon.tl.functions.auth import (
    ResetLoginEmailRequest,
)


class ScamModuleDetected(Exception):
    pass


DANGEROUS_REQUESTS = (
    DeleteAccountRequest,
    ResetAuthorizationRequest,
    ChangePhoneRequest,
    ChangePasswordRequest,
    ResetPasswordRequest,
    ResetLoginEmailRequest,
)
