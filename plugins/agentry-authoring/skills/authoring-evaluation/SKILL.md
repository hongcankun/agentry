---
name: authoring-evaluation
description: Evaluate whether a change to an authoring artifact (skill, command, subagent, or rule) improves agent behavior, using fixture-backed scenarios, structured results, and before/after pass/fail deltas. Use when a maintainer wants to prove a behavioral effect, guard against regressions, or attach evaluation evidence to a change.
---

# Authoring Evaluation

Judge whether editing an authoring artifact — a skill, command, subagent, or rule — makes the agent behave better, and by how much. Static review checks whether content reads well; this evaluates observable behavior on real tasks and produces a comparable before/after result.

The workflow is a structured-data pipeline with four roles, so behavior claims are measured, not asserted:

- **Project runner** — repository-specific code that discovers scenarios, resolves artifacts and refs, writes a run manifest (an index) and self-contained cases, invokes or coordinates an orchestrator, validates result records, aggregates them, and renders a scorecard. It never judges behavior itself.
- **Orchestrator** — the active agent that reads each case, constructs the producer packet — the prompt handed to the producer, with the expected criteria withheld — runs the producer, then runs the rubric evaluator, and writes structured result records. It directs the workflow; it does not itself produce or judge.
- **Producer** — an independent agent or sandboxed tool/model runtime that generates observable output from the constructed prompt. It is kept separate from the orchestrator and rubric evaluator so it never sees the expected criteria.
- **Rubric evaluator** — an independent agent that judges semantic checks from produced output. Keeping it separate from the producer means the party that generates output is not the party that grades it.

The pipeline's judges are automated — an agent for rubric checks, computation for deterministic checks. Human involvement is oversight *of* the resulting scorecard (deciding whether to trust it and ship the change), not a recorded per-check evaluator.

The stable boundary between the runner and the orchestrator is structured data, never free-form prose. The runner must not parse an agent's narrative to infer pass/fail; it reads structured result records and aggregates them.

## When to use

Use this skill when you want to:

- prove that an artifact change improves a target behavior before shipping it;
- guard an artifact against regressing behavior that already worked;
- attach comparable before/after evidence to a change instead of "reads better";
- capture intended behavior as reusable scenarios with expected observable outcomes.

This sits alongside static authoring review and packaging validation; it does not replace them. Deciding whether the improved artifact is well written, and reviewing the change that carries it, are separate stages.

## Core model

**Scenario.** A fixture-backed task that names the baseline behavior it is meant to change, applies realistic pressure, and lists checks with expected observable outcomes. Each scenario names its baseline failure so the before/after result proves an artifact effect rather than only an after-state pass.

**Check.** A single expected observable behavior, either deterministic (required/forbidden text, regex, structured field, ordered phrases) or rubric (versioned natural-language criterion judged from produced output, with a rationale and evidence quote). Prefer deterministic checks whenever they are strong enough; use rubric checks for semantic behavior like ordering and intent. Each check targets the final output, a specific turn, or the full transcript, and is required or optional.

**Side and target.** Evaluation runs a scenario against a *side* and a *target* (the producing tool/model, named as `tool:model`). A single-side run uses `baseline`; comparison runs compare `variant` against `baseline`. Compare baseline/variant only within the same target. Multiple targets form a matrix; cross-target summaries are descriptive and must not imply a universal improvement when only one target improved.

**Evidence tier and repetition.** LLM output is nondeterministic, so repetition count depends on how much the result must be trusted:

| Tier | Repetitions | Stable required-check outcome | Use for |
| --- | --- | --- | --- |
| Exploratory | 1 | provisional (label as such) | early authoring iteration |
| Normal | 3 | 3 of 3 consistent | routine regression checks |
| Acceptance | 5 | at least 4 of 5 consistent | evidence that gates a claim |

A required check below its stability threshold collapses the scenario to `needs-review`, never pass. A scenario may override repetitions or threshold in its metadata, and a run may override the bar for every scenario at once (a `consistent/total` pair); either way the threshold may not exceed the repetitions, and the scorecard reports the effective values and notes a run-time override.

## Workflow

### 1. Name the baseline behavior

State the specific behavior the change should fix, in observable terms, plus the rationale or pressure that triggers it. If you cannot name a concrete before-behavior, you are not ready to write a scenario — see `references/scenario-authoring.md`.

