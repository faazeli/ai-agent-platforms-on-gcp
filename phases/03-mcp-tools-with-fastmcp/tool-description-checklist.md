# Tool description checklist (Lab 3.2)

A model chooses and calls tools using only their names, descriptions and parameter schemas. Review every tool against this list.

## Name

- [ ] A verb and an object: `get_team_cost`, not `team_summary_v1_teams`
- [ ] Unambiguous next to the other tools on the same server

## Description (the docstring)

- [ ] First sentence: what it returns, with units ("EffectiveCost in the billing currency")
- [ ] When to use it, in the user's words ("for 'how much did X spend' questions")
- [ ] When *not* to use it, if another tool is better for a nearby question
- [ ] What an empty result means, so the model doesn't invent an explanation
- [ ] No internal jargon the model can't resolve (table names, ticket numbers)

## Parameters

- [ ] Every parameter has a description with an example value
- [ ] Formats are enforced by the schema (`pattern`, `ge`/`le`), not only described
- [ ] Defaults are safe and cheap (small `limit`, recent dates)
- [ ] Ids say where they come from ("exactly as returned by list_teams")

## Output

- [ ] A typed model, so clients get an output schema and structured content
- [ ] Field names are self-explanatory without the docstring

## Errors

- [ ] Problem Details body with a stable `type`
- [ ] A `hint` that tells the model the next action, or tells it to stop
- [ ] Nothing internal leaks (stack traces, SQL, hostnames)

## Safety

- [ ] `readOnlyHint` is true unless the tool changes something
- [ ] Anything that changes state is a separate tool, so it can be allow-listed and approval-gated (Phase 5)
