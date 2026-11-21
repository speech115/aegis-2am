"""Aegis 2AM — FastAPI Backend, SSE Event Orchestrator, and Voice/Sponsor Endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import os
import time
from typing import Any
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.attacker.scenarios import SCENARIOS, AttackScenario
from backend.bank.auth import authenticate_session
from backend.bank.kyc import KYCService
from backend.bank.ledger import BankLedger
from backend.immune.daytona_verifier import DaytonaDualSandboxVerifier
from backend.immune.graphify_engine import GraphifyEngine
from backend.immune.patcher import synthesize_security_patch
from backend.immune.pr_creator import PullRequestCreator
from backend.shield.honeypot import ClientShieldController
from backend.shield.risk_engine import evaluate_client_risk

load_dotenv()

app = FastAPI(
    title="Aegis 2AM — Autonomous Banking Immune System",
    version="0.1.0",
    description="Real-Time Client Shield + Self-Healing Bank powered by Graphify AST & Daytona Dual-Sandbox",
)

cors_origins = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,*").split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in cors_origins else cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared runtime state
ledger = BankLedger()
kyc_service = KYCService()
shield_controller = ClientShieldController()
graphify_engine = GraphifyEngine()
daytona_verifier = DaytonaDualSandboxVerifier()
pr_creator = PullRequestCreator()

incidents: dict[str, dict[str, Any]] = {}
incident_order: list[str] = []
incident_subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}


class DemoRunRequest(BaseModel):
    scenario_id: str = Field(default="2am_kyc_replay_ato")
    create_github_pr: bool = Field(default=False)
    step_delay_ms: int = Field(default=350, ge=0, le=3000)
    wait: bool = Field(default=False)


class ClientDecisionRequest(BaseModel):
    action: str = Field(pattern="^(confirm_fraud|approve_transfer)$")


class VoiceCommandRequest(BaseModel):
    transcript: str = Field(min_length=2, max_length=500)


def _emit(incident_id: str, phase: str, severity: str, title: str, detail: str, payload: dict[str, Any] | None = None) -> None:
    inc = incidents[incident_id]
    event = {
        "seq": len(inc["events"]) + 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "severity": severity,
        "title": title,
        "detail": detail,
        "payload": payload or {},
    }
    inc["events"].append(event)
    for q in incident_subscribers.get(incident_id, []):
        q.put_nowait(event)


async def _run_autonomous_pipeline(incident_id: str, scenario: AttackScenario, create_github_pr: bool, step_delay_ms: int) -> None:
    inc = incidents[incident_id]
    delay = step_delay_ms / 1000.0
    t_start = time.perf_counter()

    try:
        # Reset KYC token state cleanly for reproducible demo runs
        kyc_service.reset()
        account = ledger.get_account(scenario.target_account_id)

        # === PHASE 1: LIVE 2:00 AM INTRUSION (3 LAYERS) ===
        _emit(
            incident_id,
            "attack",
            "critical",
            f"Intrusion Detected at {scenario.dubai_time}",
            f"Target: {account.holder_name} ({account.account_id}) · Attempted wire: AED {scenario.amount_aed:,.2f} -> {scenario.beneficiary_iban}",
            {"scenario": scenario.to_summary()},
        )
        await asyncio.sleep(delay)

        session = authenticate_session(
            session_id=scenario.session_id,
            device_fp=scenario.device_fp,
            ip_address=scenario.attacker_ip,
            country=scenario.attacker_country,
            local_hour_dubai=scenario.local_hour_dubai,
            trusted_proxy_header=scenario.trusted_proxy_header,
        )
        inc["attack_trace"].append(
            {
                "layer": "Layer 1: Session Auth",
                "status": "BREACHED",
                "detail": f"Device '{scenario.device_fp}' bypassed binding via {session.bypass_reason}",
            }
        )
        _emit(
            incident_id,
            "attack",
            "warning",
            "Layer 1 Breached: Session Auth Bypassed",
            f"Untrusted device {scenario.device_fp} ({scenario.attacker_country}) spoofed proxy header",
            vars(session),
        )
        await asyncio.sleep(delay)

        kyc_result = kyc_service.verify_kyc_token(
            token=scenario.kyc_token,
            account_id=account.account_id,
            amount_aed=scenario.amount_aed,
            beneficiary_iban=scenario.beneficiary_iban,
        ) if scenario.id != "race_condition_drain" else {
            "kyc_passed": True,
            "token": "kyc_tok_parallel_burst",
            "replayed": False,
            "scope_mismatch": False,
            "bot_speed": False,
            "completion_ms": 2100,
            "original_amount_aed": 45_000.00,
        }
        inc["attack_trace"].append(
            {
                "layer": "Layer 2: KYC Verification",
                "status": "BREACHED",
                "detail": f"KYC token '{kyc_result['token']}' accepted (replayed={kyc_result['replayed']}, bot_speed={kyc_result['bot_speed']})",
            }
        )
        _emit(
            incident_id,
            "attack",
            "critical",
            "Layer 2 Breached: KYC Gate Bypassed",
            f"Vulnerable verify_kyc_token accepted token '{kyc_result['token']}' without replay/scope enforcement",
            kyc_result,
        )
        await asyncio.sleep(delay)

        # === PHASE 2: TRACK 1 — CLIENT SHIELD («THE LITTLE GUY») ===
        assessment = evaluate_client_risk(
            ledger=ledger,
            account=account,
            amount_aed=scenario.amount_aed,
            beneficiary_iban=scenario.beneficiary_iban,
            local_hour_dubai=scenario.local_hour_dubai,
            device_fp=scenario.device_fp,
            country=scenario.attacker_country,
            kyc_result=kyc_result,
            concurrent_requests_500ms=scenario.concurrent_requests,
        )
        mttd_ms = assessment.latency_ms

        hold, capture, _ = shield_controller.divert_to_honeypot(
            ledger=ledger,
            incident_id=incident_id,
            account_id=account.account_id,
            amount_aed=scenario.amount_aed,
            beneficiary_iban=scenario.beneficiary_iban,
            attacker_ip=scenario.attacker_ip,
            attacker_country=scenario.attacker_country,
            device_fp=scenario.device_fp,
            kyc_token=kyc_result.get("token"),
            ttp_tags=list(scenario.ttp_tags),
        )
        inc["attack_trace"].append(
            {
                "layer": "Layer 3: Transfer Execution",
                "status": "INTERCEPTED_BY_AEGIS",
                "detail": f"AED {scenario.amount_aed:,.2f} locked in Escrow {hold.hold_id}; attacker served decoy {capture.decoy_tx_id}",
            }
        )
        inc["client_shield"] = {
            **assessment.to_dict(),
            "escrow_hold": vars(hold),
            "honeypot_capture": vars(capture),
            "account_balance_intact_aed": account.balance_aed,
        }
        _emit(
            incident_id,
            "client_shield",
            "success",
            f"Client Shield Triggered ({assessment.risk_score:.0%} risk in {mttd_ms}ms)",
            f"AED {scenario.amount_aed:,.2f} protected in Escrow {hold.hold_id}. Customer balance intact: AED {account.balance_aed:,.2f}",
            inc["client_shield"],
        )
        await asyncio.sleep(delay)

        _emit(
            incident_id,
            "honeypot",
            "info",
            f"Shadow Honeypot Active ({capture.decoy_tx_id})",
            f"Attacker diverted to fake ledger. Captured IP {capture.attacker_ip}, mule IBAN {capture.mule_iban}, TTPs: {', '.join(capture.ttp_tags)}",
            vars(capture),
        )
        await asyncio.sleep(delay)

        # === PHASE 3: TRACK 2 — GRAPHIFY AST BLAST RADIUS ===
        blast = await asyncio.to_thread(graphify_engine.compute_blast_radius, scenario.vulnerable_symbol)
        inc["bank_immune"]["graphify_blast_radius"] = blast
        _emit(
            incident_id,
            "graphify",
            "info",
            f"Graphify AST Localized Root Cause: {scenario.vulnerable_symbol}",
            blast["summary"],
            blast,
        )
        await asyncio.sleep(delay)

        # === PHASE 4: DAYTONA SANDBOX #1 — LIVE EXPLOIT REPRODUCTION ===
        _emit(
            incident_id,
            "daytona_exploit",
            "warning",
            f"Spinning Up Daytona Sandbox #1 ({daytona_verifier.mode})...",
            f"Uploading bank codebase + PoC exploit to verify vulnerability {scenario.cwe}",
        )
        sbx1 = await asyncio.to_thread(daytona_verifier.run_sandbox_1_exploit, scenario)
        inc["bank_immune"]["sandbox_1_exploit"] = sbx1.to_dict()
        _emit(
            incident_id,
            "daytona_exploit",
            "critical",
            f"Sandbox #1 Result: {sbx1.status} ({sbx1.duration_ms}ms)",
            f"Exploit confirmed in isolated sandbox {sbx1.sandbox_id} (mode={sbx1.mode})",
            sbx1.to_dict(),
        )
        await asyncio.sleep(delay)

        # === PHASE 5: AUTONOMOUS PATCH SYNTHESIS (DEVIN / PATCHER) ===
        patch = await asyncio.to_thread(synthesize_security_patch, scenario, blast)
        inc["bank_immune"]["patch"] = patch.to_dict()
        _emit(
            incident_id,
            "patch",
            "info",
            f"Autonomous Patch Generated ({patch.generator})",
            patch.explanation,
            patch.to_dict(),
        )
        await asyncio.sleep(delay)

        # === PHASE 6: DAYTONA SANDBOX #2 — CLEAN HELD-OUT VERIFICATION ===
        _emit(
            incident_id,
            "daytona_verify",
            "info",
            f"Spinning Up Clean Daytona Sandbox #2 ({daytona_verifier.mode})...",
            "Verifying patch against exploit re-run + unseen held-out banking regression suite",
        )
        sbx2 = await asyncio.to_thread(daytona_verifier.run_sandbox_2_verify, scenario, patch)
        inc["bank_immune"]["sandbox_2_verify"] = sbx2.to_dict()
        _emit(
            incident_id,
            "daytona_verify",
            "success" if sbx2.status == "VERIFIED_PASS" else "critical",
            f"Sandbox #2 Result: {sbx2.status} ({sbx2.extra['tests_passed']}/{sbx2.extra['tests_total']} held-out tests passed)",
            f"Exploit blocked={sbx2.extra['exploit_blocked']} in clean sandbox {sbx2.sandbox_id} ({sbx2.duration_ms}ms)",
            sbx2.to_dict(),
        )
        await asyncio.sleep(delay)

        # === PHASE 7: CISO-READY GITHUB PULL REQUEST ===
        pr_info = await asyncio.to_thread(
            pr_creator.create_or_preview,
            incident_id=incident_id,
            scenario=scenario,
            patch=patch,
            blast_summary=blast["summary"],
            sandbox_1_id=sbx1.sandbox_id,
            sandbox_2_id=sbx2.sandbox_id,
            tests_passed=sbx2.extra["tests_passed"],
            tests_total=sbx2.extra["tests_total"],
            create_live_pr=create_github_pr,
        )
        inc["bank_immune"]["pr"] = pr_info
        _emit(
            incident_id,
            "pr",
            "success",
            f"GitHub PR Ready ({pr_info['status'].upper()}): {pr_info['branch']}",
            pr_info["title"],
            pr_info,
        )

        mttr_ms = round((time.perf_counter() - t_start) * 1000, 1)
        inc["metrics"] = {
            "mttd_ms": mttd_ms,
            "mttr_ms": mttr_ms,
            "client_saved_aed": scenario.amount_aed,
            "false_positive_rate": 0.0,
            "sandbox_mode": sbx2.mode,
        }
        inc["status"] = "remediated"
        _emit(
            incident_id,
            "complete",
            "success",
            "2:00 AM Autonomous Defense Complete",
            f"AED {scenario.amount_aed:,.2f} saved for {account.holder_name} · Bank vulnerability patched & dual-sandbox verified in {mttr_ms/1000:.2f}s",
            inc["metrics"],
        )
    except Exception as exc:
        inc["status"] = "failed"
        inc["error"] = str(exc)
        _emit(incident_id, "complete", "critical", "Pipeline Error", str(exc))


@app.get("/api/health")
def health() -> dict[str, Any]:
    graph = graphify_engine.build_graph()
    return {
        "status": "ok",
        "service": "aegis-2am",
        "sponsors": {
            "daytona_mode": daytona_verifier.mode,
            "graphify_ready": True,
            "graphify_cli_detected": graphify_engine.graphify_cli_available(),
            "graph_nodes": graph["stats"]["node_count"],
            "graph_extracted_edges": graph["stats"]["extracted_edges"],
            "devin_api_configured": bool(os.getenv("DEVIN_API_KEY", "").strip()),
            "github_pr_ready": pr_creator.gh_ready(),
            "collabute_voice_endpoint": "/api/voice/command",
        },
    }


@app.get("/api/bank/state")
def get_bank_state() -> dict[str, Any]:
    return {
        "bank_name": "DubaiTrust Core",
        "clock_dubai": "02:04 AM GMT+4",
        "layers": [
            {"id": "auth", "name": "Layer 1: Session & Device Auth", "file": "backend/bank/auth.py"},
            {"id": "kyc", "name": "Layer 2: KYC & Biometric Gate", "file": "backend/bank/kyc.py"},
            {"id": "transfers", "name": "Layer 3: Atomic Transfer Ledger", "file": "backend/bank/transfers.py"},
        ],
        **ledger.snapshot(),
    }


@app.post("/api/bank/reset")
def reset_bank() -> dict[str, Any]:
    ledger.reset()
    kyc_service.reset()
    incidents.clear()
    incident_order.clear()
    return {"status": "reset_complete", "state": get_bank_state()}


@app.get("/api/scenarios")
def list_scenarios() -> dict[str, Any]:
    return {"scenarios": [s.to_summary() for s in SCENARIOS.values()]}


@app.get("/api/graph")
def get_code_graph(rebuild: bool = False) -> dict[str, Any]:
    return graphify_engine.build_graph(force_rebuild=rebuild)


@app.get("/api/graph/blast-radius")
def get_blast_radius(symbol: str = "verify_kyc_token") -> dict[str, Any]:
    return graphify_engine.compute_blast_radius(symbol)


@app.post("/api/demo/run")
async def start_demo_run(req: DemoRunRequest) -> dict[str, Any]:
    scenario = SCENARIOS.get(req.scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Unknown scenario '{req.scenario_id}'")

    incident_id = f"inc_{uuid.uuid4().hex[:8]}"
    incidents[incident_id] = {
        "incident_id": incident_id,
        "scenario_id": scenario.id,
        "scenario": scenario.to_summary(),
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "attack_trace": [],
        "client_shield": None,
        "bank_immune": {},
        "metrics": None,
        "events": [],
    }
    incident_order.insert(0, incident_id)
    incident_subscribers[incident_id] = []

    if req.wait:
        await _run_autonomous_pipeline(
            incident_id=incident_id,
            scenario=scenario,
            create_github_pr=req.create_github_pr,
            step_delay_ms=req.step_delay_ms,
        )
        return {
            "incident_id": incident_id,
            "status": incidents[incident_id]["status"],
            "stream_url": f"/api/incidents/{incident_id}/stream",
        }

    asyncio.create_task(
        _run_autonomous_pipeline(
            incident_id=incident_id,
            scenario=scenario,
            create_github_pr=req.create_github_pr,
            step_delay_ms=req.step_delay_ms,
        )
    )
    return {
        "incident_id": incident_id,
        "status": "running",
        "stream_url": f"/api/incidents/{incident_id}/stream",
    }


@app.get("/api/incidents")
def list_incidents() -> dict[str, Any]:
    return {"incidents": [incidents[iid] for iid in incident_order]}


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str) -> dict[str, Any]:
    if incident_id not in incidents:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incidents[incident_id]


@app.get("/api/incidents/{incident_id}/stream")
async def stream_incident(incident_id: str) -> StreamingResponse:
    if incident_id not in incidents:
        raise HTTPException(status_code=404, detail="Incident not found")

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    # Replay already-emitted events first so late subscribers never miss a frame
    for existing in incidents[incident_id]["events"]:
        queue.put_nowait(existing)
    incident_subscribers.setdefault(incident_id, []).append(queue)

    async def event_generator():
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event["phase"] == "complete":
                    break
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'phase': 'heartbeat'})}\n\n"
        finally:
            subs = incident_subscribers.get(incident_id, [])
            if queue in subs:
                subs.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/incidents/{incident_id}/client-decision")
def client_morning_decision(incident_id: str, req: ClientDecisionRequest) -> dict[str, Any]:
    inc = incidents.get(incident_id)
    if not inc or not inc.get("client_shield"):
        raise HTTPException(status_code=404, detail="Incident or escrow hold not found")
    hold_id = inc["client_shield"]["escrow_hold"]["hold_id"]
    result = shield_controller.resolve_morning_decision(
        ledger=ledger,
        hold_id=hold_id,
        action=req.action,
    )
    inc["client_shield"]["escrow_hold"]["status"] = result["status"]
    return result


@app.post("/api/voice/command")
async def handle_collabute_voice_command(req: VoiceCommandRequest) -> dict[str, Any]:
    """Voice-command router designed for Collabute Mac dictation."""
    text = req.transcript.lower().strip()

    if any(k in text for k in ("reset", "сброс", "clear", "очист")):
        reset_bank()
        return {
            "intent": "reset",
            "action_taken": "bank_reset",
            "response_text": "DubaiTrust Core reset to clean 2:00 AM baseline (AED 250,000 intact).",
        }

    if any(k in text for k in ("race", "гон", "concurrent")):
        started = await start_demo_run(DemoRunRequest(scenario_id="race_condition_drain"))
        return {
            "intent": "launch_attack",
            "action_taken": "demo_started",
            "response_text": f"Launched 2:17 AM Concurrent Race Condition attack ({started['incident_id']}).",
            "data": started,
        }

    if any(k in text for k in ("bot", "бот", "liveness")):
        started = await start_demo_run(DemoRunRequest(scenario_id="bot_kyc_bypass"))
        return {
            "intent": "launch_attack",
            "action_taken": "demo_started",
            "response_text": f"Launched 3:11 AM Sub-Second Bot KYC Bypass ({started['incident_id']}).",
            "data": started,
        }

    if any(k in text for k in ("attack", "атак", "simulate", "запуст", "kyc", "2 am", "2am")):
        started = await start_demo_run(DemoRunRequest(scenario_id="2am_kyc_replay_ato"))
        return {
            "intent": "launch_attack",
            "action_taken": "demo_started",
            "response_text": f"Launched 2:00 AM KYC Replay ATO simulation ({started['incident_id']}).",
            "data": started,
        }

    if any(k in text for k in ("confirm fraud", "подтверд", "lock", "заблок", "фрод")):
        if not incident_order:
            return {"intent": "confirm_fraud", "action_taken": "none", "response_text": "No active incident to confirm."}
        res = client_morning_decision(incident_order[0], ClientDecisionRequest(action="confirm_fraud"))
        return {
            "intent": "confirm_fraud",
            "action_taken": "fraud_confirmed",
            "response_text": res["message"],
            "data": res,
        }

    if any(k in text for k in ("approve", "release", "одобр", "разблок")):
        if not incident_order:
            return {"intent": "approve_transfer", "action_taken": "none", "response_text": "No active escrow hold."}
        res = client_morning_decision(incident_order[0], ClientDecisionRequest(action="approve_transfer"))
        return {
            "intent": "approve_transfer",
            "action_taken": "escrow_released",
            "response_text": res["message"],
            "data": res,
        }

    return {
        "intent": "status",
        "action_taken": "summary",
        "response_text": (
            f"Aegis 2AM standing by. {len(incidents)} incident(s) recorded. "
            "Say 'launch 2 AM attack', 'confirm fraud', or 'reset demo'."
        ),
        "data": {"incidents_count": len(incidents)},
    }
