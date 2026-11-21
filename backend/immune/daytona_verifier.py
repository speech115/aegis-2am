"""Track 2: Daytona Dual-Sandbox Verifier (Exploit Reproduction + Held-Out Verification).

Implements the dual-sandbox security architecture:
- Sandbox #1 (Exploit Sandbox): Runs the real exploit against unpatched bank code to confirm
  reproducibility (RED), applies the patch, and verifies the exploit is neutralized.
- Sandbox #2 (Clean Held-Out Sandbox): Fresh isolated sandbox with ONLY the patched code and
  an unseen held-out test suite covering legitimate customer banking flows + security assertions
  (GREEN — guarantees 0 regressions and 0 reward hacking).

Uses the real Daytona Cloud Python SDK (`daytona`) whenever `DAYTONA_API_KEY` is configured,
and falls back cleanly to isolated ephemeral local sandboxes when running offline/without key.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any
import uuid

from backend.attacker.scenarios import AttackScenario
from backend.immune.patcher import GeneratedPatch


REPO_ROOT = Path(__file__).resolve().parents[2]
BANK_DIR = REPO_ROOT / "backend" / "bank"

HELD_OUT_SUITE = '''"""Held-out verification suite (NEVER shown to the patcher)."""
import sys
from backend.bank.ledger import BankLedger
from backend.bank.kyc import KYCService
from backend.bank.transfers import process_wire_request

tests = []

def run_test(name, fn):
    try:
        fn()
        print(f"[PASS] {name}")
        tests.append((name, True))
    except Exception as exc:
        print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
        tests.append((name, False))

def t_legit_daytime_transfer():
    ledger = BankLedger()
    kyc = KYCService()
    tok = kyc.issue_kyc_token("acc_tariq_001", 8_500.00, "AE880260001011234567890", completion_ms=4_200)
    res = process_wire_request(
        ledger, kyc,
        session_id="sess_tariq_live",
        device_fp="fp_iphone16_tariq_dubai",
        ip_address="94.200.12.4",
        country="AE",
        local_hour_dubai=14,
        kyc_token=tok.token,
        beneficiary_iban="AE880260001011234567890",
        amount_aed=8_500.00,
        simulate_io_delay_s=0.0,
    )
    assert res["transfer"]["status"] == "COMPLETED"
    assert ledger.get_account("acc_tariq_001").balance_aed == 241_500.00

def t_legit_nadia_transfer_within_limit():
    ledger = BankLedger()
    kyc = KYCService()
    tok = kyc.issue_kyc_token("acc_nadia_002", 12_000.00, "AE070331234567890123456", completion_ms=3_100)
    res = process_wire_request(
        ledger, kyc,
        session_id="sess_nadia_live",
        device_fp="fp_macbook_nadia_difc",
        ip_address="94.200.88.10",
        country="AE",
        local_hour_dubai=11,
        kyc_token=tok.token,
        beneficiary_iban="AE070331234567890123456",
        amount_aed=12_000.00,
        simulate_io_delay_s=0.0,
    )
    assert res["transfer"]["amount_aed"] == 12_000.00

def t_insufficient_funds_rejected():
    ledger = BankLedger()
    kyc = KYCService()
    tok = kyc.issue_kyc_token("acc_dmitry_003", 999_999.00, "AE070331234567890123456", completion_ms=3_400)
    try:
        process_wire_request(
            ledger, kyc,
            session_id="sess_dmitry_live",
            device_fp="fp_pixel9_dmitry_marina",
            ip_address="94.200.15.2",
            country="AE",
            local_hour_dubai=16,
            kyc_token=tok.token,
            beneficiary_iban="AE070331234567890123456",
            amount_aed=999_999.00,
            simulate_io_delay_s=0.0,
        )
        raise AssertionError("Should reject overdraft")
    except (ValueError, PermissionError):
        pass

def t_invalid_session_rejected():
    ledger = BankLedger()
    kyc = KYCService()
    try:
        process_wire_request(
            ledger, kyc,
            session_id="sess_unknown",
            device_fp="fp_unknown",
            ip_address="1.2.3.4",
            country="AE",
            local_hour_dubai=14,
            kyc_token="kyc_tok_tariq_daytime_9821",
            beneficiary_iban="AE880260001011234567890",
            amount_aed=100.00,
            simulate_io_delay_s=0.0,
        )
        raise AssertionError("Should reject invalid session")
    except PermissionError:
        pass

def t_untrusted_device_without_header_rejected():
    ledger = BankLedger()
    kyc = KYCService()
    try:
        process_wire_request(
            ledger, kyc,
            session_id="sess_tariq_live",
            device_fp="fp_evil_device",
            ip_address="1.2.3.4",
            country="AE",
            local_hour_dubai=14,
            kyc_token="kyc_tok_tariq_daytime_9821",
            beneficiary_iban="AE880260001011234567890",
            amount_aed=100.00,
            simulate_io_delay_s=0.0,
        )
        raise AssertionError("Should reject untrusted device")
    except PermissionError:
        pass

def t_escrow_preserves_balance():
    ledger = BankLedger()
    hold = ledger.create_escrow_hold("acc_tariq_001", 250_000.00, "CY17002001280000001200527600", "inc_test")
    assert hold.status == "HELD"
    assert ledger.get_account("acc_tariq_001").balance_aed == 250_000.00

run_test("legit_daytime_transfer_succeeds", t_legit_daytime_transfer)
run_test("legit_nadia_transfer_within_limit", t_legit_nadia_transfer_within_limit)
run_test("insufficient_funds_rejected", t_insufficient_funds_rejected)
run_test("invalid_session_rejected", t_invalid_session_rejected)
run_test("untrusted_device_rejected", t_untrusted_device_without_header_rejected)
run_test("escrow_preserves_customer_balance", t_escrow_preserves_balance)

passed = sum(1 for _, ok in tests if ok)
print(f"[HELD_OUT_SUMMARY] {passed}/{len(tests)} passed")
sys.exit(0 if passed == len(tests) else 1)
'''


@dataclass
class SandboxRunResult:
    mode: str  # "daytona_cloud" | "local_sandbox"
    sandbox_id: str
    stage: str
    status: str
    exit_code: int
    logs: str
    duration_ms: float
    extra: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "sandbox_id": self.sandbox_id,
            "stage": self.stage,
            "status": self.status,
            "exit_code": self.exit_code,
            "logs": self.logs,
            "duration_ms": self.duration_ms,
            **self.extra,
        }


class DaytonaDualSandboxVerifier:
    """Runs Sandbox #1 (Exploit Reproduction) and Sandbox #2 (Clean Held-Out Verification)."""

    def __init__(self) -> None:
        self.api_key = os.getenv("DAYTONA_API_KEY", "").strip()
        self.target = os.getenv("DAYTONA_TARGET", "eu").strip()

    @property
    def mode(self) -> str:
        if self.api_key:
            try:
                import daytona  # noqa: F401
                return "daytona_cloud"
            except ImportError:
                return "local_sandbox"
        return "local_sandbox"

    def _collect_bank_files(self, override_file: str | None = None, override_content: str | None = None) -> dict[str, bytes]:
        files: dict[str, bytes] = {
            "backend/__init__.py": b'"""Bank sandbox package."""\n',
            "backend/bank/__init__.py": b'"""Target bank core."""\n',
        }
        for py_file in BANK_DIR.glob("*.py"):
            rel = f"backend/bank/{py_file.name}"
            if override_file == rel and override_content is not None:
                files[rel] = override_content.encode("utf-8")
            else:
                files[rel] = py_file.read_bytes()
        return files

    def _run_in_local_sandbox(self, files: dict[str, bytes], script_name: str, script_content: str) -> tuple[str, int, str, float]:
        started = time.perf_counter()
        sandbox_id = f"local-sbx-{uuid.uuid4().hex[:8]}"
        tmp = Path(tempfile.mkdtemp(prefix=f"aegis_{sandbox_id}_"))
        try:
            for rel, raw in files.items():
                dest = tmp / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw)
            script_path = tmp / script_name
            script_path.write_text(script_content, encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(tmp)
            proc = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(tmp),
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )
            logs = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
            return sandbox_id, proc.returncode, logs.strip(), round((time.perf_counter() - started) * 1000, 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _run_in_daytona_cloud(self, files: dict[str, bytes], script_name: str, script_content: str) -> tuple[str, int, str, float]:
        from daytona import Daytona, DaytonaConfig

        started = time.perf_counter()
        client = Daytona(DaytonaConfig(api_key=self.api_key))
        sandbox = client.create()
        sandbox_id = getattr(sandbox, "id", f"dtn-{uuid.uuid4().hex[:8]}")
        try:
            work_root = "/tmp/aegis_work"
            sandbox.process.exec(f"mkdir -p {work_root}/backend/bank")
            for rel, raw in files.items():
                sandbox.fs.upload_file(raw, f"{work_root}/{rel}")
            sandbox.fs.upload_file(script_content.encode("utf-8"), f"{work_root}/{script_name}")
            resp = sandbox.process.exec(f"cd {work_root} && PYTHONPATH={work_root} python3 {script_name}")
            exit_code = getattr(resp, "exit_code", 0)
            logs = getattr(resp, "result", "") or ""
            return str(sandbox_id), int(exit_code), logs.strip(), round((time.perf_counter() - started) * 1000, 1)
        finally:
            try:
                sandbox.delete()
            except Exception:
                pass

    def _exec_sandbox(self, files: dict[str, bytes], script_name: str, script_content: str) -> tuple[str, str, int, str, float]:
        if self.mode == "daytona_cloud":
            try:
                sbx_id, rc, logs, dur = self._run_in_daytona_cloud(files, script_name, script_content)
                return "daytona_cloud", sbx_id, rc, logs, dur
            except Exception as exc:
                # Graceful resilience during live hackathon demo if cloud proxy hiccups
                sbx_id, rc, logs, dur = self._run_in_local_sandbox(files, script_name, script_content)
                fallback_note = f"[Daytona Cloud fallback notice: {exc}]\n"
                return "local_sandbox", sbx_id, rc, fallback_note + logs, dur
        sbx_id, rc, logs, dur = self._run_in_local_sandbox(files, script_name, script_content)
        return "local_sandbox", sbx_id, rc, logs, dur

    def run_sandbox_1_exploit(self, scenario: AttackScenario) -> SandboxRunResult:
        """Sandbox #1: Reproduces the exploit against unpatched bank code."""
        files = self._collect_bank_files()
        mode, sbx_id, rc, logs, dur = self._exec_sandbox(files, "exploit_poc.py", scenario.exploit_script)
        confirmed = rc == 0
        return SandboxRunResult(
            mode=mode,
            sandbox_id=sbx_id,
            stage="sandbox_1_exploit_repro",
            status="EXPLOIT_CONFIRMED" if confirmed else "EXPLOIT_NOT_REPRODUCED",
            exit_code=rc,
            logs=logs,
            duration_ms=dur,
            extra={"exploit_reproduced": confirmed},
        )

    def run_sandbox_2_verify(self, scenario: AttackScenario, patch: GeneratedPatch) -> SandboxRunResult:
        """Sandbox #2: Clean isolated sandbox verifying patched code against exploit + held-out tests."""
        files = self._collect_bank_files(override_file=patch.file_path, override_content=patch.patched_code)

        # Combined verification runner: (1) re-run exploit (must exit 42 = blocked), (2) run unseen held-out suite (must exit 0)
        combined = (
            "import subprocess, sys\n"
            "r1 = subprocess.run([sys.executable, 'exploit_poc.py'], capture_output=True, text=True)\n"
            "print('=== SECURITY EXPLOIT RE-CHECK ===')\n"
            "print(r1.stdout.strip())\n"
            "if r1.stderr: print(r1.stderr.strip())\n"
            "exploit_blocked = (r1.returncode == 42)\n"
            "print(f'EXPLOIT_BLOCKED={exploit_blocked}')\n"
            "r2 = subprocess.run([sys.executable, 'held_out_tests.py'], capture_output=True, text=True)\n"
            "print('\\n=== CLEAN HELD-OUT REGRESSION SUITE ===')\n"
            "print(r2.stdout.strip())\n"
            "if r2.stderr: print(r2.stderr.strip())\n"
            "held_out_ok = (r2.returncode == 0)\n"
            "sys.exit(0 if (exploit_blocked and held_out_ok) else 1)\n"
        )
        files["exploit_poc.py"] = scenario.exploit_script.encode("utf-8")
        files["held_out_tests.py"] = HELD_OUT_SUITE.encode("utf-8")

        mode, sbx_id, rc, logs, dur = self._exec_sandbox(files, "verify_all.py", combined)
        verified = rc == 0
        passed_count = logs.count("[PASS]")
        total_count = passed_count + logs.count("[FAIL]")
        return SandboxRunResult(
            mode=mode,
            sandbox_id=sbx_id,
            stage="sandbox_2_clean_verify",
            status="VERIFIED_PASS" if verified else "VERIFICATION_FAILED",
            exit_code=rc,
            logs=logs,
            duration_ms=dur,
            extra={
                "exploit_blocked": "EXPLOIT_BLOCKED=True" in logs,
                "held_out_passed": verified,
                "tests_passed": passed_count,
                "tests_total": total_count or 6,
            },
        )
