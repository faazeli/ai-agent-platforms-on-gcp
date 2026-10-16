# Golden path: "a secure MCP server on GKE in one day"

A template repository turns what you learned in Phases 3, 6 and 9 into a starting point other teams can use without taking this course.

## What the template includes
- [ ] FastMCP server skeleton with one example tool, typed output, bounded inputs
- [ ] Problem Details errors and a hint convention (Phase 3)
- [ ] JWT verification on the MCP endpoint and delegation to upstream APIs (Phase 6)
- [ ] Audit logging wired in (Phase 6)
- [ ] Hardened Dockerfile and Kustomize base with Workload Identity and default-deny NetworkPolicy (Phase 9)
- [ ] CI: tests, build, scan, sign, deploy to dev via GitOps (Phase 9)
- [ ] An eval file with three example cases and the gate in CI
- [ ] README: "from template to deployed in one day", with every command
- [ ] An ADR folder with the decisions already made and why

## Measuring adoption
| Metric | How | Target |
| --- | --- | --- |
| Teams that used it | Repos created from the template | 3 in the first quarter |
| Time to first deploy | Repo creation → first dev deploy (from CI) | Under 1 day |
| Support load | Questions in your channel per new team | Falling over time |
| Drift | Template version each repo is on | Most within one minor version |

## Keeping it alive
- [ ] An owner and a review cadence
- [ ] A changelog; breaking changes announced
- [ ] A "contributing back" path for teams that improve it
