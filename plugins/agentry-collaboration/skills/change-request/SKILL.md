---
name: change-request
description: Author or triage a change request — a well-framed ask to alter a project, such as a feature request, bug report, or refactor proposal. Use when a user wants help writing a feature/bug/refactor request, or judging, prioritizing, or deciding on an incoming request.
---

# Change Request

A *change request* is a well-framed ask to alter a project: a feature request, bug report, or refactor proposal. This skill helps on both sides of that ask — **authoring** a clear request and **triaging** an incoming one — using one shared rubric. The same request is executed by whoever picks it up, a human contributor or an AI agent; who executes it does not change the request. This skill covers the request itself (a Why-focused input), not the downstream implementation or execution handoff.

Follow these principles:
- **State Why, not How.** Describe the problem and the desired outcome; leave the implementation to the party doing the work. Prescribing a solution hides the real need and rules out better options.
- **Quantify the pain.** Back the problem with evidence — frequency, time cost, blast radius, money — so its importance can be judged, not guessed.
- **Make acceptance result-oriented.** Define success as observable behavior or outcomes, not internal mechanisms or specific APIs.
- **Bound the scope.** Say what is in and, explicitly, what is out (non-goals), so the request cannot quietly sprawl.
- **Pick the right form.** Match the artifact to the intent (feature vs bug vs refactor) and the venue to the stakes (issue vs discussion vs RFC vs PR).
- **Judge the request, not the delivered implementation.** Triage decides whether an ask is worth doing and well-framed; reviewing the code that fulfills it is a separate job.

## When to use

Use this skill when the task is to:
- write a feature request, bug report, or refactor proposal for a project;
- turn a rough need into a well-framed request an executor can later pick up;
- decide whether an incoming request is worth doing and well-formed;
- prioritize a request or determine what missing information it needs.

## Expected input

Gather as much of the following as available:

- **Authoring** — the underlying problem or need; the context (project, component, who is affected); current pain and any evidence for it; constraints, deadlines, or prior workarounds.
- **Triage** — the request text (pasted, a file path, or a link the user provides); the project's existing requests or backlog for duplicate-checking; any conventions (`CONTRIBUTING`, issue templates, RFC process) and priority signals that apply.

If the request type is unclear, infer the most likely one from the input and state the assumption; ask only when the choice materially changes the artifact.

## Request types

Classify the ask before writing or judging it — each type emphasizes different fields of the shared rubric. See `references/request-types.md` for the full taxonomy, the concept distinctions (Feature Request vs Problem Statement / Proposal-RFC / PRD), and the form-selection decision tree.

| Ask | Type | Core question |
| --- | --- | --- |
| Add or change a capability | Feature Request | "What capability is missing?" |
| Something is broken | Bug Report | "What is not working?" |
| Improve internal quality, behavior unchanged | Refactor Proposal | "What blocks maintenance or evolution?" |

A change request is a Why-focused input: it states the problem and the desired outcome, not how to build it. See `references/request-types.md` for how the request hands off downstream.

## Workflow

Pick the path from the task, then converge on the shared rubric.

### Authoring path

1. **Classify the request type** using the table above and `references/request-types.md`. If the ask mixes a bug fix with a design change, split it into separate requests.
2. **State the problem (Why, not How).** Describe the situation and pain, quantified where possible. Do not lead with a solution.
3. **Define the desired outcome and result-oriented acceptance criteria.** Write success as observable behavior. Keep implementation-level thresholds out unless they are a hard requirement you own.
4. **Choose the form and venue** with the decision tree in `references/request-types.md` (issue vs discussion vs RFC vs direct PR; private disclosure for security).
5. **Fill the matching template** from `assets/` and set explicit non-goals. Keep detail proportional to complexity — a one-line ask does not need a full template.

### Triage path

1. **Check for prior art.** Search existing requests for duplicates or related discussion before evaluating; if it duplicates an open request, mark it and point there.
2. **Judge against the rubric.** Is the problem real and quantified? Is the scope bounded? Are the acceptance criteria result-oriented rather than locked to one implementation? Is this the right form and venue?
3. **Decide.** Assign one decision — **accept**, **reject**, **needs-info**, or **duplicate** — with a priority and a brief rationale. For *needs-info*, name the specific rubric fields that are missing. See `references/triage.md`.

### Converge: the rubric

Both paths turn on the same lens (the principles above): authoring builds a request that satisfies the rubric; triage measures a request against it.

## Output

- **Authoring** — the completed change-request artifact in Markdown (from the matching template), ready for the user to file or post. Note the chosen type and venue, and call out any rubric field left thin because the input did not cover it.
- **Triage** — the decision (accept / reject / needs-info / duplicate) with priority and rationale, tied to the rubric. For *needs-info*, list the exact questions or fields the requester must supply.

## References

- `references/request-types.md`: the request taxonomy, concept distinctions (Feature Request vs Problem Statement, Proposal/RFC, PRD), and the form-and-venue decision tree.
- `references/triage.md`: the triage decision framework — decision states, duplicate and needs-info handling, and priority signals.
- `assets/feature-request.md`, `assets/bug-report.md`, `assets/refactor-proposal.md`: fill-in templates for each request type.
