"""Layer 2: KYC & Biometric Verification for DubaiTrust Core.

INTENTIONAL VULNERABILITIES (for Aegis 2AM demonstration):
1. KYC Token Replay (CWE-294): Verified tokens are never marked consumed (multi-use).
2. Missing Transaction Scope Binding: Token is not bound to `amount_aed` or `beneficiary_iban`,
   so an attacker can replay a small daytime KYC token to authorize a 250,000 AED night wire.
3. Missing Human Liveness Floor: Accepts sub-second automated bot KYC completions (< 1500ms).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import uuid


@dataclass
class KYCTokenRecord:
    token: str
    account_id: str
    verified: bool
    issued_for_amount_aed: float
    issued_for_iban: str
    completion_ms: int
    used: bool = False
    use_count: int = 0


class KYCService:
    """Handles KYC biometric/document step-up tokens."""

    def __init__(self) -> None:
        self.tokens: dict[str, KYCTokenRecord] = {}
        self.reset()

    def reset(self) -> None:
        self.tokens = {
            # Legitimate token issued earlier at 14:22 for a small DEWA utility bill
            "kyc_tok_tariq_daytime_9821": KYCTokenRecord(
                token="kyc_tok_tariq_daytime_9821",
                account_id="acc_tariq_001",
                verified=True,
                issued_for_amount_aed=420.00,
                issued_for_iban="AE880260001011234567890",
                completion_ms=4_800,
                used=True,
                use_count=1,
            ),
            # Automated bot-generated liveness token completed in 380ms
            "kyc_tok_bot_fast_4410": KYCTokenRecord(
                token="kyc_tok_bot_fast_4410",
                account_id="acc_dmitry_003",
                verified=True,
                issued_for_amount_aed=95_000.00,
                issued_for_iban="GE29NB0000000101904917",
                completion_ms=380,
                used=False,
                use_count=0,
            ),
        }

    def issue_kyc_token(
        self,
        account_id: str,
        amount_aed: float,
        beneficiary_iban: str,
        completion_ms: int = 3_500,
    ) -> KYCTokenRecord:
        token = f"kyc_tok_{uuid.uuid4().hex[:10]}"
        rec = KYCTokenRecord(
            token=token,
            account_id=account_id,
            verified=True,
            issued_for_amount_aed=amount_aed,
            issued_for_iban=beneficiary_iban,
            completion_ms=completion_ms,
            used=False,
            use_count=0,
        )
        self.tokens[token] = rec
        return rec

    def verify_kyc_token(
        self,
        token: str,
        account_id: str,
        amount_aed: float,
        beneficiary_iban: str,
    ) -> dict[str, Any]:
        """Verifies a KYC token before authorizing a high-value transfer."""
        rec = self.tokens.get(token)
        if not rec or not rec.verified:
            raise PermissionError("KYC token not found or unverified")

        if rec.account_id != account_id:
            raise PermissionError("KYC token belongs to a different account")

        # VULNERABILITY: Does NOT reject already-used tokens (replay bypass),
        # does NOT verify issued_for_amount_aed / issued_for_iban binding,
        # and does NOT reject sub-human bot completion_ms < 1500!
        replayed = rec.used or rec.use_count > 0
        scope_mismatch = (
            abs(rec.issued_for_amount_aed - amount_aed) > 0.01
            or rec.issued_for_iban != beneficiary_iban
        )
        bot_speed = rec.completion_ms < 1500

        rec.use_count += 1
        rec.used = True

        return {
            "kyc_passed": True,
            "token": token,
            "replayed": replayed,
            "scope_mismatch": scope_mismatch,
            "bot_speed": bot_speed,
            "completion_ms": rec.completion_ms,
            "original_amount_aed": rec.issued_for_amount_aed,
        }
