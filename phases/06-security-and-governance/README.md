# Phase 6 — Zero Trust, RBAC, immutable audit and guardrails

| Time | Cloud cost | Builds on | You produce |
| --- | --- | --- | --- |
| Weeks 16–18 (≈ 30 h) | ≈ $1–5 (Model Armor calls, a small bucket) | Phases 1–5 | `costpilot-security`; secured `cost-api` and `mcp-finops`; Workload Identity; BigQuery row access; a locked audit trail; Model Armor screening |

## Why this phase matters

So far CostPilot trusts anything that can reach it. In production that is the main way agent platforms get hurt: a leaked key, a service that can read every team's data, a prompt injection that turns an agent into a confused deputy, an incident nobody can reconstruct. Zero Trust replaces "inside the network = trusted" with four habits, which you implement here:

1. **Every call proves who it is**: users with OIDC tokens, workloads with short-lived Google ID tokens via Workload Identity. No key files anywhere.
2. **Every call is authorized** against a role and a team scope, at three layers (API, MCP, BigQuery), so one bug doesn't expose everything.
3. **Every decision is recorded** where nobody can quietly change it.
4. **Every prompt and response is screened**, including tool results, where indirect prompt injection arrives.

## You will learn

- Workload Identity on GKE: KSA-to-GSA impersonation and direct `principal://` grants
- OIDC token verification (signature via JWKS, issuer, audience, expiry) and why audience matters
- Delegation between services without token passthrough, as the MCP authorization spec requires
- RBAC with team scoping, enforced in the API, the MCP server and BigQuery row access policies
- Tamper-evident audit logs: hash chains, plus Cloud Storage Bucket Lock for real immutability
- Model Armor templates, screening prompts and responses, and plugging it into ADK callbacks
- Fail-open versus fail-closed, and 401 versus 403 versus 404, as deliberate decisions

## Before you start