### 2. Write scenarios

Author one or more scenarios with fixtures, pressure, and checks that match the baseline failure mode. Prefer one scenario with multiple checks when the artifact, prompt, context, fixtures, baseline failure, and refs are the same; split scenarios only when the setup or behavioral pressure differs. `references/scenario-authoring.md` covers check selection, fixtures and fake sinks, keeping expected answers away from the producer, and multi-turn scenarios. `references/project-runner.md` documents the reference project-runner contract, scenario file format, and schemas.

### 3. Prepare the run

Have the project runner resolve the scoped scenarios, materialize the requested baseline side and optional variant side, and write a run manifest plus one self-contained case per scenario, side, and target. The manifest is an index; each case carries the producer inputs and the full check definitions and execution params, so one case is a complete execution unit. The case holds the expected criteria for judging — withholding them from the *producer* is the orchestrator's runtime duty when it builds the producer packet, not a property of the case file. Keep runs side-effect-free (see Safety).

### 4. Produce and judge

Run the orchestrator against the manifest. For each case, the orchestrator composes the producer packet per the case's orchestrator brief while withholding the expected criteria, runs the producer to generate output under the scenario's task and pressure, and **captures that output as a file**. It then settles each check against the captured output — deterministic checks by computation, rubric checks by the rubric evaluator (see below) — recording an outcome, rationale, and an evidence quote that comes from that output. Keep the producer and the rubric evaluator as independent agents or subagents, so the party that generates output is not the party that grades it. Use the same rubric evaluator across both sides of a scenario and target where practical, so rubric-evaluator variance does not become the measured delta. Every result record references its captured produced output; a result with no captured output behind it is not valid evidence and will be rejected at collection. The orchestrator writes structured result records; that data is the source of truth even when it also prints a human summary.

**Settle deterministic checks by computation, not by reading.** A `required-text`, `forbidden-text`, `regex`, `json-field`, or `ordered` check is decided by running its operand against the captured output as code, so the outcome is reproducible and free of model variance — not by asking a model whether the pattern matched. Run `scripts/check_output.py` (a self-contained, stdlib-only matcher) against the captured file per check; it emits the outcome and an evidence quote that is a genuine substring of the output (the matched span, or a head anchor when nothing matched, including a `forbidden-text` pass). Only rubric checks go to the rubric evaluator, which judges the versioned criterion from the same captured output and records its rationale and evidence quote. Do not substitute a model judgment for a deterministic operand.

**Realize the producer as the case `target` and the judge as the case's pinned evaluator (or the orchestrator's own runtime when none is pinned), each at the named tool and model.** Pin the model through a mechanism that actually sets it: a subprocess invocation of the tool with a model flag, or a runtime spawn-call that takes a model override. Do not rely on a subagent *definition file* to choose a model — those inherit the caller's model. An in-process subagent is only correct when the required model equals the orchestrator's current model, or when the runtime's spawn call accepts a model override. The recorded `producer` and `evaluator` identities must be the tool and model that actually ran, and collection cross-checks them against the case's target and pinned evaluator.

Isolation differs by role and mode, because only the producer activates the artifact:

- **Producer, sandbox mode** — run in the isolated per-execution sandbox (own home/config, artifact installed, tool mocks staged) so the target tool loads and activates the artifact itself; see the `evaluation-sandbox` skill.
- **Producer, rendered mode** — no artifact is installed (the guidance is inlined into the prompt); when the producer runs as a separate tool process, give it a minimal clean home so it does not inherit the orchestrator's installed skills, agents, or rules.
- **Rubric evaluator, either mode** — needs no sandbox and no artifact: it only reads the captured produced output plus the checks and returns a verdict. A fresh judge that sees the captured output but not the producer's live session is what keeps judgment independent.

### 5. Collect and compare

Have the project runner read the result records, validate their schema and provenance (each check must reference an existing captured output whose quote it cites, with no duplicate repetitions), aggregate per-check and per-scenario outcomes, compute baseline/variant deltas when a variant side exists, and render a scorecard. Collection also runs integrity cross-checks derived from the records: the producer must be the case's target and the judge the pinned evaluator (a differing recorded model is flagged), and a scenario's baseline and variant sides must be judged by the same evaluator. Any integrity finding marks the run `invalid`, a stronger signal than a failing check. Pass/fail delta is authoritative and a derived pass percentage is for scanability only; see the Comparison contract below for how a variant counts as improved or regressed. Any required `needs-review` check makes the scenario `needs-review`, and an empty or partial run is reported as `no-results`/`incomplete`, never a clean pass.

