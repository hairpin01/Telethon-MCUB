from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Optional

from telethon.tl import TLRequest
from telethon.tl.functions.account import (
    ChangePhoneRequest,
    DeleteAccountRequest,
    FinishTakeoutSessionRequest,
    GetAuthorizationsRequest,
    GetWebAuthorizationsRequest,
    InitTakeoutSessionRequest,
    ResetAuthorizationRequest,
    ResetPasswordRequest,
    ResetWebAuthorizationsRequest,
    UpdatePasswordSettingsRequest,
)
from telethon.tl.functions.auth import (
    BindTempAuthKeyRequest,
    ImportAuthorizationRequest,
    LogOutRequest,
    ResetAuthorizationsRequest,
)

logger = logging.getLogger(__name__)

MAX_NESTING_DEPTH = 20
PROTECTION_MODES = frozenset({"off", "safe", "strict", "custom"})


class ScamModuleDetected(Exception):
    """Raised when a dangerous or blacklisted Telegram API request is detected."""


SAFE_DANGEROUS_REQUESTS: tuple[type[TLRequest], ...] = (
    DeleteAccountRequest,
    ResetAuthorizationRequest,
    ResetAuthorizationsRequest,
    ResetWebAuthorizationsRequest,
    BindTempAuthKeyRequest,
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
)

# Backward-compatible aliases for callers that relied on the old names.
DANGEROUS_REQUESTS = STRICT_DANGEROUS_REQUESTS
DANGEROUS_REQUEST_IDS = frozenset(r.CONSTRUCTOR_ID for r in DANGEROUS_REQUESTS)


def _normalize_request_types(requests, field_name: str) -> tuple[type[TLRequest], ...]:
    if not requests:
        return ()

    result = []
    seen = set()
    for request in requests:
        if isinstance(request, TLRequest):
            request = type(request)

        if not isinstance(request, type) or not issubclass(request, TLRequest):
            raise TypeError(f"{field_name} must contain TLRequest subclasses or instances")

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
    blocked_request_ids: frozenset[int] = field(init=False, repr=False)
    allowed_request_ids: frozenset[int] = field(init=False, repr=False)

    def __post_init__(self):
        if self.mode not in PROTECTION_MODES:
            raise ValueError(
                f"Unknown protection mode {self.mode!r}. Expected one of: "
                f"{', '.join(sorted(PROTECTION_MODES))}"
            )
        if self.max_nesting_depth <= 0:
            raise ValueError("max_nesting_depth must be greater than zero")

        blocked_requests = _normalize_request_types(self.blocked_requests, "blocked_requests")
        allowed_requests = _normalize_request_types(self.allowed_requests, "allowed_requests")

        object.__setattr__(self, "blocked_requests", blocked_requests)
        object.__setattr__(self, "allowed_requests", allowed_requests)
        object.__setattr__(
            self,
            "blocked_request_ids",
            frozenset(request.CONSTRUCTOR_ID for request in blocked_requests),
        )
        object.__setattr__(
            self,
            "allowed_request_ids",
            frozenset(request.CONSTRUCTOR_ID for request in allowed_requests),
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
) -> ProtectionPolicy:
    mode = mode.lower()
    if mode == "off":
        default_blocked = ()
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
        blocked_requests=default_blocked if blocked_requests is None else blocked_requests,
        allowed_requests=() if allowed_requests is None else allowed_requests,
        max_nesting_depth=max_nesting_depth,
        dry_run=dry_run,
        log_blocked=log_blocked,
        raise_on_blocked=raise_on_blocked,
    )


DEFAULT_PROTECTION_POLICY = build_protection_policy("strict")


def find_dangerous_request(
    request: TLRequest,
    *,
    policy: ProtectionPolicy = None,
    blocked_request_ids: frozenset[int] = None,
    allowed_request_ids: frozenset[int] = None,
    max_nesting_depth: int = None,
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
            elif isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Iterable):
                continue

            for inner in value:
                if isinstance(inner, TLRequest):
                    stack.append((next_depth, inner))

    return None


def check_request_safety(
    request: TLRequest, policy: ProtectionPolicy = None
) -> Optional[ProtectionViolation]:
    policy = policy or DEFAULT_PROTECTION_POLICY
    dangerous = find_dangerous_request(request, policy=policy)
    if dangerous is None:
        return None

    return ProtectionViolation(
        request=request,
        dangerous_request=dangerous,
        policy=policy,
    )


def assert_safe(request: TLRequest, policy: ProtectionPolicy = None) -> None:
    """
    Raise :class:`ScamModuleDetected` if *request* (or any request nested
    inside it) is on the blacklist, or if the nesting depth exceeds the
    configured limit.
    """
    violation = check_request_safety(request, policy=policy)
    if violation is not None and violation.policy.should_block:
        raise ScamModuleDetected(violation.message)
    if violation is not None and violation.policy.log_blocked:
        logger.warning(violation.log_message)
