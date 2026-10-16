"""Capture real responses from the Python cost-api as Java contract fixtures.

    python scripts/export_contract_fixtures.py

Writes solution/ledger-java/src/test/resources/contract/ (and the same for the
starter): team_summary.json, a problem example, and cost-api's openapi.json.
Re-run it whenever cost-api's models change; CostApiContractTest then tells you
whether the Java side still matches. In CI (Phase 9) this runs before `mvn test`.
"""

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
os.environ.setdefault("COST_API_AUTH_ENABLED", "false")
sys.path.insert(0, str(HERE.parent / "01-fastapi-pydantic-problem-details/solution/cost-api/src"))

from fastapi.testclient import TestClient  # noqa: E402

from cost_api.main import create_app  # noqa: E402

with TestClient(create_app()) as client:
    fixtures = {
        "team_summary.json": client.get("/v1/teams/payments/summary", params={"month": "2026-09"}).json(),
        "problem_team_not_found.json": client.get("/v1/teams/marketing/summary", params={"month": "2026-09"}).json(),
        "openapi.json": client.get("/openapi.json").json(),
    }

for target in ("solution", "starter"):
    out = HERE / target / "ledger-java/src/test/resources/contract"
    if out.parent.parent.parent.exists():
        out.mkdir(parents=True, exist_ok=True)
        for name, body in fixtures.items():
            (out / name).write_text(json.dumps(body, indent=2) + "\n")
        print(f"wrote {len(fixtures)} fixtures to {out.relative_to(HERE)}")
