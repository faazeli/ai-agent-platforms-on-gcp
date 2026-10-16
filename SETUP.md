# Setup

Do this once, before Phase 1. About an hour.

## 1. Local tools

| Tool | Version | Needed from | Check |
| --- | --- | --- | --- |
| Python | 3.11+ | Phase 1 | `python3 --version` |
| [uv](https://docs.astral.sh/uv/) (recommended) or pip | latest | Phase 1 | `uv --version` |
| Git | any recent | Phase 1 | `git --version` |
| Docker Desktop or Docker Engine | 24+ | Phase 4 | `docker version` |
| Node.js (for the MCP Inspector) | 18+ | Phase 3 | `node --version` |
| JDK 21 and Maven 3.9+ | | Phase 7 | `java -version`, `mvn -version` |
| Google Cloud CLI (`gcloud`, `bq`) | latest | Phase 2 | `gcloud version` |
| kubectl and kustomize | latest | Phase 9 | `kubectl version --client` |
| OpenTofu | 1.8+ | Phase 9 | `tofu version` |

An editor with Python and Java support (VS Code with the Python and Java extension packs, or PyCharm plus IntelliJ IDEA) makes the starters much easier.

## 2. The course data

```bash
python data/generate_sample.py
```

This writes `data/sample/focus_costs.csv`: 92 days of synthetic FOCUS cost data for four teams, with a commitment purchase, untagged spend and one planted anomaly. Every phase uses it, and the committed file is what the tests expect. Don't edit it by hand.

## 3. A Google Cloud project (from Phase 2)

1. Create a project (or use a sandbox your organization gives you) and link a billing account. New accounts usually come with free trial credits; check the current offer.
2. **Create a budget alert before anything else:** Billing → Budgets & alerts → Create budget, for this project, with alerts at 50%, 90% and 100% of an amount you're comfortable with (for example $50/month). It's also your first FinOps habit.
3. Log in and set defaults:

```bash
gcloud auth login
gcloud auth application-default login      # credentials for SDKs and the local gateway
export PROJECT=your-project-id
gcloud config set project $PROJECT
gcloud services enable bigquery.googleapis.com aiplatform.googleapis.com
```

Later phases enable more APIs as they need them, and say which.

## 4. Your own working repository

Fork or copy this course into your own GitHub repository. Work in each phase's `starter/` folder, and keep your ADRs under `docs/adr/` in your repo. Phase 9 runs CI from it.

## 5. Environment variables you'll collect along the way

| Variable | Set in | Used by |
| --- | --- | --- |
| `PROJECT` | Setup | scripts in every phase |
| `LITELLM_MASTER_KEY` | Phase 4 `.env` | gateway admin calls |
| `COORDINATOR_VKEY`, `COST_ANALYST_VKEY`, `ANOMALY_DETECTOR_VKEY`, `RECOMMENDER_VKEY`, `EVAL_RUNNER_VKEY` | Phase 4 key script | Phase 5 agents, evals |
| `COST_API_*`, `MCP_FINOPS_*` | Phase 6 | secured services |

Never commit any of these. `.gitignore` already excludes `.env` files.
