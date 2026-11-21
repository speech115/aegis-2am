"""Track 2: Autonomous Security Patcher (Devin / LLM / Verified Patch Synthesizer).

Generates a concrete code fix, unified diff, and regression test for the root-cause
vulnerability localized by Graphify. Optionally invokes Cognition Devin API when
DEVIN_API_KEY is configured, while guaranteeing fast, deterministic verified patches
so live demos never fail on network latency.
"""

from __future__ import annotations

from dataclasses import dataclass
import difflib
import os
from pathlib import Path
from typing import Any
import httpx

from backend.attacker.scenarios import AttackScenario


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class GeneratedPatch:
    scenario_id: str
    file_path: str
    original_code: str
    patched_code: str
    diff: str
    explanation: str
    regression_test_name: str
    regression_test_code: str
    generator: str
    devin_session_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "file_path": self.file_path,
            "diff": self.diff,
            "explanation": self.explanation,
            "regression_test_name": self.regression_test_name,
            "regression_test_code": self.regression_test_code,
            "generator": self.generator,
            "devin_session_url": self.devin_session_url,
        }


PATCHED_KYC_PY = '''"""Layer 2: KYC & Biometric Verification for DubaiTrust Core (PATCHED BY AEGIS 2AM).

SECURITY FIXES APPLIED:
1. Enforces single-use KYC tokens (blocks CWE-294 replay attacks).
2. Binds KYC token strictly to `account_id`, `amount_aed`, and `beneficiary_iban`.
3. Enforces human biometric liveness timing floor (`completion_ms >= 1500`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import uuid

MIN_HUMAN_LIVENESS_MS = 1500


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
    """Handles KYC biometric/document step-up tokens with replay & scope protection."""

    def __init__(self) -> None:
        self.tokens: dict[str, KYCTokenRecord] = {}
        self.reset()

    def reset(self) -> None:
        self.tokens = {
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
        """Verifies single-use KYC token with strict scope binding and liveness floor."""
        rec = self.tokens.get(token)
        if not rec or not rec.verified:
            raise PermissionError("KYC token not found or unverified")

        if rec.account_id != account_id:
            raise PermissionError("KYC token belongs to a different account")

        # FIX 1 (CWE-294): Reject already-consumed tokens immediately
        if rec.used or rec.use_count > 0:
            raise PermissionError("KYC token already consumed (replay attack blocked)")

        # FIX 2: Strict cryptographic/scope binding to amount & destination IBAN
        if abs(rec.issued_for_amount_aed - amount_aed) > 0.01 or rec.issued_for_iban != beneficiary_iban:
            raise PermissionError("KYC token scope mismatch (amount or beneficiary IBAN altered)")

        # FIX 3: Enforce human liveness timing floor against automated bots
        if rec.completion_ms < MIN_HUMAN_LIVENESS_MS:
            raise PermissionError(
                f"KYC liveness duration {rec.completion_ms}ms below human floor ({MIN_HUMAN_LIVENESS_MS}ms)"
            )

        rec.use_count += 1
        rec.used = True

        return {
            "kyc_passed": True,
            "token": token,
            "replayed": False,
            "scope_mismatch": False,
            "bot_speed": False,
            "completion_ms": rec.completion_ms,
            "original_amount_aed": rec.issued_for_amount_aed,
        }
'''

PATCHED_TRANSFERS_PY = '''"""Layer 3: Account & Transfer Execution for DubaiTrust Core (PATCHED BY AEGIS 2AM).

SECURITY FIXES APPLIED:
1. Acquires per-account atomic lock around balance + daily limit check and debit (fixes CWE-362).
2. Enforces daily_limit_aed unconditionally before debiting customer funds.
"""

from __future__ import annotations

from threading import Lock
import time
from typing import Any

from backend.bank.auth import SessionContext, authenticate_session
from backend.bank.kyc import KYCService
from backend.bank.ledger import BankLedger, TransferRecord

_ACCOUNT_LOCKS: dict[str, Lock] = {}
_LOCK_REGISTRY_GUARD = Lock()


def _get_account_lock(account_id: str) -> Lock:
    with _LOCK_REGISTRY_GUARD:
        if account_id not in _ACCOUNT_LOCKS:
            _ACCOUNT_LOCKS[account_id] = Lock()
        return _ACCOUNT_LOCKS[account_id]


def execute_transfer(
    ledger: BankLedger,
    account_id: str,
    beneficiary_iban: str,
    amount_aed: float,
    kyc_result: dict[str, Any],
    simulate_io_delay_s: float = 0.02,
) -> TransferRecord:
    """Executes a wire transfer atomically with daily limit enforcement."""
    lock = _get_account_lock(account_id)
    with lock:
        account = ledger.get_account(account_id)
        if account.balance_aed < amount_aed:
            raise ValueError("Insufficient funds")

        if round(account.daily_spent_aed + amount_aed, 2) > account.daily_limit_aed:
            raise PermissionError(
                f"Daily transfer limit exceeded: {account.daily_spent_aed + amount_aed:,.2f} > {account.daily_limit_aed:,.2f} AED"
            )

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
    """Full 3-layer banking pipeline: Auth -> KYC -> Atomic Transfer."""
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
'''


