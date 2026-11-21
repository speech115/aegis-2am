"""Layer 3: Account & Transfer Execution for DubaiTrust Core.

INTENTIONAL VULNERABILITIES (for Aegis 2AM demonstration):
1. TOCTOU Race Condition (CWE-362): `execute_transfer` validates daily limit and balance
   before an async/sleep window without acquiring a per-account lock, allowing concurrent
   requests to exceed daily limits and drain funds.
2. Blindly trusts Layer 1 & Layer 2 outputs even when bypassed.
"""

from __future__ import annotations

import time
from typing import Any

from backend.bank.auth import SessionContext, authenticate_session
from backend.bank.kyc import KYCService
from backend.bank.ledger import BankLedger, TransferRecord


def execute_transfer(
    ledger: BankLedger,
    account_id: str,
    beneficiary_iban: str,
    amount_aed: float,
    kyc_result: dict[str, Any],
    simulate_io_delay_s: float = 0.02,
) -> TransferRecord:
    """Executes a wire transfer after KYC verification."""
    account = ledger.get_account(account_id)

    # VULNERABILITY (CWE-362): Check-then-act without atomic per-account lock!
    # Also skips daily_limit enforcement when kyc_passed=True (flawed VIP override).
    if account.balance_aed < amount_aed:
        raise ValueError("Insufficient funds")

    if simulate_io_delay_s > 0:
        time.sleep(simulate_io_delay_s)

    return ledger.debit(
        account_id=account_id,
        beneficiary_iban=beneficiary_iban,
        amount_aed=amount_aed,
        metadata={"kyc_token": kyc_result.get("token")},
    )


def process_wire_request(
    ledger: BankLedger,
    kyc_service: KYCService,
    *,
    session_id: str,
    device_fp: str,
    ip_address: str,
    country: str,
    local_hour_dubai: int,
    kyc_token: str,
    beneficiary_iban: str,
    amount_aed: float,
    trusted_proxy_header: str | None = None,
    simulate_io_delay_s: float = 0.02,
) -> dict[str, Any]:
    """Full 3-layer vulnerable banking pipeline: Auth -> KYC -> Transfer."""
    session: SessionContext = authenticate_session(
        session_id=session_id,
        device_fp=device_fp,
        ip_address=ip_address,
        country=country,
        local_hour_dubai=local_hour_dubai,
        trusted_proxy_header=trusted_proxy_header,
    )

    kyc_result = kyc_service.verify_kyc_token(
        token=kyc_token,
        account_id=session.account_id,
        amount_aed=amount_aed,
        beneficiary_iban=beneficiary_iban,
    )

    tx = execute_transfer(
        ledger=ledger,
        account_id=session.account_id,
        beneficiary_iban=beneficiary_iban,
        amount_aed=amount_aed,
        kyc_result=kyc_result,
        simulate_io_delay_s=simulate_io_delay_s,
    )

    return {
        "session": vars(session),
        "kyc": kyc_result,
        "transfer": vars(tx),
    }
