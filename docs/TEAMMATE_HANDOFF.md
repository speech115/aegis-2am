"""Teammate Handoff Guide — Frontend War Room UI + Demo + Submission."""

# 🛡️ Aegis 2AM — Teammate Quickstart (UI War Room + Demo + Submission)

Repo: **https://github.com/speech115/aegis-2am**

## 1. Clone & Start the Live Backend (Takes 30 Seconds)
```bash
git clone https://github.com/speech115/aegis-2am.git
cd aegis-2am
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/uvicorn backend.api.app:app --reload --port 8000
```
Open Swagger UI to explore every endpoint live: `http://localhost:8000/docs`

## 2. Full Frontend Contract
Read [`docs/API_CONTRACT.md`](API_CONTRACT.md) — every REST endpoint and SSE event payload is already implemented and tested (`pytest` green).

### Fastest Path to a 1st-Place UI (`frontend/` in Next.js + Tailwind)
Build a single-screen **"2:00 AM Dubai Security War Room"** (dark obsidian + emerald/crimson telemetry):
1. **Top Control Bar:**
   - Clock badge: `02:04 AM · DUBAI (GMT+4)`
   - Scenario picker (`GET /api/scenarios`)
   - Primary CTA: **`🚨 Launch 2:00 AM Attack`** (`POST /api/demo/run` → subscribe to SSE `GET /api/incidents/{id}/stream`)
   - **`Reset`** (`POST /api/bank/reset`)
   - **Collabute Voice Box** (focus input → dictate with Collabute → `POST /api/voice/command`)
   - Live Sponsor Badges (`GET /api/health` → shows `Daytona Cloud / Local Dual-Sandbox`, `Graphify AST`, `Devin`, `Collabute`)
2. **Column 1 (Left) — Track 1: Client Shield («The Little Guy»):**
   - Customer card (`Tariq Al-Mansoori`, Balance `AED 250,000.00`, Protected Escrow status)
   - 3-layer defense flow (`Layer 1 Auth` → `Layer 2 KYC` → `Layer 3 Transfer`)
   - Explainable **Question-Bottleneck Risk Bars** (7 plain-English questions + contribution bars)
   - **Shadow Honeypot Card** (Decoy TX ID sent to hacker + captured IP, device fingerprint, mule IBAN, TTP tags)
   - Morning action buttons: **`Confirm Fraud & Blacklist IBAN`** / **`Release Escrow`** (`POST /api/incidents/{id}/client-decision`)
3. **Column 2 (Center) — Graphify AST Blast Radius + Live Timeline:**
   - Interactive graph from `GET /api/graph`, highlighting `affected_node_ids` from `graphify_blast_radius` in pulsing red (`EXTRACTED` edges labeled!)
   - Real-time SSE event log
4. **Column 3 (Right) — Track 2: Bank Immune System («The Big Guy»):**
   - **Daytona Sandbox #1** terminal output (`🔴 EXPLOIT_CONFIRMED`)
   - **Autonomous Patch Diff** viewer (green/red unified diff)
   - **Daytona Sandbox #2** terminal output (`🟢 VERIFIED_PASS · 6/6 Held-Out Tests`)
   - **GitHub PR Card** + KPI metrics (`AED 250,000 Saved`, `MTTD < 15ms`, `MTTR`)

## 3. Submission Checklist (STRICT DEADLINE: 16:00)
- [ ] Both participants connected to **Devin AI** accounts (emails required in form!)
- [ ] Checkboxes ticked: `Graphify`, `Daytona`, `Cap`, `Collabute`
- [ ] Record 2-minute live walkthrough in **Cap**
- [ ] Upload video to **Google Drive** with **"Anyone with the link can view"**
- [ ] Deploy frontend to Vercel (add URL in `Anything extra`)
- [ ] Submit form by **15:45**: https://docs.google.com/forms/d/e/1FAIpQLSf7M9M4UwJUGBRnblfGOhNoH0ffnJDZcrgylvRCyeTvNojC1A/viewform