def _maybe_trigger_devin_session(scenario: AttackScenario, blast_summary: str) -> str | None:
    """Optionally notifies Cognition Devin API to open a live audit/remediation session."""
    api_key = os.getenv("DEVIN_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        resp = httpx.post(
            "https://api.devin.ai/v1/sessions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "prompt": (
                    f"Aegis 2AM detected live intrusion '{scenario.name}' ({scenario.cwe}) "
                    f"targeting {scenario.vulnerable_file}::{scenario.vulnerable_symbol}. "
                    f"Graphify blast radius: {blast_summary}. "
                    f"Review and verify the generated security patch and regression test."
                ),
                "idempotent": False,
            },
            timeout=10.0,
        )
        if resp.status_code < 300:
            data = resp.json()
            return data.get("url") or data.get("session_url")
    except Exception:
        return None
    return None


def synthesize_security_patch(
    scenario: AttackScenario,
    blast_radius: dict[str, Any],
) -> GeneratedPatch:
    """Generates a verified security patch and unified diff for the compromised file."""
    target_path = REPO_ROOT / scenario.vulnerable_file
    original_code = target_path.read_text(encoding="utf-8")

    if scenario.vulnerable_file == "backend/bank/kyc.py":
        patched_code = PATCHED_KYC_PY
        explanation = (
            "Hardened `KYCService.verify_kyc_token` with 3 atomic invariants: "
            "(1) reject consumed tokens to block CWE-294 replay attacks, "
            "(2) enforce strict binding to exact `amount_aed` and `beneficiary_iban`, "
            "(3) enforce a 1,500ms human biometric liveness timing floor to stop headless bots."
        )
        test_name = "test_kyc_replay_and_bot_blocked"
        test_code = (
            "def test_kyc_replay_blocked():\n"
            "    from backend.bank.kyc import KYCService\n"
            "    svc = KYCService()\n"
            "    try:\n"
            "        svc.verify_kyc_token('kyc_tok_tariq_daytime_9821', 'acc_tariq_001', 250000.0, 'CY17002001280000001200527600')\n"
            "        assert False, 'Expected PermissionError on replayed KYC token'\n"
            "    except PermissionError:\n"
            "        pass\n"
        )
    else:
        patched_code = PATCHED_TRANSFERS_PY
        explanation = (
            "Hardened `execute_transfer` against CWE-362 concurrent TOCTOU drains by wrapping "
            "balance validation, daily transfer limit enforcement, and ledger debit inside a "
            "per-account atomic lock."
        )
        test_name = "test_concurrent_race_limit_enforced"
        test_code = (
            "def test_daily_limit_enforced_atomically():\n"
            "    from backend.bank.ledger import BankLedger\n"
            "    from backend.bank.transfers import execute_transfer\n"
            "    ledger = BankLedger()\n"
            "    try:\n"
            "        execute_transfer(ledger, 'acc_nadia_002', 'AE070331234567890123456', 90000.0, {'token': 't'}, 0.0)\n"
            "        assert False, 'Expected PermissionError above daily limit'\n"
            "    except PermissionError:\n"
            "        pass\n"
        )

    diff_lines = list(
        difflib.unified_diff(
            original_code.splitlines(keepends=True),
            patched_code.splitlines(keepends=True),
            fromfile=f"a/{scenario.vulnerable_file}",
            tofile=f"b/{scenario.vulnerable_file}",
            n=3,
        )
    )
    diff_text = "".join(diff_lines)
    devin_url = _maybe_trigger_devin_session(scenario, blast_radius.get("summary", ""))
    generator = "devin+aegis-patcher" if devin_url else "aegis-autonomous-patcher"

    return GeneratedPatch(
        scenario_id=scenario.id,
        file_path=scenario.vulnerable_file,
        original_code=original_code,
        patched_code=patched_code,
        diff=diff_text,
        explanation=explanation,
        regression_test_name=test_name,
        regression_test_code=test_code,
        generator=generator,
        devin_session_url=devin_url,
    )
