# ADK apps

`adk web` and `adk run` treat each folder here as one app.

```bash
pip install -e ..            # installs costpilot_agents
cd adk_apps
adk web                      # pick "costpilot" or "monthly_report" in the UI
adk run costpilot            # terminal chat instead of the web UI
```

Both apps need the gateway on :4000 (Phase 4), mcp-finops on :8001 (Phase 3) and cost-api on :8000 (Phase 1),
plus the agents' virtual keys in the environment (`COORDINATOR_VKEY`, `COST_ANALYST_VKEY`, `ANOMALY_DETECTOR_VKEY`, `RECOMMENDER_VKEY`).
