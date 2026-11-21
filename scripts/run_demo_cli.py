"""Quick CLI verification & terminal demo runner for Aegis 2AM."""

from __future__ import annotations

import json
import sys
import time

from fastapi.testclient import TestClient

from backend.api.app import app


def main() -> None:
    scenario_id = sys.argv[1] if len(sys.argv) > 1 else "2am_kyc_replay_ato"
    with TestClient(app) as client:
        print("=== AEGIS 2AM HEALTH ===")
        print(json.dumps(client.get("/api/health").json(), indent=2))

        print(f"\n=== LAUNCHING SCENARIO: {scenario_id} ===")
        started = client.post(
            "/api/demo/run",
            json={"scenario_id": scenario_id, "step_delay_ms": 0, "wait": True},
        ).json()
        inc_id = started["incident_id"]
        inc = client.get(f"/api/incidents/{inc_id}").json()

        for ev in inc["events"]:
            print(f"[{ev['seq']:02d}] [{ev['phase']:15s}] [{ev['severity'].upper():8s}] {ev['title']} — {ev['detail']}")

        print("\n=== METRICS ===")
        print(json.dumps(inc["metrics"], indent=2))


if __name__ == "__main__":
    main()
