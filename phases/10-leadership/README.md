# Phase 10 — Coaching, mentoring and influence

| Time | Cloud cost | Builds on | You produce |
| --- | --- | --- | --- |
| All along (≈ 1–2 h per phase), focus in weeks 26–27 | $0 | Every phase | A mentee who shipped, a proposal that changed a decision, a template others use, and an evidence log |

## Why this phase matters

Senior and staff roles are judged less by what you build than by what you make possible for others. That impact is practised the same way as code: small reps, real feedback, visible artifacts. This phase is not saved for the end. Do one rep per technical phase, using the work you just did as the material, then spend the last two weeks on the two biggest reps (the proposal and the golden path).

## You will learn

- Writing decisions down so they scale beyond meetings (ADRs, one-page proposals)
- Teaching: "I do, we do, you do"; collecting and acting on feedback
- Mentoring with the GROW model, and measuring success by the mentee's output
- Code review as coaching
- Influence without authority: stakeholder maps, pre-wiring, objection handling
- Multiplying impact with a golden-path template
- Running blameless postmortems and drills

## Before you start

Read (pick two now, the rest over the course):

- Will Larson, *Staff Engineer* (especially "Writing engineering strategy" and "Getting in the room")
- Camille Fournier, *The Manager's Path* (the mentoring and tech lead chapters)
- L. David Marquet, *Turn the Ship Around!* (intent-based leadership)
- Michael Bungay Stanier, *The Coaching Habit* (seven questions, the basis of the mentoring guide)
- [Google SRE: Postmortem culture](https://sre.google/sre-book/postmortem-culture/)

## What's in this folder

```
templates/proposal-one-pager.md    Rep 10.5   (+ a worked example in examples/)
templates/brown-bag-plan.md        Rep 10.2
templates/mentoring-guide.md       Rep 10.3   (GROW, a four-week plan for Phase 1)
templates/code-review-guide.md     Rep 10.4   (comment labels, CostPilot examples)
templates/stakeholder-map.md       Rep 10.5
templates/golden-path-checklist.md Rep 10.6
templates/postmortem-template.md   Rep 10.7   (+ four drill scenarios)
templates/reflection-journal.md    weekly
templates/leadership-evidence.md   your running record
```

The ADR template every phase uses is at [docs/adr-template.md](../../docs/adr-template.md).

## When to do each rep

| After phase | Rep | Material you already have |
| --- | --- | --- |
| 1 | 10.1 Decisions in writing | ADR 0001 (error format) |
| 2 | 10.2 Teach a phase | The dry-run comparison; Problem Details |
| 3 | 10.4 Code review as coaching | Review someone's MCP tool against the tool checklist |
| 4 | 10.1 again | ADR 0004 (gateway): send it to a senior and a junior reviewer |
| 5 | 10.2 again | The live injection drill makes a gripping 45 minutes |
| 1 → 4 (in parallel) | 10.3 Mentor someone through Phase 1 | The Phase 1 starter and tests |
| 6 | 10.5 Influence (small) | Propose no-key service accounts for one existing service |
| 8 | 10.5 Influence (big) | Your sizing ADR or "adopt FOCUS" |
| 9 | 10.6 Golden path | Phases 3 + 6 + 9 as a template repo |
| 9 | 10.7 Postmortem drill | Drill scenarios in the postmortem template |

## The reps

### Rep 10.1 — Decisions in writing
You have written an ADR per phase. Send two of them for review, one to someone more senior and one to someone more junior, and revise based on what each questioned. Writing is how ideas scale beyond meetings, and reviewers from both directions catch different gaps.

### Rep 10.2 — Teach a phase
Run a 45-minute brown bag (`templates/brown-bag-plan.md`). Problem Details (Phase 1) and FOCUS (Phase 2) work well because everyone hits those problems. Use "I do, we do, you do": demo, build one together, then a 10-minute exercise in pairs. Collect three pieces of anonymous feedback and act on one, visibly.

### Rep 10.3 — Mentor one person through Phase 1
Meet weekly for four weeks (`templates/mentoring-guide.md`). Use GROW, ask more than you tell, and count it. Your success metric is their pull request merged, not yours.

### Rep 10.4 — Code review as coaching
Label every comment (`blocking`, `question`, `suggestion`, `nit`, `praise`), explain the why, and link the ADR (`templates/code-review-guide.md`). Once a month, read back your own comments: how many were questions? How many were praise?

### Rep 10.5 — Influence without authority
Write a one-page proposal (`templates/proposal-one-pager.md`; see `examples/proposal-adopt-focus.md`). Lead with a problem that has a number, compare options including "do nothing", and end with a precise ask. Map stakeholders (`templates/stakeholder-map.md`) and pre-wire with the people who could say no *before* any group meeting. Log each objection and what you changed.

### Rep 10.6 — Build a golden path
Turn Phases 3, 6 and 9 into a template repository that lets another team ship a secure MCP server to GKE in one day (`templates/golden-path-checklist.md`). Measure adoption: how many teams used it, and how long they took to first deploy.

### Rep 10.7 — Run a blameless postmortem
Break something on purpose in dev (four ready scenarios are in `templates/postmortem-template.md`: an exhausted gateway budget, a failing eval gate under deadline pressure, a retired model, a broken audit sink). Run the incident, then write the postmortem focused on systems, not people. Track the action items to done.

## Done when

- [ ] A person you mentored has shipped something (merged PR, deployed service)
- [ ] A proposal you wrote changed a team decision, and your pre-wiring log shows how
- [ ] A template you built is used by at least one other team
- [ ] `templates/leadership-evidence.md`, copied into your repo, has an entry for every rep

## Write it down

Your evidence log *is* the write-up for this phase. Keep it next to your ADRs.

## Teach it

By now you have taught at least twice. For the capstone demo (see the course README), present one technical decision and one leadership outcome side by side: what you built, and who else can now build on it.
