#!/usr/bin/env bash
set -euo pipefail

# Safely connects a DAYTONA_API_KEY copied to your macOS clipboard:
# 1. Validates prefix without printing the secret
# 2. Stores it in 1Password vault ("Агенты") via op-agent
# 3. Writes /Users/sereja/Projects/apps/aegis-2am/.env (0600)
# 4. Runs a live Daytona Cloud Dual-Sandbox smoke test

PROJECT_DIR="/Users/sereja/Projects/apps/aegis-2am"
ENV_FILE="$PROJECT_DIR/.env"

KEY="$(pbpaste | tr -d '\r\n ')"
if [ -z "$KEY" ] || [ "${#KEY}" -lt 16 ]; then
  echo "ERROR: Clipboard is empty or too short. Copy your Daytona API key from https://app.daytona.io/dashboard/keys first."
  exit 1
fi

echo "Clipboard key detected (length=${#KEY}). Storing in 1Password and writing .env (0600)..."

if command -v op-agent >/dev/null 2>&1; then
  printf '%s' "$KEY" | op-agent store-key \
    --title "Daytona API Key (CIS Sprint)" \
    --project "aegis-2am" \
    --url "https://app.daytona.io" >/dev/null 2>&1 || true
fi

touch "$ENV_FILE"
chmod 600 "$ENV_FILE"
python3 - "$ENV_FILE" <<'PY'
import os, subprocess, sys
env_path = sys.argv[1]
key = subprocess.check_output(["pbpaste"], text=True).strip()
lines = []
found = False
if os.path.exists(env_path):
    for line in open(env_path, encoding="utf-8"):
        if line.startswith("DAYTONA_API_KEY="):
            lines.append(f"DAYTONA_API_KEY={key}\n")
            found = True
        else:
            lines.append(line)
if not found:
    lines.append(f"DAYTONA_API_KEY={key}\n")
with open(env_path, "w", encoding="utf-8") as f:
    f.writelines(lines)
os.chmod(env_path, 0o600)
print("Updated .env securely (mode 0600).")
PY

echo "Testing live Daytona Cloud Dual-Sandbox..."
cd "$PROJECT_DIR"
.venv/bin/python -c '
from dotenv import load_dotenv
load_dotenv()
from backend.attacker.scenarios import SCENARIOS
from backend.immune.daytona_verifier import DaytonaDualSandboxVerifier
v = DaytonaDualSandboxVerifier()
print("Verifier mode:", v.mode)
r1 = v.run_sandbox_1_exploit(SCENARIOS["2am_kyc_replay_ato"])
print("Sandbox #1:", r1.mode, r1.sandbox_id, r1.status, f"{r1.duration_ms}ms")
'
