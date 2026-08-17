+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "authoring-evaluation-deterministic-checks-by-computation"
artifact = "plugins/agentry-authoring/skills/authoring-evaluation/SKILL.md"
kind = "skill"
description = "Settle deterministic checks with the bundled matcher."
baseline_failure = "The agent asks a model to decide deterministic required-text or regex checks."
baseline_rationale = "Deterministic checks are reproducible only when computed against the captured output."
pressure = "The run contains only deterministic checks, and the user asks whether a model can judge them directly."
evidence_tier = "normal"

[[checks]]
id = "uses-check-output"
type = "required-text"
required = true
target = "final"
value = "check_output.py"

[[checks]]
id = "says-by-computation"
type = "required-text"
required = true
target = "final"
value = "by computation"
+++

## Prompt

This evaluation case has a `required-text` check and a `regex` check. Can I ask
the rubric evaluator model to judge both checks from the output, or is there a
deterministic step I should run?

## Context

The produced output has already been captured as a file. The case carries the
full check definitions, including the deterministic operands.
