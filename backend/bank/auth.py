"""Layer 1: Session & Device Authentication for DubaiTrust Core.

INTENTIONAL VULNERABILITY (for Aegis 2AM demonstration):
`authenticate_session` skips device fingerprint binding when `trusted_proxy_header`
is present, enabling 2:00 AM session hijack / account takeover from an untrusted device.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SessionContext:
    session_id: str
    account_id: str
    device_fp: str
    ip_address: str
    country: str
    local_hour_dubai: int
    device_matched: bool
    bypass_reason: str | None = None


ACTIVE_SESSIONS: dict[str, dict[str, Any]] = {
    "sess_tariq_live": {
        "account_id": "acc_tariq_001",
        "bound_device_fp": "fp_iphone16_tariq_dubai",
        "owner_country": "AE",
    },
    "sess_nadia_live": {
        "account_id": "acc_nadia_002",
        "bound_device_fp": "fp_macbook_nadia_difc",
        "owner_country": "AE",
    },
    "sess_dmitry_live": {
        "account_id": "acc_dmitry_003",
        "bound_device_fp": "fp_pixel9_dmitry_marina",
        "owner_country": "AE",
    },
}


def authenticate_session(
    session_id: str,
    device_fp: str,
    ip_address: str,
    country: str = "AE",
    local_hour_dubai: int = 14,
    trusted_proxy_header: str | None = None,
) -> SessionContext:
    """Validates caller session against bound device fingerprint."""
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        raise PermissionError("Invalid or expired session token")

    bound_fp = session["bound_device_fp"]
    device_matched = device_fp == bound_fp

    # VULNERABILITY (CWE-287): Trusts caller-supplied proxy header to bypass device binding!
    if not device_matched and trusted_proxy_header:
        return SessionContext(
            session_id=session_id,
            account_id=session["account_id"],
            device_fp=device_fp,
            ip_address=ip_address,
            country=country,
            local_hour_dubai=local_hour_dubai,
            device_matched=False,
            bypass_reason="trusted_proxy_header_accepted_without_mtls",
        )

    if not device_matched:
        raise PermissionError("Device fingerprint mismatch")

    return SessionContext(
        session_id=session_id,
        account_id=session["account_id"],
        device_fp=device_fp,
        ip_address=ip_address,
        country=country,
        local_hour_dubai=local_hour_dubai,
        device_matched=True,
    )
