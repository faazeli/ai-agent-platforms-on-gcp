# Phase 7 — Java integration with core platform services

| Time | Cloud cost | Builds on | You produce |
| --- | --- | --- | --- |
| Weeks 19–20 (≈ 20 h) | ≈ $1 in model calls | Phases 1, 5, 6 | `ledger-java`, a Spring Boot budgets service integrated with the Python platform; `budget-guardian`, an ADK for Java agent reachable over A2A |

## Why this phase matters

Most enterprises run their core platform services on the JVM. An AI platform that only speaks Python ends up isolated, re-implementing contracts and security the rest of the company already has. This phase builds the bridges both ways: Java calling the Python APIs through a shared contract and a shared error format, and a Python agent delegating to a Java agent over the Agent2Agent (A2A) protocol. It is also where the object-oriented design habits of enterprise Java (immutable values, sealed hierarchies, constructor injection, no static state) meet the platform.

> **Verification note.** This phase targets **Spring Boot 4.1** (Spring Framework 7, Jackson 3, Java 21) and **ADK for Java 1.7.1**. When the course was built, the pure-Java domain (`domain/`) was compiled and exercised with JDK 21, but the Spring and ADK builds could not be run in the authoring environment, which had no Maven Central access. If `mvn test` fails on your machine, please open an issue with the error: Boot 4 renamed several starters and moved some test annotations, and those are the likeliest spots.

## You will learn

- Contract-first integration: Java records that mirror Pydantic models, and a contract test fed by fixtures captured from the real Python API
- RFC 9457 in Spring: `ProblemDetail`, `ResponseEntityExceptionHandler`, mapping upstream problems to your own
- Spring Boot 4 essentials: renamed starters, `@ConfigurationProperties` records, `RestClient`, `MockRestServiceServer`, standalone `MockMvc`
- OO design that survives change: records, sealed interfaces with exhaustive `switch`, pure domain logic separated from frameworks
- Spring Security as an OAuth2 resource server, with the same RBAC rule as the Python services
- Workload identity from Java (Google ID tokens via Application Default Credentials)
- ADK for Java, and connecting agents across languages with A2A

## Before you start

