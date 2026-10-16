"""Lab 8.4 — load test the agent wherever it runs, with the same traffic shape.

The target is ADK's API server (`adk api_server` in Phase 5's adk_apps folder, or
the same app containerized on Cloud Run / GKE in Phase 9). For Agent Engine, use
agent_engine/deploy.py's `ask` in a loop instead; it has its own client.

    pip install locust
    cd ../05-multi-agent-adk-and-langgraph/solution/agents/adk_apps && adk api_server --port 8000 &
    locust -f loadtest/locustfile.py --host http://localhost:8000 \
           --users 20 --spawn-rate 2 --run-time 10m --headless --csv results/local

Model calls cost money: keep runs short, and point the agents at an eval-sized
gateway budget. Record p50/p95, failure rate and the gateway's spend for the run.
"""

import random
import uuid

from locust import HttpUser, between, task

APP = "costpilot"
QUESTIONS = [
    "How much did payments spend in 2026-09?",
    "What is driving data-platform's cost in 2026-09?",
    "Did anything unusual happen for ml-research in September 2026?",
    "Which team spent the most in 2026-08?",
    "Any savings opportunities for payments in 2026-09?",
]


class CostPilotUser(HttpUser):
    wait_time = between(5, 20)  # people read the answer before asking again

    def on_start(self):
        self.user_id = f"load-{uuid.uuid4().hex[:8]}"

    @task
    def ask(self):
        session_id = uuid.uuid4().hex
        self.client.post(f"/apps/{APP}/users/{self.user_id}/sessions/{session_id}", json={},
                         name="create session")
        with self.client.post("/run", name="run agent", catch_response=True, timeout=120, json={
            "app_name": APP, "user_id": self.user_id, "session_id": session_id,
            "new_message": {"role": "user", "parts": [{"text": random.choice(QUESTIONS)}]},
        }) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
            elif "limit of" in response.text:
                response.failure("budget guard stopped the run")
