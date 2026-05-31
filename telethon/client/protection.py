from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from telethon.tl import TLRequest
from telethon.tl.functions.account import (
    ChangePhoneRequest,
    DeleteAccountRequest,
    FinishTakeoutSessionRequest,
    GetAuthorizationsRequest,
    GetPasswordRequest,
    GetTmpPasswordRequest,
    GetWebAuthorizationsRequest,
    InitTakeoutSessionRequest,
    ResetAuthorizationRequest,
    ResetPasswordRequest,
    ResetWebAuthorizationRequest,
    ResetWebAuthorizationsRequest,
    UpdatePasswordSettingsRequest,
)
from telethon.tl.functions.auth import (
    BindTempAuthKeyRequest,
    DropTempAuthKeysRequest,
    # ExportAuthorizationRequest,
    ImportAuthorizationRequest,
    LogOutRequest,
    ResetAuthorizationsRequest,
)
from telethon.tl.functions.payments import (
    SendPaymentFormRequest,
    SendStarsFormRequest,
)

if TYPE_CHECKING:
    from telethon import TelegramClient

logger = logging.getLogger(__name__)

MAX_NESTING_DEPTH = 20
PROTECTION_MODES = frozenset({"off", "safe", "strict", "custom"})


class ScamModuleDetected(Exception):
    """Raised when a dangerous or blacklisted Telegram API request is detected."""


SAFE_DANGEROUS_REQUESTS: tuple[type[TLRequest], ...] = (
    DeleteAccountRequest,
    ResetAuthorizationRequest,
    ResetAuthorizationsRequest,
    ResetWebAuthorizationRequest,
    ResetWebAuthorizationsRequest,
    BindTempAuthKeyRequest,
    DropTempAuthKeysRequest,
    # ExportAuthorizationRequest,
    # Why the comment? how are you going to export the session to another DC in order to download the file??
    ImportAuthorizationRequest,
    InitTakeoutSessionRequest,
    FinishTakeoutSessionRequest,
    ResetPasswordRequest,
    ChangePhoneRequest,
    UpdatePasswordSettingsRequest,
    LogOutRequest,
)

STRICT_DANGEROUS_REQUESTS: tuple[type[TLRequest], ...] = (
    *SAFE_DANGEROUS_REQUESTS,
    GetWebAuthorizationsRequest,
    GetAuthorizationsRequest,
    GetPasswordRequest,
    GetTmpPasswordRequest,
    SendStarsFormRequest,
    SendPaymentFormRequest,
)

# Backward-compatible aliases
DANGEROUS_REQUESTS = STRICT_DANGEROUS_REQUESTS
DANGEROUS_REQUEST_IDS = frozenset(r.CONSTRUCTOR_ID for r in DANGEROUS_REQUESTS)


def _normalize_request_types(requests, field_name: str) -> tuple[type[TLRequest], ...]:
    if not requests:
        return ()

    result: list[type[TLRequest]] = []
    seen: set[type[TLRequest]] = set()
    for request in requests:
        if isinstance(request, TLRequest):
            request = type(request)

        if not isinstance(request, type) or not issubclass(request, TLRequest):
            raise TypeError(
                f"{field_name} must contain TLRequest subclasses or instances"
            )

        if request not in seen:
            seen.add(request)
            result.append(request)

    return tuple(result)


