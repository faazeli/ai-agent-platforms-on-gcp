# Changelog

## 1.1.0 — 2026-10-16

- **Phase 9, Track B: Harness.** The same CostPilot delivery built in Harness:
  - a CI stage that builds, scans, signs (cosign with Cloud KMS) and attests by digest, on build pods in your own cluster
  - a dev canary gated by the *same* agent eval Job as the Argo AnalysisTemplate, plus optional Continuous Verification
  - an approval stage that the person who ran the pipeline can't approve
  - a prod canary
  - an in-cluster delegate with least-privilege RBAC and Workload Identity, and an OpenTofu module for its identities
  - OPA policies with tests, and Labs 9.H1–9.H7, ending in a measured comparison with Track A

  `tests/test_harness.py` checks schema validity and that both tracks deploy the same objects through the same gate.
- **Phase 5, Lab 5.9: typed decisions with TypeSafe AI's Jev** (optional).
  - Anomaly triage through three interchangeable deciders (mock, Jev, LLM), with deadlines that fail safe.
  - A versioned confidence policy decides between dismiss, review and propose, and a LangGraph flow puts every write behind human approval.
  - Calibration metrics (Brier, ECE, selective accuracy) and an 18-case labeled eval set.
  - Tests drive the real SDK against a fake server. Ideas borrowed from jev-trader: a mock model by default, and a late decision means no action.
- Phases 4 and 8 point to the calibration comparison and the cost of human review. The course CI installs opa, shellcheck and jsonschema.


## 1.0.0 — 2026-10-16

First public release: ten phases, starters and reference solutions, offline test suites, delivery assets, leadership templates.

Verified against: FastAPI 0.143, Pydantic 2.14, FastMCP 3.4.8, google-adk 2.12.0, LangGraph 1.2.15, langchain-mcp-adapters 0.3.2, Python 3.13, JDK 21 (domain layer), kustomize 5.7.1, kubeconform 0.7.0, hadolint 2.12.0, actionlint 1.7.7, OpenTofu 1.10.6 (fmt). See the root README for what was and wasn't executed.
