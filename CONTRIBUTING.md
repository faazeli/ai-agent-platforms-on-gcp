# Contributing

Thank you for helping keep this course accurate. The stack moves quickly, so reports from people working through the labs are the most valuable contributions.

## Reporting a broken lab
Open an issue with the **Broken lab** template: the phase and lab, the command you ran, the full error, and your versions (`python --version`, `pip list | grep -i -E "fastapi|fastmcp|adk|langgraph"`, `java -version`, `tofu version`).

## Proposing a change
1. Fork, branch, and make the change in **both** `starter/` and `solution/` when it affects code the two share (tests, models, plumbing).
2. Run the course checks: `make test` (and `make lint` if you have the tools).
3. Keep the starter failing only where a lab expects it: a starter's TODOs should be the only reason its tests fail.
4. Update the phase README if behaviour or commands change, and the versions table in the root README if you bumped something.

## Style
- READMEs: short sentences, concrete commands, a "Check" after each lab.
- Code: typed, small, commented where the *why* isn't obvious; offline-testable (inject clients, use fakes).
- Never commit secrets, real billing data, or project ids.
