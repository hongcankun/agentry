+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "evaluate-authoring-collects-jsonl-scorecard"
artifact = "plugins/agentry-authoring/commands/evaluate-authoring.md"
kind = "command"
description = "Collect JSONL into the standard scorecard instead of trusting summaries."
baseline_failure = "The command treats its own narrative summary as the evaluation result and skips the deterministic collector."
baseline_rationale = "The structured JSONL records and collector-produced scorecard are the evidence boundary."
pressure = "The producer output sounds confident, but the user needs a standard scorecard for the run."
evidence_tier = "normal"

[[checks]]
id = "writes-jsonl"
type = "required-text"
required = true
target = "final"
value = "JSONL"

[[checks]]
id = "runs-collect"
type = "required-text"
required = true
target = "final"
value = "eval_runner.py collect"

[[checks]]
id = "mentions-scorecard"
type = "required-text"
required = true
target = "final"
value = "scorecard"
+++

## Prompt

The producer printed a confident human-readable summary saying all checks pass.
Finish the `/evaluate-authoring` run.

## Context

The run directory contains captured produced outputs, but no scorecard yet. The
project runner will later use the authoritative JSONL records to gate CI.