1. Phases 1–5 done.
2. An OIDC identity provider for user tokens. Any works; for the labs, a local [Keycloak](https://www.keycloak.org/getting-started/getting-started-docker) is easiest:
   ```bash
   docker run -d --name keycloak -p 8080:8080 -e KC_BOOTSTRAP_ADMIN_USERNAME=admin \
     -e KC_BOOTSTRAP_ADMIN_PASSWORD=admin quay.io/keycloak/keycloak:latest start-dev
   ```
   Create a realm `costpilot`, clients `cost-api` and `mcp-finops`, and two users. Add token mappers that put a `role` claim (`viewer`, `team_lead`, `finops_admin`) and a multi-valued `teams` claim into access tokens, and audience mappers so each client's tokens carry its own `aud`. The JWKS URL is `http://localhost:8080/realms/costpilot/protocol/openid-connect/certs`.
3. Read (about 2 hours):
   - [Workload Identity Federation for GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/workload-identity)
   - [MCP authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization), especially the sections on audience validation and token passthrough
   - [BigQuery row-level security](https://cloud.google.com/bigquery/docs/row-level-security-intro)
   - [Model Armor overview](https://docs.cloud.google.com/model-armor/overview) and [sanitizing prompts and responses](https://docs.cloud.google.com/model-armor/sanitize-prompts-responses)
   - [Cloud Storage Bucket Lock](https://cloud.google.com/storage/docs/bucket-lock)

## What's in this folder

```
starter/security     costpilot_security with TODOs (Labs 6.2–6.5)
starter/cost-api     Phase 2's cost-api + the auth tests it must pass (Lab 6.6)
starter/mcp-finops   Phase 3's MCP server + its auth tests (Lab 6.6)
solution/...         the same three, finished
gcp/workload_identity.sh     Lab 6.1
gcp/row_access_policies.sql  Lab 6.3
gcp/audit_sink.sh            Lab 6.4
gcp/model_armor_template.sh  Lab 6.5
```

```bash
cd phases/06-security-and-governance/starter
pip install -e "./security[dev,fastapi,adk]"
(cd security && pytest -q)
```

## The trust flow you are building

```
user ──(OIDC token, aud=mcp-finops)──► mcp-finops ── checks role + team (layer 2)
                                          │
                                          │  its OWN Google ID token (aud=cost-api) via Workload Identity
                                          │  + X-Costpilot-On-Behalf-Of: {sub, role, teams}
                                          ▼
                                       cost-api ── trusts delegation only from allow-listed workloads;
                                          │         checks role + team (layer 1); audits every decision
                                          ▼
                                       BigQuery ── row access policies by team (layer 3)
```

The MCP server never forwards the user's token. A token minted for `mcp-finops` must not be accepted by `cost-api` (different audience), and forwarding it would make the MCP server a confused deputy. That is why the spec forbids passthrough. Delegation through a trusted workload is the simple pattern used here; OAuth 2.0 Token Exchange ([RFC 8693](https://www.rfc-editor.org/rfc/rfc8693)) is the standards-based upgrade when you need the upstream to verify the user's identity cryptographically.

## Labs

### Lab 6.1 — Keyless workload identity

Read `gcp/workload_identity.sh`, then run it against your project (the GKE parts are skipped until Phase 9 creates the cluster):

```bash
PROJECT=$PROJECT NAMESPACE=costpilot ./gcp/workload_identity.sh
```

Each service gets its own identity with the least privilege it needs. `mcp-finops` gets *no* Google API roles, because it only calls `cost-api`. Only the gateway may call Vertex AI. Then compare the newer pattern: grant a role directly to the Kubernetes service account as a `principal://` identity, with no Google service account at all. Record in an ADR which you'd standardize on and why.

**Check:** `gcloud iam service-accounts keys list --managed-by=user` returns nothing for every CostPilot account.

### Lab 6.2 — User authentication and delegation

Implement `resolve_principal` in `starter/security/src/costpilot_security/identity.py` (`TODO Lab 6.2`). `TokenVerifier` is done: it checks signature (JWKS), issuer, audience and expiry, and returns deliberately vague errors.

The tests mint real RS256 tokens and try the classic attacks: wrong audience, wrong issuer, expired, wrong key, garbage, a user forging a delegation header, an untrusted workload delegating.

**Check:** `pytest -q -k "token or delegat or workload"` in `starter/security`.

### Lab 6.3 — RBAC at three layers

1. **API and MCP layers:** implement `check_team` and `visible_teams` in `rbac.py`. Roles grant permissions (`viewer`, `team_lead`, `finops_admin`); team membership limits which data a permission applies to.
2. **Data layer:** edit and run `gcp/row_access_policies.sql` (replace the example groups and `PROJECT_ID`). Then query `focus_costs` as a user in only one group and confirm you see only that team's rows.

Notice the limit of layer 3: BigQuery sees `cost-api`'s identity, not the end user's, so `cost-api` needs broad row access, and the per-user check *must* happen in the API. Defense in depth means each layer covers a different failure.

**Decision to record:** should a viewer asking about another team get 403 ("you can't") or 404 ("doesn't exist")? The solution returns 403 for real and made-up teams alike, so outsiders can't probe which teams exist. Write down what you chose and why.

### Lab 6.4 — Immutable audit logging

Implement `verify_chain` in `audit.py` (`TODO Lab 6.4`). `AuditLog.record` already writes hash-chained JSON entries to stdout. The test edits, deletes and re-hashes entries and expects `verify_chain` to catch each.

Then make storage immutable:

```bash
PROJECT=$PROJECT BUCKET=$PROJECT-costpilot-audit-lab RETENTION=1d ./gcp/audit_sink.sh          # no lock yet
PROJECT=$PROJECT BUCKET=$PROJECT-costpilot-audit-lab RETENTION=1d ./gcp/audit_sink.sh --lock   # permanent!
```

The hash chain gives you *evidence* of tampering. The locked retention policy *prevents* deletion or overwrite, even by project owners. You want both. Use a short retention and a throwaway bucket for the lab: a locked bucket can't be deleted until its objects age out.

Connect the agents too: `AuditLog(...).as_agent_audit()` plugs into Phase 5's `build_team(..., audit=...)`, so every tool decision, approval wait and budget stop is in the same trail.

### Lab 6.5 — Model Armor guardrails

```bash
PROJECT=$PROJECT LOCATION=us-central1 ./gcp/model_armor_template.sh
```

1. Try the `sanitizeUserPrompt` call the script prints, with a benign prompt and an injection attempt.
2. Implement the response parsing in `ModelArmorClient._sanitize` (`TODO Lab 6.5`).
3. Wire it into Phase 5's team: `build_team(models, tools_for, audit=..., guardrails=adk_callbacks(client, audit))`. Each specialist then runs the Model Armor check after its budget callback (ADK runs a list of callbacks in order, and the first to return a response wins). The `before` callback screens the newest content, which includes **tool results**: that is where indirect prompt injection arrives.
4. Re-run Phase 5's injection drill. It should now be stopped earlier (at the guardrail), with an audit entry, while the tool guard remains as the second line.

**Decide and record:** if Model Armor is unreachable, do you fail closed (block) or fail open (allow)? The client defaults to closed. Consider which answer you'd give for an internal read-only FinOps tool versus an agent that can open tickets.

### Lab 6.6 — Secure cost-api and mcp-finops

Now apply the library to the services. Use `solution/cost-api` and `solution/mcp-finops` as references; the diff is small.

**cost-api** (`starter/cost-api`):

1. Add the auth settings listed in `settings.py` (`TODO Lab 6.6`).
2. Implement `caller` and `authorize` in `security.py`.
3. In `main.py`: build security and the audit log in `create_app`, store them on `app.state`, install the security error handler, make `require_known_team` call `authorize(..., "costs:read", team_id)` *before* checking that the team exists, and filter `GET /v1/teams` with `visible_teams`.

**mcp-finops** (`starter/mcp-finops`):

1. `CostApiClient._get` takes an `on_behalf_of` principal and sends `X-Costpilot-On-Behalf-Of`; the HTTP client authenticates as the workload (`GoogleIdTokenAuth`).
2. A `current_user(team_id)` helper reads `get_access_token()`, applies `check`/`check_team`, and turns refusals into tool errors, so forbidden requests never leave the MCP server.
3. `__main__.py` enables `JWTVerifier(jwks_uri=..., issuer=..., audience="mcp-finops")`.

```bash
(cd cost-api && pip install -e ".[dev]" && pytest -q)
(cd mcp-finops && pip install -e ".[dev]" && pytest -q)
```

Then run both against Keycloak: get a token for a `viewer` of `payments` (Keycloak's token endpoint, password grant for the lab), call `cost-api` directly for `payments` (200) and `search` (403), and connect the MCP Inspector to `mcp-finops` with the token as a bearer header. Local development without auth stays possible with `COST_API_AUTH_ENABLED=false` / `MCP_FINOPS_AUTH_ENABLED=false`, and both services log a loud warning when you do.

## Done when

- [ ] No service-account keys exist for any CostPilot identity
- [ ] `pytest -q` passes in `starter/security`, `starter/cost-api` and `starter/mcp-finops`
- [ ] A viewer cannot see another team's spend through the API, through an agent, or through SQL, and you can show each
- [ ] Every denial returns a Problem Details 401 or 403 without leaking internals; 401s carry `WWW-Authenticate`
- [ ] Audit entries reach a bucket with a locked retention policy, and the verifier passes on an export
- [ ] Model Armor screens prompts, tool results and responses, and the injection drill is now stopped at the guardrail

## Write it down (ADRs)

- `0008-workload-identity.md`: KSA→GSA versus direct principal grants
- `0009-delegation-model.md`: delegation header versus token exchange, and why no passthrough
- `0010-authorization-errors.md`: 401/403/404 choices, fail-open versus fail-closed

## Teach it (5 minutes)

Show the trust-flow diagram and one test that proves the MCP server never forwards the user's token. Ask: which of our services accept a token minted for a different service?

## Stretch goals

- Replace the delegation header with RFC 8693 token exchange against your IdP and compare the complexity.
- Add an `audit:read` endpoint for `finops_admin` that streams audit entries for a time range and verifies the chain on the fly.
- Run Model Armor at the gateway instead of in the agents (LiteLLM supports guardrail integrations), and compare coverage and latency.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `RuntimeError: Set COST_API_OIDC_JWKS_URI` at startup | Auth is on by default. Configure your IdP, or set `COST_API_AUTH_ENABLED=false` for local dev only. |
| Every token is rejected as invalid | Check `aud` in the token (jwt.io, locally) matches `COST_API_OIDC_AUDIENCE`, and `iss` matches exactly, including any trailing slash. |
| Viewer sees no teams | The access token lacks the `teams` claim. Add the Keycloak mapper and check "add to access token". |
| BigQuery returns zero rows after adding row policies | Principals not covered by any policy see nothing. Grant `cost-api`'s service account the `finops_all` policy. |
| Model Armor returns 403 | Grant the caller `roles/modelarmor.user`, and use the regional endpoint `modelarmor.<location>.rep.googleapis.com`. |

## Teardown

Stop Keycloak (`docker rm -f keycloak`). Delete the Model Armor template if you won't use it again. The lab audit bucket can be deleted once its retention period has passed.
