# 🛡️ Aegis 2AM — Autonomous Banking Immune System

> **The CIS Sprint x Devin (Dubai, Nov 21, 2026)**
> Built from scratch today to solve **both tracks simultaneously**: protecting **the little guy** (customer accounts & transactions) and **the big guy** (the bank's own infrastructure & code) at **2:00 AM in Dubai**.

---

## The Problem (2:00 AM in Dubai)

Everyone is asleep — customers and bank engineers alike. Attackers bypass 3 layers of defense (Session Auth → KYC Verification → Transfer Execution) and try to drain **AED 250,000** from a customer's account.

Existing solutions are split in half:
- Fraud platforms (BioCatch, Sardine, Kairos) score transactions *outside* the bank's codebase — they can block a transfer, but **cannot find or patch the code vulnerability** that let the attacker bypass KYC.
- Security coding agents (Aardvark, Patchlane) patch code — but **don't save the customer's money in real time** or trap the attacker during the live intrusion.

## Our Solution: Closed-Loop Autonomous Defense

**Aegis 2AM** closes the loop in seconds across **both tracks**:

```mermaid
flowchart LR
    A["2:00 AM Attack\n(Auth → KYC → Transfer)"] --> B["Track 1: Client Shield\nQuestion-Bottleneck Risk (<15ms)"]
    B --> C["Protected Escrow Hold\n(AED 250,000 Saved)"]
    B --> D["Shadow Honeypot\n(Decoy TX + Capture TTP/IBAN)"]
    D --> E["Track 2: Graphify AST\nDeterministic Blast Radius"]
    E --> F["Daytona Sandbox #1\nReproduce Exploit (RED)"]
    F --> G["Autonomous Patch\n(Devin / AI Patcher + Diff)"]
    G --> H["Daytona Sandbox #2\nHeld-Out Tests Verify (GREEN)"]
    H --> I["GitHub Pull Request\nReady for CISO at 8:00 AM"]
```

---

## Sponsor Stack Integration

| Sponsor | Role in Aegis 2AM |
| :--- | :--- |
| **Cognition / Devin** | Autonomous remediation & PR engineering workflow |
| **Graphify** | Deterministic tree-sitter AST Knowledge Graph of the bank codebase (`EXTRACTED` call/import edges) for zero-hallucination blast-radius localization |
| **Daytona** | **Dual-Sandbox Verification**: Sandbox #1 reproduces the live exploit against unpatched bank code; clean Sandbox #2 verifies the patch against held-out regression tests the patcher never saw |
| **Collabute** | Voice-driven CISO / customer command interface (`POST /api/voice/command`) for morning incident triage & one-phrase actions |
| **Cap** | Demo recording & submission walkthrough |

---

## Quick Start

### Backend (FastAPI + Bank Core + Graphify + Daytona)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# Optional sponsor SDKs:
pip install -e ".[sponsors]"

cp .env.example .env
# Add DAYTONA_API_KEY to enable live Daytona Cloud dual-sandboxes (falls back to isolated local sandboxes automatically)

uvicorn backend.api.app:app --reload --port 8000
```

### Run Tests
```bash
pytest -v
```

### API Docs & Teammate Contract
- Full REST + SSE specification: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md)
- Interactive Swagger UI: `http://localhost:8000/docs`
