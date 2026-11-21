"""Track 1: Explainable Question-Bottleneck Risk Engine (<15ms, zero label delay).

Inspired by Question-Bottleneck Scoring (Finic Kairos): every risk decision decomposes
into plain-English auditable questions with calibrated weights and concrete evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from backend.bank.ledger import BankAccount, BankLedger


@dataclass
class RiskQuestionResult:
    id: str
    question: str
    triggered: bool
    weight: float
    contribution: float
    evidence: str


@dataclass
class RiskAssessment:
    risk_score: float
    decision: str  # ALLOW | STEP_UP | ESCROW_AND_HONEYPOT
    latency_ms: float
    questions: list[RiskQuestionResult]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "decision": self.decision,
            "latency_ms": self.latency_ms,
            "summary": self.summary,
            "questions": [vars(q) for q in self.questions],
        }


def evaluate_client_risk(
    *,
    ledger: BankLedger,
    account: BankAccount,
    amount_aed: float,
    beneficiary_iban: str,
    local_hour_dubai: int,
    device_fp: str,
    country: str,
    kyc_result: dict[str, Any],
    concurrent_requests_500ms: int = 1,
) -> RiskAssessment:
    """Evaluates 7 calibrated Question-Bottleneck risk signals in milliseconds."""
    started = time.perf_counter()

    start_h, end_h = account.sleep_window_utc4
    is_sleep_window = start_h <= local_hour_dubai < end_h
    device_mismatch = device_fp != account.trusted_device_fp
    kyc_replayed = bool(kyc_result.get("replayed")) or bool(kyc_result.get("scope_mismatch"))
    bot_kyc = bool(kyc_result.get("bot_speed")) or int(kyc_result.get("completion_ms", 5000)) < 1500
    mule_iban = beneficiary_iban in ledger.blocked_ibans or not beneficiary_iban.startswith("AE")
    amount_spike = amount_aed > (account.p95_transfer_aed * 3.0)
    race_burst = concurrent_requests_500ms >= 3

    checks: list[tuple[str, str, bool, float, str]] = [
        (
            "q_sleep_window",
            "Is this transfer initiated during the customer's 00:00–05:00 Dubai sleep window?",
            is_sleep_window,
            0.14,
            f"Local Dubai time is {local_hour_dubai:02d}:00 (inside dormant sleep window 00:00–05:00)"
            if is_sleep_window
            else f"Local Dubai time is {local_hour_dubai:02d}:00 (active hours)",
        ),
        (
            "q_device_hijack",
            "Does the caller device fingerprint deviate from the customer's trusted hardware?",
            device_mismatch,
            0.20,
            f"Untrusted device '{device_fp}' vs bound '{account.trusted_device_fp}' (country={country})"
            if device_mismatch
            else f"Matched trusted device '{device_fp}'",
        ),
        (
            "q_kyc_replay",
            "Was the KYC verification token replayed or issued for a different amount/IBAN?",
            kyc_replayed,
            0.26,
            f"Token '{kyc_result.get('token')}' was issued for AED {kyc_result.get('original_amount_aed')} and reused for AED {amount_aed:,.2f}"
            if kyc_replayed
            else "Fresh single-use KYC token matched to exact transaction scope",
        ),
        (
            "q_bot_liveness",
            "Was KYC liveness completed faster than humanly possible (<1,500ms)?",
            bot_kyc,
            0.22,
            f"KYC completed in {kyc_result.get('completion_ms')}ms — automated headless bot signature"
            if bot_kyc
            else f"Human liveness duration ({kyc_result.get('completion_ms')}ms)",
        ),
        (
            "q_mule_graph",
            "Is the destination IBAN an unseen offshore or flagged mule-network account?",
            mule_iban,
            0.18,
            f"Destination IBAN {beneficiary_iban} matches offshore/mule threat intelligence cluster"
            if mule_iban
            else f"Domestic UAE beneficiary {beneficiary_iban}",
        ),
        (
            "q_amount_anomaly",
            "Does the transfer exceed 3x the customer's 90-day p95 transfer baseline?",
            amount_spike,
            0.14,
            f"AED {amount_aed:,.2f} is {amount_aed / max(account.p95_transfer_aed, 1):.1f}x customer p95 (AED {account.p95_transfer_aed:,.0f})"
            if amount_spike
            else f"AED {amount_aed:,.2f} within normal customer velocity",
        ),
        (
            "q_race_burst",
            "Are multiple concurrent wire requests hitting the ledger within 500ms?",
            race_burst,
            0.24,
            f"{concurrent_requests_500ms} parallel transfer threads detected inside 500ms window (TOCTOU race pattern)"
            if race_burst
            else "Single sequential request",
        ),
    ]

    results: list[RiskQuestionResult] = []
    raw_score = 0.0
    triggered_labels: list[str] = []
    for qid, question, triggered, weight, evidence in checks:
        contrib = weight if triggered else 0.0
        raw_score += contrib
        if triggered:
            triggered_labels.append(qid)
        results.append(
            RiskQuestionResult(
                id=qid,
                question=question,
                triggered=triggered,
                weight=weight,
                contribution=round(contrib, 3),
                evidence=evidence,
            )
        )

    score = round(min(raw_score, 0.99), 3)
    if score >= 0.50:
        decision = "ESCROW_AND_HONEYPOT"
        summary = (
            f"Critical intrusion blocked ({score:.0%} risk): {len(triggered_labels)} signals triggered. "
            f"Funds locked in protected escrow; attacker diverted to Shadow Honeypot."
        )
    elif score >= 0.25:
        decision = "STEP_UP"
        summary = f"Elevated risk ({score:.0%}): requiring out-of-band biometric confirmation."
    else:
        decision = "ALLOW"
        summary = f"Low risk ({score:.0%}): transaction cleared."

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    return RiskAssessment(
        risk_score=score,
        decision=decision,
        latency_ms=latency_ms,
        questions=results,
        summary=summary,
    )
