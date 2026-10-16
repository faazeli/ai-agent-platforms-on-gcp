# Postmortem: <title> (blameless)

**Date:** · **Duration:** · **Severity:** · **Author:** · **Status:** draft | reviewed

## Summary
Two or three sentences: what happened, impact, how it was resolved.

## Impact
Who was affected, how, for how long. Numbers: failed questions, minutes of degraded service, money.

## Timeline (UTC)
| Time | Event |
| --- | --- |
| | Detection: how did we find out? (alert, user, luck?) |
| | |

## Root causes and contributing factors
Focus on systems and conditions, not people. Ask "how did our system make this the easy mistake?"

## What went well
## What went poorly
## Where we got lucky

## Action items
| Action | Type (prevent / detect / mitigate) | Owner | Due |
| --- | --- | --- | --- |

---
## Drill scenarios for Rep 10.7 (run in dev)
1. **Expired gateway budget:** set an agent's virtual key budget to $0.01. What do users see? Does anything alert?
2. **Failing eval gate in a hurry:** someone needs a prompt fix shipped today and the gate fails. What's the process?
3. **Model retired:** point the `smart` alias at a non-existent model id. Do fallbacks hide it? Should they?
4. **Audit sink broken:** remove the sink writer's permission. How long until someone notices missing audit entries?
