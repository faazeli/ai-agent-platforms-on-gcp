# Proposal: adopt FOCUS as our internal cost schema

**Author:** (you) · **Date:** 2026-10-20 · **Decision needed by:** 2026-11-15 · **Decider:** Head of Platform

## Problem
Our three providers (GCP, a SaaS observability vendor, an on-prem chargeback feed) each use different column names and cost definitions. Two analysts spend about 3 days a month reconciling them by hand, and team dashboards disagree with finance by up to 8% because some show billed cost and others amortized cost.

## Options
| Option | What it costs | What it gets us | Risk |
| --- | --- | --- | --- |
| Do nothing | ~6 analyst-days/month | Nothing new | Disagreements keep eroding trust in the numbers |
| Custom internal schema | ~6 engineer-weeks + upkeep | Fits us exactly | We maintain a standard alone; new vendors need custom mapping |
| Adopt FOCUS | ~4 engineer-weeks; GCP and many vendors export it natively | A shared vocabulary; vendor exports drop in; FinOps Foundation guidance applies directly | Our on-prem feed needs a mapping we own |

## Recommendation
Adopt FOCUS. Most of our spend can arrive already in FOCUS, and EffectiveCost versus BilledCost gives teams and finance one definition each, ending the 8% disagreement.

## What it costs
Four engineer-weeks this quarter (one engineer), plus a half-day workshop for the analysts. We pause the custom dashboard rewrite to make room.

## Risks and how we'd notice
- On-prem mapping is harder than expected → if the mapping isn't validated against two months of data by week 3, we scope it out of phase one.
- Teams keep old dashboards → we track dashboard usage weekly and retire the old ones at 80% migration.

## The ask
Approve one engineer for four weeks starting 2026-11-01, and a 30-minute slot at the December all-hands to show the result.

---
| Person | Their concern | What changed |
| --- | --- | --- |
| Finance lead | "Will my month-end numbers change?" | Added: finance reports stay on BilledCost, explicitly |
| Analyst | "Who maintains the on-prem mapping?" | Added the risk and the week-3 checkpoint |
