# Scenario Authoring

How to write scenarios that measure a real behavioral effect instead of confirming an after-state that would pass anyway. Read this when defining or revising scenarios for an authoring artifact.

## Start from an observed baseline failure

A scenario is worth writing only when you can name the specific way the agent goes wrong today, in observable terms. "The artifact could be clearer" is not a scenario. "The agent reads existing review threads before deriving findings from the diff" is.

Record three things for every scenario:

- **Baseline failure** — the wrong observable behavior, stated concretely.
- **Rationale or pressure** — why the agent tends toward it: a tempting shortcut, ambiguous input, noisy context, or urgency.
- **Expected behavior** — what the corrected artifact should do instead, expressed as checks.

If you cannot name the baseline failure, do not invent one. Discovering an unknown weak behavior is exploratory work; a regression scenario encodes a failure you can already describe.

## Build realistic task pressure

An artifact that behaves well only on a frictionless prompt is not proven. Put the failure mode under pressure the way real use does:

- include distracting or stale context that invites the wrong shortcut;
- give an ambiguous instruction when the correct behavior is to ask or to pick the safe default;
- provide a fixture where the tempting-but-wrong path looks locally reasonable.

The before side should reproduce the baseline failure under this pressure; the after side should resist it. A scenario whose before side already passes proves nothing about the change.

## Select check types by failure mode

Match the check to how the behavior goes wrong. Prefer deterministic checks whenever they are strong enough, because they are settled by computation over the captured output (the `scripts/check_output.py` matcher), not by a model, so they add no rubric-evaluator variance.

| Failure mode | Check type |
| --- | --- |
| A required or forbidden output element | required-text / forbidden-text |
| A structured or machine-readable field | json-field |
| A pattern with variation | regex |
| A sequence or ordering failure | ordered phrases |
| Semantic behavior: intent, ordering of *reasoning*, scope adherence | rubric |

Rubric checks carry a versioned natural-language criterion and demand a rationale and an evidence quote from the produced output. Tie every rubric check to one clear expected observable behavior; a vague criterion produces vague judgments. Record the rubric-evaluator identity so a rubric result is attributable.

## Keep runs side-effect-free

Fixtures are the only external state a scenario may depend on. Never let a scenario reach a real remote, tracker, or credential.

- Provide inputs as fixture files (diffs, comment threads, config snapshots).
- Represent any publish, network, or mutation action as a proposed output or a write to a run-local fake sink, never a real call.
- Keep reusable, scenario-specific mock executables as source under the scenario's `tool-mocks/`. They are copied into the run's sandbox before execution and are never run in place.
- A confirmation turn authorizes only the simulated or sandboxed action.

## Keep expected answers away from the producer

The producer must not see the expected answers, or it will pattern-match them instead of behaving naturally. The self-contained case carries the full check definitions (including expected criteria) for the rubric evaluator, so keeping them from the producer is the orchestrator's runtime duty: it builds the producer packet from the case's prompt, context, fixtures, and artifact and withholds each check's expected text, supplying the criteria only to the independent rubric evaluator. Your part as a scenario author is to make that possible — do not restate the expected behavior verbatim in the prompt or context, or it leaks into the producer packet no matter how carefully the orchestrator filters the checks.

## Merge or split scenarios

Prefer one scenario with several checks when the artifact, prompt, context, fixtures, baseline failure, and before/after refs are all the same. Multiple checks on one scenario keep the produced output shared, cut token cost, and still report granular per-check failures.

Split into separate scenarios only when the setup or the behavioral pressure differs — a different fixture, a different prompt, or a different failure mode. Do not merge scenarios that need different pressure into one session, since that contaminates the produced output.

## Multi-turn scenarios

Most scenarios are single-turn. Use ordered turns when the correct behavior is to ask for confirmation or request missing information before acting. Turns run in declared order and are stateful only within that scenario. A check may target a specific turn, the final output, or the full transcript. Asking for clarification or confirmation can be the expected behavior rather than a harness failure — but the side-effect boundary still holds: even after a confirmation turn, use a fixture or fake sink rather than mutating real state.

## Choose an evidence tier

Set the tier to how much the result must be trusted: exploratory for early iteration (one repetition, provisional), normal for routine regression (three repetitions, 3 of 3 stable), acceptance for evidence that gates a claim (five repetitions, at least 4 of 5 stable). An acceptance witness should stably reproduce the known-bad before behavior and stable after behavior before you claim improvement. Override the default repetitions or threshold only with a recorded reason.
