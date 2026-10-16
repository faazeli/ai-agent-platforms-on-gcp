"""Lab 4.5 (6) — batch prediction: monthly summaries for every team as one job.

Batch jobs trade latency (minutes to hours) for a lower price per token, which
suits monthly reports. Inputs and outputs live in Cloud Storage.

    PROJECT=my-project BUCKET=gs://my-bucket MODEL=gemini-3.5-flash python vertex/batch_summaries.py

Check current batch pricing and the regions/models that support batch before
using this for a real decision.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from google import genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "solution/llm-toolkit/src"))
from costpilot_llm.evals.data import load_facts  # noqa: E402

facts = load_facts()
month = facts.months[-1]
bucket = os.environ["BUCKET"].rstrip("/")
requests = []
for team in facts.teams:
    tm = facts.team_month[(team, month)]
    services = ", ".join(f"{s} {round(c, 2)}" for s, c in sorted(tm.by_service.items(), key=lambda kv: -kv[1]))
    prompt = (f"Write a 3-sentence cost summary for team {team} in {month}. Effective cost {round(tm.effective, 2)} "
              f"{facts.currency}, billed {round(tm.billed, 2)}. By service: {services}.")
    requests.append({"request": {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}})

with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
    f.write("".join(json.dumps(r) + "\n" for r in requests))
src = f"{bucket}/batch/input-{int(time.time())}.jsonl"
subprocess.run(["gcloud", "storage", "cp", f.name, src], check=True)

client = genai.Client(vertexai=True, project=os.environ["PROJECT"], location=os.environ.get("LOCATION", "us-central1"))
job = client.batches.create(
    model=os.environ.get("MODEL", "gemini-3.5-flash"),
    src=src,
    config=types.CreateBatchJobConfig(dest=f"{bucket}/batch/output/", display_name="costpilot-monthly"),
)
print("submitted", job.name)
DONE = {"JOB_STATE_SUCCEEDED", "JOB_STATE_PARTIALLY_SUCCEEDED", "JOB_STATE_FAILED",
        "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
while job.state.name not in DONE:
    time.sleep(30)
    job = client.batches.get(name=job.name)
    print("state", job.state.name)
print("results under", f"{bucket}/batch/output/")
