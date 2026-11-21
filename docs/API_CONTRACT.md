# Aegis 2AM — API & Event Contract (for Frontend / War Room UI)

> **Backend base URL (local):** `http://localhost:8000`
> **Interactive OpenAPI docs:** `http://localhost:8000/docs`

This contract lets **UI (Frontend)** and **Backend** work 100% in parallel without blocking each other.

---

## 1. Core REST Endpoints

### Health & System Capabilities
- `GET /api/health`
  Returns backend status + which sponsor integrations are active (`daytona_mode`: `"daytona_cloud" | "local_sandbox"`, `graphify_ready`: `bool`, `devin_ready`: `bool`, `github_pr_ready`: `bool`).

### Target Bank State («DubaiTrust Core» — 3 Layers)
- `GET /api/bank/state`
  Returns current accounts (e.g. `acc_tariq_001` with `AED 250,000.00`), active escrow holds, honeypot decoy transfers, security layers status (`auth`, `kyc`, `transfers`), and patch state (`vulnerable` vs `patched`).
- `POST /api/bank/reset`
  Resets all accounts, escrow holds, honeypot captures, and incidents back to initial 2:00 AM demo state (clean reset between demo runs!).

### Graphify Code Knowledge Graph
- `GET /api/graph`
  Returns the AST knowledge graph built from `backend/bank/` (`nodes[]`, `edges[]` with `confidence: "EXTRACTED" | "INFERRED"`, `file`, `line`, `layer: "auth" | "kyc" | "transfers" | "ledger"`).
- `GET /api/graph/blast-radius?symbol=verify_kyc_token`
  Returns highlighted subgraph of compromised symbol + downstream callers/callees + affected account flows.

### Attack & Full Autonomous Defense Demo (One-Click!)
- `GET /api/scenarios`
  Lists the 3 built-in 2:00 AM attack scenarios:
  1. `2am_kyc_replay_ato` — **2:00 AM KYC Token Replay + Account Takeover** (AED 250,000 drain attempt)
  2. `race_condition_drain` — **Concurrent Transfer Race Condition** (4x parallel AED 45,000 bypass)
  3. `bot_kyc_bypass` — **Automated Sub-Second KYC Liveness Bypass** (0.4s bot + new mule IBAN)
- `POST /api/demo/run`
  Body:
  ```json
  {
    "scenario_id": "2am_kyc_replay_ato",
    "create_github_pr": false,
    "step_delay_ms": 450
  }
  ```
  Starts the full autonomous end-to-end pipeline asynchronously and returns `{ "incident_id": "inc_...", "status": "running" }`.
  Subscribe to `GET /api/incidents/{incident_id}/stream` (SSE) or poll `GET /api/incidents/{incident_id}` for live updates!

### Incidents & Client / CISO Actions
- `GET /api/incidents` — list all incidents (newest first).
- `GET /api/incidents/{incident_id}` — full incident object:
  - `attack_trace`: step-by-step penetration through Layer 1 (Auth) → Layer 2 (KYC) → Layer 3 (Transfer)
  - `client_shield`:
    - `risk_score` (`0.0`–`1.0`), `decision` (`"ESCROW_AND_HONEYPOT"` | `"STEP_UP"` | `"ALLOW"`)
    - `questions[]`: explainable Question-Bottleneck factors (`{ id, question, triggered, weight, evidence }`)
    - `escrow_hold`: `{ hold_id, amount_aed, account_id, status }`
    - `honeypot_capture`: `{ decoy_tx_id, attacker_ip, device_fp, mule_iban, ttp_tags[], captured_payload }`
  - `bank_immune`:
    - `graphify_blast_radius`: `{ root_symbol, affected_nodes[], affected_edges[], summary }`
    - `sandbox_1_exploit`: `{ mode, sandbox_id, status: "EXPLOIT_CONFIRMED", logs, duration_ms }`
    - `patch`: `{ file_path, diff, explanation, regression_test, generator }`
    - `sandbox_2_verify`: `{ mode, sandbox_id, status: "VERIFIED_PASS", exploit_blocked: true, held_out_passed: true, tests_passed, tests_total, logs, duration_ms }`
    - `pr`: `{ url, branch, title, status: "created" | "preview" }`
  - `metrics`: `{ mttd_ms, client_saved_aed, mttr_ms, false_positive_rate }`
- `POST /api/incidents/{incident_id}/client-decision`
  Body: `{ "action": "confirm_fraud" | "approve_transfer" }` — lets sleeping user in the morning confirm fraud (permanently blocks mule IBAN + rotates credentials) or release escrow.
- `POST /api/voice/command` *(Collabute Voice AI integration!)*
  Body: `{ "transcript": "Simulate 2 AM KYC attack" }` (or `"confirm fraud"`, `"reset demo"`, `"create pull request"`).
  Parses dictated voice text from Collabute and executes the matching action, returning `{ "intent", "action_taken", "response_text", "data" }`.

---

## 2. Live SSE Event Stream (`GET /api/incidents/{incident_id}/stream`)

Each SSE `data:` frame is a JSON object:
```json
{
  "seq": 1,
  "timestamp": "2026-11-21T02:00:01.142Z",
  "phase": "attack" | "client_shield" | "honeypot" | "graphify" | "daytona_exploit" | "patch" | "daytona_verify" | "pr" | "complete",
  "severity": "info" | "warning" | "critical" | "success",
  "title": "Layer 2 Breached: KYC Token Replayed",
  "detail": "Attacker reused verified KYC token kyc_tok_9821 from 14:22 small check",
  "payload": {}
}
```

---

## 3. Recommended War Room Layout (3 Columns on 1 Screen)

1. **Top Bar:** Clock (`02:00 AM DUBAI`), Scenario Selector + big red **`Launch 2:00 AM Attack`** button, **`Reset`** button, **Collabute Voice Command input** (click & dictate with Collabute!), and Sponsor Stack live badges (`Graphify AST`, `Daytona Dual-Sandbox`, `Devin`, `Collabute`).
2. **Left Column — Track 1: Client Shield («The Little Guy»):**
   - Sleeping client card (`Tariq Al-Mansoori`, Balance `AED 250,000.00`, Protected Escrow badge).
   - 3-layer defense status pills (`Auth` / `KYC` / `Transfer`).
   - Explainable **Question-Bottleneck Risk Score** bars.
   - **Shadow Honeypot** live attacker capture card (fake TX ID sent to hacker + captured mule IBAN & IP).
   - Morning Client Decision buttons (`Confirm Fraud & Lock` / `Release Escrow`).
3. **Center Column — Live Timeline + Graphify AST Blast Radius:**
   - Interactive node-edge graph from `GET /api/graph` with pulsing red compromised path & blast radius nodes (`EXTRACTED` edges).
   - Live streaming timeline feed from SSE.
4. **Right Column — Track 2: Bank Immune System («The Big Guy»):**
   - **Daytona Sandbox #1 (Reproduce Exploit):** live terminal logs + 🔴 `EXPLOIT CONFIRMED`.
   - **Autonomous Patch Diff:** syntax-highlighted unified diff of the fix.
   - **Daytona Sandbox #2 (Clean Held-Out Verify):** live terminal logs + 🟢 `EXPLOIT BLOCKED · 6/6 HELD-OUT TESTS PASSED`.
   - **GitHub PR Card:** branch, title, link to PR + KPI strip (`AED 250,000 Saved`, `MTTD < 20ms`, `MTTR < 8s`).
