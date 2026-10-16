# Glossary

| Term | Meaning in this course |
| --- | --- |
| **A2A** | Agent2Agent protocol: lets agents built in different frameworks or languages call each other (Phase 7). |
| **ADC** | Application Default Credentials: how Google SDKs find credentials (your login locally, Workload Identity on GKE). |
| **ADK** | Google's Agent Development Kit, for Python, Java, Go and TypeScript (Phase 5, 7). |
| **ADR** | Architecture Decision Record: a one-page record of a decision, its options and consequences. |
| **Alias (model)** | A gateway name such as `fast` or `smart` that maps to a real model id, so agents never hardcode vendors (Phase 4). |
| **BilledCost** | FOCUS: what the invoice charges for a row. |
| **Canary** | Shipping a new version to a small share of traffic first, and rolling back automatically if it misbehaves (Phase 9). |
| **Delegation** | A workload calling an API on behalf of a user without forwarding the user's token (Phase 6). |
| **EffectiveCost** | FOCUS: amortized cost after commitments and discounts; what teams should see. |
| **Eval** | A test of model or agent behaviour against cases with known answers (Phase 4, 5). |
| **Execution boundary** | A limit enforced in code on what an agent can do: allowed tools, approvals, budgets (Phase 5). |
| **FOCUS** | FinOps Open Cost and Usage Specification: a vendor-neutral schema for billing data (Phase 2). |
| **GitOps** | The cluster's desired state lives in Git; a controller (Argo CD) makes the cluster match it (Phase 9). |
| **GSA / KSA** | Google service account / Kubernetes service account; Workload Identity lets a KSA act as a GSA. |
| **MCP** | Model Context Protocol: a standard way for AI clients to discover and call tools, read resources and use prompts (Phase 3). |
| **Model Armor** | Google Cloud service that screens prompts and responses for injection, sensitive data and harmful content (Phase 6). |
| **Problem Details** | RFC 9457 (formerly 7807): the standard JSON shape for HTTP API errors. |
| **Prompt injection** | Text that tries to change a model's instructions; *indirect* injection arrives inside data the agent reads. |
| **RBAC** | Role-based access control: roles grant permissions; here also scoped by team. |
| **SBOM / SLSA** | Software bill of materials / Supply-chain Levels for Software Artifacts (Phase 9). |
| **SLO** | Service level objective: a target for a user-visible measure, with an error budget. |
| **Workload Identity** | GKE feature that gives pods Google credentials without key files. |
| **WIF** | Workload Identity Federation: external identities (such as GitHub Actions) get short-lived Google credentials. |
