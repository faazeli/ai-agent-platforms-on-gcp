# cost-api error catalog

Every error is `application/problem+json` (RFC 9457). Clients branch on `type`, never on `detail`.
The base URL comes from `COST_API_PROBLEM_BASE_URL` (default `https://example.com/problems`); replace it with a domain you own before publishing your API.

| `type` slug | Status | Meaning | Extension members | Retry? |
| --- | --- | --- | --- | --- |
| `invalid-request` | 422 | One or more query/path parameters failed validation | `invalid_params[]` with `name`, `in`, `reason` | No, fix the request |
| `team-not-found` | 404 | The team id has no cost data | none | No; call `GET /v1/teams` |
| `no-cost-data` | 404 | The team exists but has no rows in that month | none | No |
| `not-found` | 404 | Unknown route | none | No |
| `method-not-allowed` | 405 | Wrong HTTP method for the route | none | No |
| `unauthorized` | 401 | Missing or invalid token (added in Phase 6) | none | After re-authenticating |
| `forbidden` | 403 | Authenticated, but your role or team scope does not allow it (Phase 6) | none | No |
| `internal-error` | 500 | Unexpected failure; details are logged, not returned | `trace_id` | Yes, with backoff |

The MCP server (Phase 3) reuses these same `type` URIs inside tool errors, so one vocabulary spans HTTP and MCP.
