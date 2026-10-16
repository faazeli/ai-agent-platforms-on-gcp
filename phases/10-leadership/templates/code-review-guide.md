# Code review as coaching

Every review comment carries a label, so the author knows what's required and what's optional.

| Label | Meaning | Must the author act? |
| --- | --- | --- |
| `blocking:` | Must change before merge (bug, security, broken contract) | Yes |
| `question:` | I don't understand; help me | Answer, maybe change |
| `suggestion:` | I'd do it differently; your call | No |
| `nit:` | Style or taste | No |
| `praise:` | This is good; keep doing it | No |

## Examples from CostPilot

- `blocking:` This query has no `ChargePeriodStart` filter, so it fails on the partitioned table (`require_partition_filter`) and would scan everything if it didn't. See ADR 0002.
- `question:` Why does the tool return a string instead of a `TeamCostSummary`? Agents lose the output schema; was that deliberate?
- `suggestion:` The hint "an error occurred" won't help the model. Something like "call list_teams for valid ids" lets it recover.
- `nit:` `costs_list` → `costs`; the type already says it's a list.
- `praise:` Nice catch putting the authorization check before the existence check, so outsiders can't probe team names.

## Rules
1. Explain the *why* and link to the ADR or doc that holds it.
2. Review the design first, then the details. If the design is wrong, details don't matter yet.
3. Ask questions when you're not sure; you may be the one who's wrong.
4. Once a month, read back your own review comments. How many were `question:` or `praise:`?
