"""End-to-end tests for Aegis 2AM (Client Shield + Graphify AST + Dual-Sandbox Immune Loop)."""

from __future__ import annotations

import asyncio
import pytest

from backend.attacker.scenarios import SCENARIOS
from backend.bank.kyc import KYCService
from backend.bank.ledger import BankLedger
from backend.immune.daytona_verifier import DaytonaDualSandboxVerifier
from backend.immune.graphify_engine import GraphifyEngine
from backend.immune.patcher import synthesize_security_patch
from backend.shield.honeypot import ClientShieldController
from backend.shield.risk_engine import evaluate_client_risk


def test_graphify_builds_deterministic_ast_and_blast_radius() -> None:
    engine = GraphifyEngine()
    graph = engine.build_graph(force_rebuild=True)
    assert graph["stats"]["node_count"] >= 10
    assert graph["stats"]["extracted_edges"] >= 10

    blast = engine.compute_blast_radius("verify_kyc_token")
    assert blast["root_symbol"] == "verify_kyc_token"
    assert blast["root_file"] == "backend/bank/kyc.py"
    assert "backend/bank/transfers.py" in blast["affected_files"]
    assert blast["confidence"] == "EXTRACTED"


def test_client_shield_blocks_2am_kyc_replay_and_preserves_funds() -> None:
    ledger = BankLedger()
    kyc = KYCService()
    account = ledger.get_account("acc_tariq_001")
    kyc_res = kyc.verify_kyc_token(
        "kyc_tok_tariq_daytime_9821",
        "acc_tariq_001",
        250_000.00,
        "CY17002001280000001200527600",
    )
    assert kyc_res["replayed"] is True

    risk = evaluate_client_risk(
        ledger=ledger,
        account=account,
        amount_aed=250_000.00,
        beneficiary_iban="CY17002001280000001200527600",
        local_hour_dubai=2,
        device_fp="fp_kali_tor_exit_09",
        country="NL",
        kyc_result=kyc_res,
    )
    assert risk.decision == "ESCROW_AND_HONEYPOT"
    assert risk.risk_score >= 0.85

    shield = ClientShieldController()
    hold, capture, _ = shield.divert_to_honeypot(
        ledger=ledger,
        incident_id="inc_unit_1",
        account_id="acc_tariq_001",
        amount_aed=250_000.00,
        beneficiary_iban="CY17002001280000001200527600",
        attacker_ip="185.220.101.47",
        attacker_country="NL",
        device_fp="fp_kali_tor_exit_09",
        kyc_token="kyc_tok_tariq_daytime_9821",
        ttp_tags=["KYC-TOKEN-REPLAY"],
    )
    # Customer's real balance is 100% intact!
    assert ledger.get_account("acc_tariq_001").balance_aed == 250_000.00
    assert hold.status == "HELD"
    assert capture.decoy_tx_id.startswith("SHADOW-TX-")


@pytest.mark.parametrize("scenario_id", list(SCENARIOS.keys()))
def test_dual_sandbox_reproduces_and_verifies_patch_for_all_scenarios(scenario_id: str) -> None:
    scenario = SCENARIOS[scenario_id]
    engine = GraphifyEngine()
    blast = engine.compute_blast_radius(scenario.vulnerable_symbol)

    verifier = DaytonaDualSandboxVerifier()
    # Sandbox #1: Unpatched bank MUST be exploitable
    sbx1 = verifier.run_sandbox_1_exploit(scenario)
    assert sbx1.status == "EXPLOIT_CONFIRMED", sbx1.logs

    # Synthesize security patch
    patch = synthesize_security_patch(scenario, blast)
    assert "--- a/" in patch.diff and "+++ b/" in patch.diff

    # Sandbox #2: Patched bank MUST block exploit AND pass 6/6 held-out legitimate banking tests
    sbx2 = verifier.run_sandbox_2_verify(scenario, patch)
    assert sbx2.status == "VERIFIED_PASS", sbx2.logs
    assert sbx2.extra["exploit_blocked"] is True
    assert sbx2.extra["tests_passed"] == 6


def test_fastapi_full_demo_pipeline() -> None:
    from fastapi.testclient import TestClient
    from backend.api.app import app

    with TestClient(app) as client:
        r_health = client.get("/api/health")
        assert r_health.status_code == 200
        assert r_health.json()["sponsors"]["graphify_ready"] is True

        r_run = client.post(
            "/api/demo/run",
            json={"scenario_id": "2am_kyc_replay_ato", "step_delay_ms": 0, "wait": True},
        )
        assert r_run.status_code == 200
        inc_id = r_run.json()["incident_id"]

        inc = client.get(f"/api/incidents/{inc_id}").json()
        assert inc["status"] == "remediated", inc
        assert inc["client_shield"]["decision"] == "ESCROW_AND_HONEYPOT"
        assert inc["bank_immune"]["sandbox_1_exploit"]["status"] == "EXPLOIT_CONFIRMED"
        assert inc["bank_immune"]["sandbox_2_verify"]["status"] == "VERIFIED_PASS"
        assert inc["metrics"]["client_saved_aed"] == 250_000.00

        # Test Collabute voice confirmation endpoint
        r_voice = client.post("/api/voice/command", json={"transcript": "confirm fraud and lock mule"})
        assert r_voice.status_code == 200
        assert r_voice.json()["action_taken"] == "fraud_confirmed"