### 6. Report the evidence

Attach the scorecard to the change. It should show its `status`, per-scenario pass/fail/needs-review, the aggregate counts, baseline/variant improvement and regression counts when applicable, the effective repetitions and stability, the per-target provenance (producer identity, rubric-evaluator identity, and how many checks are backed by a captured output), producer versus rubric-evaluator variance when distinguishable, and any unresolved checks.

## Comparison contract

- **Pass/fail delta is authoritative.** Numeric model scores are not part of the acceptance bar.
- A variant **improves** when baseline fails and variant passes; it **regresses** when baseline passes and variant fails; otherwise it is **unchanged** or, with no baseline result, **newly covered**.
- A scenario with any required `needs-review` check is `needs-review`, not pass.
- Compare baseline/variant only within the same target.

## Execution modes

- **True-activation sandbox (preferred for evidence that gates a claim).** Install or expose the artifact through the real target tool in an isolated config/home, route external commands to run-local mocks and sinks, capture transcripts and sink writes, and return produced outputs to the same result contract. Higher fidelity; see the `evaluation-sandbox` skill for the shared isolation and safety contract.
- **Rendered simulation (portable fallback).** Build the producer packet from artifact source and fixtures and ask the producer to return proposed outputs and fake-sink writes. Cheap and portable, useful for early iteration, unsupported tools, and cases where sandbox setup is unavailable, but lower fidelity. It supports evidence that gates a claim only when it reproduces the known-bad before behavior; otherwise the comparison is `needs-review`, not proof of no improvement.

## Safety

Evaluations must avoid live external side effects in both modes.

- Fixtures are the only allowed external state. Represent publication, network, or tracker actions as drafts or planned actions, or route them to a run-local fake sink.
- A confirmation turn authorizes only the simulated or sandboxed action, never real remote state.
- Any attempt to call real remotes, use production credentials, execute scenario-local mock sources in place, or write outside the run directory is a failed or `needs-review` run.

## Rules as first-class artifacts

A rule takes effect as active guidance the tool loads into context, by whatever mechanism that tool uses to decide a rule applies — always-on, path- or scope-based, or context-triggered. Evaluate a rule through that activation path, with whatever scoping or context the tool needs to treat it as active, and never as isolated Markdown divorced from the context that activates it. How you reproduce the activation depends on the mode:

- **Rendered** — there is no live tool, so model the activation as context: render the canonical rule text, plus whatever scoping or surrounding context would make the tool apply it, into the producer's context. Do not require a real global install.
- **Sandbox** — reproduce the activation for real: place the rule where the tool loads rules from in the isolated home, with whatever scoping the tool needs, so it loads into context through the tool's normal path (a home-scoped install, not a global one). This is the same real-load-path fidelity the loadable kinds get.

## References

Read these when needed:

- `references/scenario-authoring.md` — how to write strong scenarios: baseline failures, pressure, check selection by failure mode, fixtures and fake sinks, keeping expected answers away from the producer, and merging versus splitting scenarios.
- `references/project-runner.md` — the reference project-runner workflow, scenario file format, run manifest and result schemas, and comparison semantics.
- `scripts/eval_runner.py` — self-contained, independently versioned prepare+collect frontend for skill-only, single-side runs: `prepare --scenario <scenario.md>` materializes scenarios into a baseline-only manifest and cases, including independent rule files with tool-agnostic rule context, and `collect` emits `scorecard.md`/`.json` from JSONL without setting a pass/fail exit gate. Positional scenario paths are also accepted for simple CLI use; run `python3 eval_runner.py --version` to inspect the runner version.
- `scripts/check_output.py` — self-contained, stdlib-only matcher that settles one deterministic check against a captured output file and prints the outcome plus an evidence quote. Run it per deterministic check during the judge step.

For true-activation runs, use the `evaluation-sandbox` skill, which defines the shared isolation, safe-external-command, capture, and result-handoff contract for running an artifact through a real target tool.