1. JDK 21 and Maven 3.9+ (`java -version`, `mvn -version`). IntelliJ IDEA or VS Code with the Java extension pack.
2. Phase 1's `cost-api` running on :8000 (with `COST_API_AUTH_ENABLED=false` for the first labs).
3. Read (about 2 hours):
   - [Spring Boot reference: REST clients](https://docs.spring.io/spring-boot/reference/io/rest-client.html) and [error handling](https://docs.spring.io/spring-boot/reference/web/servlet.html)
   - [Spring Framework: ProblemDetail and error responses](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-ann-rest-exceptions.html)
   - [Spring Boot 4 migration notes](https://bell-sw.com/blog/how-to-migrate-a-spring-boot-3-project-to-spring-boot-4/) (starters renamed, Jackson 3)
   - ADK for Java: [getting started](https://adk.dev/get-started/java/) and the [1.0 announcement](https://developers.googleblog.com/announcing-adk-for-java-100-building-the-future-of-ai-agents-in-java/)

## What's in this folder

```
starter/ledger-java, solution/ledger-java       Spring Boot 4.1 service
  domain/          Budget, BudgetStatus, BudgetEvaluator, AllocationRule (sealed), Allocator  ← pure Java
  client/          CostApiClient (RestClient), TeamCostSummary (record), CostApiException, GoogleIdTokenInterceptor
  budget/          repository, service, controller, response DTO
  security/        SecurityConfig (resource server), TeamAccess (RBAC)
  web/ApiErrors    Problem Details for everything
  src/test/resources/contract/   fixtures captured from the Python cost-api
starter/budget-guardian-agent, solution/...     ADK for Java agent
scripts/export_contract_fixtures.py             regenerate the contract fixtures
solution/a2a/remote_guardian.py                 the Python coordinator delegating over A2A
```

```bash
cd phases/07-java-integration/starter/ledger-java
mvn -q test          # fails until you finish the labs
```

## Labs

### Lab 7.1 — Contract-first client

The Java client must not guess what Python sends. Look at:

- `client/TeamCostSummary.java`: a record with `@JsonProperty("total_effective_cost")` and friends. The JSON names are the wire contract; the Java names are idiomatic Java. (This is the same separation Phase 1 made with Pydantic aliases.)
- `src/test/resources/contract/team_summary.json`: a response captured from the *real* Python `cost-api` by `scripts/export_contract_fixtures.py`.
- `CostApiContractTest`: fails if the Java record and the Python response don't have exactly the same fields.

Prove the safety net works: add a field to `TeamCostSummary` in Phase 1's `models.py` (say `forecast_effective_cost`), re-run `python scripts/export_contract_fixtures.py`, then `mvn test`. The contract test fails and tells you why. Revert the change.

Optional: generate a client from cost-api's OpenAPI spec (`contract/openapi.json`) with [openapi-generator](https://openapi-generator.tech/) (`-g java --library restclient`) and compare it with the hand-written one. Record in an ADR when you'd generate and when you'd hand-write.

### Lab 7.2 — The same error contract in Java

1. `CostApiClient.toException` (`TODO Lab 7.2`): turn a Python problem response into a `CostApiException` that carries the whole `ProblemDetail`, so callers branch on `ex.slug()` ("team-not-found") exactly as Python clients do. Non-problem error bodies (an HTML error page from a proxy) must still become a problem.
2. `ApiErrors.upstream` (`TODO Lab 7.2`): upstream 4xx errors describe the caller's request, so pass their status and type through. Upstream 5xx means *our dependency* failed, so answer 502 `upstream-error` and keep the upstream type as an extension member.

`spring.mvc.problemdetails.enabled: true` plus extending `ResponseEntityExceptionHandler` makes Spring's own errors (validation 400s, unknown routes, wrong methods) Problem Details too. Try `curl -i localhost:8080/v1/budgets/payments/status?month=2026-13` once the service runs.

**Check:** `mvn test -Dtest='CostApiClientTest,BudgetControllerTest'`.

### Lab 7.3 — Object-oriented design that survives change

1. Implement `BudgetEvaluator.evaluate` (`TODO Lab 7.3 (a)`): linear month-end forecast, percent used, and a state.
2. Implement the `switch` in `Allocator.allocate` (`TODO Lab 7.3 (b)`) over the sealed `AllocationRule`: `Even`, `Fixed`, `Proportional`. Write it with **no default branch**.

Then change the design mid-lab, which is the point of the exercise: add a fourth rule, `ByTag(String tagKey, Map<String, String> teamByTagValue)`, to the `permits` list. The compiler now refuses to build `Allocator` until you handle it. That compile error is a feature: a sealed hierarchy turns "we forgot a case" from a production bug into a build failure. Note what else made the change easy (records, a pure domain with no Spring in it) and what didn't.

**Check:** `mvn test -Dtest='BudgetEvaluatorTest,AllocatorTest'`.

### Lab 7.4 — Identity and security

1. Implement `TeamAccess.check` (`TODO Lab 7.4`): the same rule as Phase 6's `check_team`, reading the same `role` and `teams` claims from the JWT.
2. Read `SecurityConfig`: every `/v1` request needs a JWT from your identity provider; issuer and audience come from `application.yml`. Health probes stay open for Kubernetes.
3. Run the service against Keycloak from Phase 6 (add a `ledger-java` client and audience mapper):

```bash
mvn spring-boot:run
TOKEN=...   # a viewer of payments, from Keycloak
curl -s localhost:8080/v1/budgets/payments/status?month=2026-09 -H "Authorization: Bearer $TOKEN"
curl -s localhost:8080/v1/budgets/search/status?month=2026-09 -H "Authorization: Bearer $TOKEN"   # 403 problem
```

On GKE (Phase 9), set `COST_API_WORKLOAD_AUTH=true`: `GoogleIdTokenInterceptor` then attaches this pod's Google ID token (via Workload Identity, no key file) when calling `cost-api`, and `cost-api` sees a workload principal. Add `ledger-java-gsa` to Phase 6's `workload_identity.sh` with no Google API roles: it only calls `cost-api`.

### Lab 7.5 — An agent in Java, reachable over A2A

1. Build the agent in `budget-guardian-agent` (`TODO Lab 7.5`): `LlmAgent.builder()` with a description (the Python coordinator routes on it), an instruction, and `FunctionTool.create(BudgetTools.class, "getBudgetStatus")`. Read `BudgetTools`: tools are static methods described with `@Schema`.
2. Chat with it:

```bash
cd budget-guardian-agent
export GOOGLE_GENAI_USE_VERTEXAI=TRUE GOOGLE_CLOUD_PROJECT=$PROJECT GOOGLE_CLOUD_LOCATION=global
export LEDGER_URL=http://localhost:8080 LEDGER_TOKEN=$TOKEN
mvn -q compile exec:java
```

3. Expose it over A2A. ADK for Java's `a2a` module provides the runtime, and its `a2a/webservice` module a Spring Boot transport (`A2ARemoteConfiguration`, which serves your `BaseAgent` bean over JSON-RPC). Follow the current [A2A guide for Java](https://adk.dev/a2a/quickstart-exposing-java/) and the examples in the [adk-java repository](https://github.com/google/adk-java): the module coordinates and agent-card path move between releases, so take them from there rather than from memory. Note the agent card URL your server publishes.
4. From Python, add the Java agent to Phase 5's team as a sub-agent:

```bash
pip install "google-adk[a2a]"
export GUARDIAN_AGENT_CARD=<agent card URL from step 3>
python solution/a2a/remote_guardian.py "Is payments on budget for 2026-09?"
```

`RemoteA2aAgent` reads the agent card and behaves like any local sub-agent, so the coordinator routes budget questions to Java without knowing it's Java. ADK Python marks its A2A support as experimental, so pin your versions.

**ADR (trade-off):** the Java agent calls Vertex AI directly, bypassing the LiteLLM gateway and its per-agent budgets. Options: accept it, with a separate Vertex AI quota and budget alert for this agent; route Java through the gateway (check whether your ADK for Java version supports an OpenAI-compatible model or a LangChain4j bridge); or keep model calls out of Java and let it be a pure tool service. Decide and justify.

## Done when

- [ ] `mvn test` passes in `starter/ledger-java`, including the contract test against Python's real response
- [ ] Every error from `ledger-java` is `application/problem+json`, and upstream Python problems map as designed
- [ ] Adding a fourth `AllocationRule` fails the build until it is handled
- [ ] A viewer gets 200 for their team and a 403 problem for another, with the same rule as the Python services
- [ ] A Python agent asks "is payments on budget?", the coordinator delegates to the Java agent over A2A, and both sides log the request

## Write it down (ADRs)

- `0011-java-contracts.md`: generated versus hand-written clients; how the contract test runs in CI
- `0012-java-agent-model-access.md`: the gateway trade-off from Lab 7.5

## Teach it (5 minutes)

Break the contract on purpose (rename a Python field) and show the Java build failing with a readable message. Ask the Java and Python developers in the room how they find out about each other's breaking changes today.

## Stretch goals

- Replace the configuration-backed `BudgetRepository` with Spring Data JDBC on Cloud SQL for PostgreSQL.
- Add Spring Boot's OpenTelemetry support and see the trace continue from `ledger-java` into `cost-api` (Phase 9 sets up tracing for the Python side).
- Build the Java image with `mvn jib:build` (already configured in the POM) instead of a Dockerfile, and compare it with Phase 9's Python images.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Could not find artifact org.springframework.boot:spring-boot-starter-web` | Boot 4 renamed it: use `spring-boot-starter-webmvc` (already in the POM). |
| `package com.fasterxml.jackson.databind does not exist` | Jackson 3 moved databind to `tools.jackson.*`. Only the annotations (`com.fasterxml.jackson.annotation`) kept their package. |
| `@WebMvcTest` or `@MockBean` not found | Boot 4 moved `@WebMvcTest` and replaced `@MockBean` with `@MockitoBean`. This project avoids both by using standalone `MockMvc`. |
| Every request is 401 | Check `OIDC_ISSUER` matches the token's `iss` exactly and the token's `aud` includes `ledger-java`. |
| `These credentials cannot mint ID tokens` | Locally, user credentials can't mint ID tokens for arbitrary audiences; keep `COST_API_WORKLOAD_AUTH=false` and use workload auth on GKE. |
| A2A: Python can't reach the agent card | Open the agent card URL in a browser first; then check the Java server's port and path. |

## Teardown

Stop the Java processes. Nothing new runs in the cloud in this phase.
