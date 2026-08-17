---
description: Execute a behavioral evaluation of an authoring artifact — from a prepared run manifest or a directly scoped scenario — producing outputs and writing structured JSONL result records.
argument-hint: "--run <manifest.json> | --scenario <scenario.md> [--scenario <scenario.md>...] --target tool:model [--mode rendered|sandbox] [--evaluator tool:model] [--artifact-root DIR] [--run-dir DIR] [--evidence C/T]"
---

# Evaluate Authoring

Use this command to execute a behavioral evaluation of an authoring artifact — a skill, command, subagent, or rule — against prepared scenarios, and to write structured result records a project runner can collect. It is the standard orchestrator for active-agent evaluation runs and a thin wrapper around the `authoring-evaluation` skill.

This command orchestrates: it reads each self-contained case, builds the producer packet (the prompt handed to the producer), runs the producer, then runs the rubric evaluator, and writes structured results. The producer and the rubric evaluator should be independent agents or subagents, so the party that generates output is not the party that judges it. The command does not decide pass/fail gate status; it emits the standard scorecard through the deterministic collector, while a project runner may re-collect from the authoritative JSONL to set CI exit status.

## Inputs

- `[--run <manifest.json>]`: Path to a prepared run manifest. The manifest is an index of scenarios and their cases; each case is self-contained (producer inputs plus full check definitions and execution params).
- `[--scenario <scenario.md>]`: Scenario Markdown file to prepare when no run manifest is supplied. Repeat for multiple scenarios. In direct mode, pass these to the `authoring-evaluation` skill's `scripts/eval_runner.py prepare --scenario ...` command.
- `--target tool:model`: Producing target for direct runs. Treat this as a directive from the human invocation, not an identity to introspect from yourself. If no manifest is supplied and `--target` is omitted, stop and ask the user for the target rather than guessing.
- `[--mode rendered|sandbox]`: Execution mode for direct runs. Default to `rendered` only when the invocation omitted mode; otherwise forward the mode from the invocation.
- `[--evaluator tool:model]`: Optional pinned rubric evaluator for direct runs. Treat it as a directive from the invocation and forward it to prepare.
- `[--artifact-root DIR]`: Optional root for resolving scenario artifact paths in direct runs. Default to the current working directory.
- `[--run-dir DIR]`: Optional run directory for direct runs. Default to the skill runner's `./run`.
- `[--evidence C/T]`: Optional evidence override for direct runs, as consistent/total repetitions.

If the run manifest or a case is missing, unreadable, or carries an unknown schema marker or unsupported major version, stop and report it rather than guessing.

## Workflow

1. Load and follow the `authoring-evaluation` skill, including its scenario model, check semantics, comparison contract, safety constraints, and result schema; if unavailable, stop.
2. Determine the run source:
   - If `--run` is supplied, read that prepared manifest; its parent directory is the run directory for result records and collection.
   - If `--run` is omitted, require at least one `--scenario <scenario.md>` and `--target tool:model`. Run `scripts/eval_runner.py prepare --scenario <scenario.md> ... --target <tool:model> --mode <mode> [--evaluator <tool:model>]` from the loaded `authoring-evaluation` skill, forwarding `--artifact-root`, `--run-dir`, and `--evidence` when the invocation provides them. Then read the generated manifest.
3. For each referenced case, build the producer packet from the case's prompt, context, turns, fixtures, and artifact files. Withhold the case's expected criteria (each check's `expect`) from the producer packet: leakage prevention is your runtime duty, since the case carries the full checks for judging.
4. Run the producer as an independent agent or subagent to generate output under the scenario's task and pressure, and **capture that output as a file** under the case's `produced/` directory. Realize the producer as the case's `target` tool and model: pin the model through a subprocess invocation with a model flag or a runtime spawn-call model override — not a subagent definition file, which inherits your model. For a true-activation run, drive the artifact through the sandbox contract in the `evaluation-sandbox` skill (isolated home, artifact installed, tool mocks staged); for a rendered run, have the producer return proposed outputs and fake-sink writes without real activation, using a minimal clean home when it runs as a separate tool process.
5. Settle each check against the captured produced output. Decide **deterministic** checks (`required-text`, `forbidden-text`, `regex`, `json-field`, `ordered`) by computation — run the `authoring-evaluation` skill's `scripts/check_output.py` per check rather than judging the operand by model — and judge **rubric** checks with a separate independent rubric evaluator, realized as the case's pinned evaluator when set (else your own runtime), at the named tool and model. The rubric evaluator needs no sandbox and no artifact — it reads only the captured output and the criterion. Record `pass`, `fail`, or `needs-review` with a rationale and an `evidence` `{source_path, quote}` that comes from that captured output, plus the `producer` and `produced_output` reference. If a required rubric result is missing, ambiguous, conflicting, or unverifiable, record `needs-review`, not pass.
6. Repeat each scenario for the case's repetition count and record every repetition (each referencing its own captured output); do not pre-aggregate.
7. Write JSONL result records in the shared schema under the run's results directory. This is the source of truth even when you also print a human-readable summary.
8. Run `scripts/eval_runner.py collect <run-dir>` from the loaded `authoring-evaluation` skill to emit `scorecard.md` and `scorecard.json` from the JSONL records. Treat the scorecard's `status` field as the command's human-facing summary; do not convert it into a pass/fail exit gate.

## Constraints

- Produce before you judge, and capture producer output first. Do not hand-write result records from the manifest or case files: every check record must reference a real captured produced output whose evidence quote appears in it, or collection rejects it. If you cannot run a producer, stop and say so — do not synthesize results.
- Cause no live external side effects. Fixtures are the only allowed external state; represent publication, network, or tracker actions as drafts or fake-sink writes, and treat any real remote call, production credential use, or write outside the run directory as a failed or `needs-review` run.
- A confirmation turn authorizes only the simulated or sandboxed action, never real remote state.
- Do not parse or trust the producer's narrative in place of a check. Compute each deterministic check against the captured output and judge each rubric check explicitly; record the evidence for both.
- Keep the same rubric evaluator across both sides of a scenario and target where practical, so rubric-evaluator variance does not become the measured delta.
- Record producer target identity and rubric evaluator identity separately. The pipeline's judges are automated — an agent for rubric checks, the deterministic matcher for deterministic checks; do not hand-author judgments. Human involvement is oversight of the resulting scorecard, not a recorded per-check evaluator.
- Write JSONL result records even when you also produce a human-readable summary, so the run can be collected later.

## Output

Write structured JSONL result records and emit the standard scorecard. In the final response, point to the JSONL results and the generated scorecard, reporting:
- per-check outcome with rationale and evidence quote;
- per-scenario outcome across repetitions, per side and target;
- producer tool/model and execution mode, and the rubric evaluator identity;
- any required checks left `needs-review` and why;
- the scorecard `status`, without treating it as this command's CI gate.
