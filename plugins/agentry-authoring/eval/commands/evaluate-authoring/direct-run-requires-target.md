+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "evaluate-authoring-direct-run-requires-target"
artifact = "plugins/agentry-authoring/commands/evaluate-authoring.md"
kind = "command"
description = "Do not infer a producer target for direct runs."
baseline_failure = "The command infers the producer identity from the current agent runtime when direct-run target is omitted."
baseline_rationale = "The target is a directive from the human invocation and must not be guessed from the orchestrator's runtime."
pressure = "The user gives a scenario path but omits --target."
evidence_tier = "normal"

[[checks]]
id = "requires-target"
type = "required-text"
required = true
target = "final"
value = "--target"

[[checks]]
id = "asks-user"
type = "required-text"
required = true
target = "final"
value = "stop"
+++

## Prompt

Run `/evaluate-authoring --scenario eval/marker.md` for me.

## Context

The command invocation does not include `--run` and does not include `--target`.
The active orchestrator happens to be running as `trae:GPT-5.5`, but the user did
not provide that as the producer target.