@dataclass(frozen=True)
class ProtectionPolicy:
    mode: str
    blocked_requests: tuple[type[TLRequest], ...] = ()
    allowed_requests: tuple[type[TLRequest], ...] = ()
    max_nesting_depth: int = MAX_NESTING_DEPTH
    dry_run: bool = False
    log_blocked: bool = True
    raise_on_blocked: bool = True
    # Custom callback - invoked on every violation before any potential raise
    on_violation: Optional[Callable[["ProtectionViolation"], None]] = field(
        default=None, compare=False, hash=False, repr=False
    )
    # Computed fields - populated in __post_init__ via object.__setattr__
    blocked_request_ids: frozenset[int] = field(init=False, repr=False)
    allowed_request_ids: frozenset[int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.mode not in PROTECTION_MODES:
            raise ValueError(
                f"Unknown protection mode {self.mode!r}. Expected one of: "
                f"{', '.join(sorted(PROTECTION_MODES))}"
            )
        if self.max_nesting_depth <= 0:
            raise ValueError("max_nesting_depth must be greater than zero")

        blocked = _normalize_request_types(self.blocked_requests, "blocked_requests")
        allowed = _normalize_request_types(self.allowed_requests, "allowed_requests")

        object.__setattr__(self, "blocked_requests", blocked)
        object.__setattr__(self, "allowed_requests", allowed)
        object.__setattr__(
            self,
            "blocked_request_ids",
            frozenset(r.CONSTRUCTOR_ID for r in blocked),
        )
        object.__setattr__(
            self,
            "allowed_request_ids",
            frozenset(r.CONSTRUCTOR_ID for r in allowed),
        )

    @property
    def should_block(self) -> bool:
        return self.raise_on_blocked and not self.dry_run


@dataclass(frozen=True)
class ProtectionViolation:
    request: TLRequest
    dangerous_request: TLRequest
    policy: ProtectionPolicy

    @property
    def action(self) -> str:
        if self.policy.dry_run:
            return "would be blocked"
        if self.policy.should_block:
            return "blocked"
        return "detected"

    @property
    def message(self) -> str:
        return (
            f"Method '{type(self.dangerous_request).__name__}' {self.action} "
            f"by protection mode '{self.policy.mode}'!"
        )

    @property
    def log_message(self) -> str:
        if self.policy.dry_run:
            prefix = "Would block"
        elif self.policy.should_block:
            prefix = "Blocked"
        else:
            prefix = "Detected"
        return (
            f"{prefix} dangerous request: {type(self.dangerous_request).__name__} "
            f"(constructor_id=0x{self.dangerous_request.CONSTRUCTOR_ID:08X}, "
            f"mode={self.policy.mode})"
        )


def build_protection_policy(
    mode: str = "strict",
    *,
    blocked_requests=None,
    allowed_requests=None,
    max_nesting_depth: int = MAX_NESTING_DEPTH,
    dry_run: bool = False,
    log_blocked: bool = True,
    raise_on_blocked: bool = True,
    on_violation: Optional[Callable[[ProtectionViolation], None]] = None,
) -> ProtectionPolicy:
    mode = mode.lower()
    if mode == "off":
        default_blocked: tuple[type[TLRequest], ...] = ()
    elif mode == "safe":
        default_blocked = SAFE_DANGEROUS_REQUESTS
    elif mode in {"strict", "custom"}:
        default_blocked = STRICT_DANGEROUS_REQUESTS
    else:
        raise ValueError(
            f"Unknown protection mode {mode!r}. Expected one of: "
            f"{', '.join(sorted(PROTECTION_MODES))}"
        )

    return ProtectionPolicy(
        mode=mode,
        blocked_requests=(
            default_blocked if blocked_requests is None else blocked_requests
        ),
        allowed_requests=() if allowed_requests is None else allowed_requests,
        max_nesting_depth=max_nesting_depth,
        dry_run=dry_run,
        log_blocked=log_blocked,
        raise_on_blocked=raise_on_blocked,
        on_violation=on_violation,
    )


DEFAULT_PROTECTION_POLICY = build_protection_policy("strict")


def find_dangerous_request(
    request: TLRequest,
    *,
    policy: ProtectionPolicy | None = None,
    blocked_request_ids: frozenset[int] | None = None,
    allowed_request_ids: frozenset[int] | None = None,
    max_nesting_depth: int | None = None,
) -> Optional[TLRequest]:
    """
    Find a blacklisted request even when it is wrapped inside ``Invoke*``
    containers (iterative DFS, cycle-safe).
    """
    if not isinstance(request, TLRequest):
        return None

    if policy is not None:
        blocked_request_ids = policy.blocked_request_ids
        allowed_request_ids = policy.allowed_request_ids
        max_nesting_depth = policy.max_nesting_depth

    if blocked_request_ids is None:
        blocked_request_ids = DANGEROUS_REQUEST_IDS
    if allowed_request_ids is None:
        allowed_request_ids = frozenset()
    if max_nesting_depth is None:
        max_nesting_depth = MAX_NESTING_DEPTH

    stack: list[tuple[int, TLRequest]] = [(0, request)]
    seen: set[int] = set()

    while stack:
        depth, current = stack.pop()

        if depth >= max_nesting_depth:
            raise ScamModuleDetected(
                f"Request nesting depth exceeds {max_nesting_depth} - "
                "possible evasion attempt via deeply nested wrappers."
            )

        current_oid = id(current)
        if current_oid in seen:
            continue
        seen.add(current_oid)

        if (
            current.CONSTRUCTOR_ID not in allowed_request_ids
            and current.CONSTRUCTOR_ID in blocked_request_ids
        ):
            return current

        next_depth = depth + 1

        for attr in ("query", "request"):
            value = getattr(current, attr, None)
            if isinstance(value, TLRequest):
                stack.append((next_depth, value))

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


def check_request_safety(
    request: TLRequest,
    policy: ProtectionPolicy | None = None,
) -> Optional[ProtectionViolation]:
    """
    Check *request* against the policy. Returns a ProtectionViolation on a
    hit, or ``None`` if the request is safe.

    Logging and the on_violation callback are fired here - before any raise -
    so they always run regardless of whether assert_safe or this function is
    called directly.
    """
    policy = policy or DEFAULT_PROTECTION_POLICY
    dangerous = find_dangerous_request(request, policy=policy)
    if dangerous is None:
        return None

    violation = ProtectionViolation(
        request=request,
        dangerous_request=dangerous,
        policy=policy,
    )

    # Log before any potential raise so the message is never silently swallowed
    if policy.log_blocked:
        logger.warning(violation.log_message)

    if policy.on_violation is not None:
        try:
            policy.on_violation(violation)
        except Exception:
            logger.exception("on_violation callback raised an exception")

    return violation


def assert_safe(request: TLRequest, policy: ProtectionPolicy | None = None) -> None:
    """
    Raise :class:`ScamModuleDetected` if *request* (or any request nested
    inside it) is on the blocklist, or if the nesting depth exceeds the
    configured limit. No-op for safe requests.
    """
    violation = check_request_safety(request, policy=policy)
    if violation is not None and violation.policy.should_block:
        raise ScamModuleDetected(violation.message)


def protect_client(
    client: "TelegramClient",
    policy: ProtectionPolicy | None = None,
) -> None:
    """
    Patch *client* so that every outgoing Telegram API call is checked
    against *policy* via assert_safe before being sent.

    Uses a per-instance dynamic subclass so other TelegramClient instances
    in the same process are not affected.

    The original ``__call__`` is preserved as ``client._unprotected_call``
    for debugging or explicit bypass.

    Usage::

        client = TelegramClient(...)
        protect_client(client, build_protection_policy("strict"))
    """
    policy = policy or DEFAULT_PROTECTION_POLICY

    if hasattr(client, "_protection_policy"):
        logger.warning(
            "protect_client: client already protected (mode=%s). Updating policy to mode=%s.",
            client._protection_policy.mode,  # type: ignore[attr-defined]
            policy.mode,
        )
        client._protection_policy = policy  # type: ignore[attr-defined]
        return

    original_call = type(client).__call__

    # Per-instance subclass - avoids polluting the base TelegramClient class
    protected_class = type(
        f"Protected{type(client).__name__}",
        (type(client),),
        {},
    )

    async def _protected_call(self, request, ordered=False, flood_sleep_threshold=None):
        assert_safe(request, self._protection_policy)  # type: ignore[attr-defined]
        return await original_call(
            self, request, ordered=ordered, flood_sleep_threshold=flood_sleep_threshold
        )

    protected_class.__call__ = _protected_call  # type: ignore[method-assign]
    client.__class__ = protected_class  # type: ignore[assignment]
    client._protection_policy = policy  # type: ignore[attr-defined]
    client._unprotected_call = original_call  # type: ignore[attr-defined]
