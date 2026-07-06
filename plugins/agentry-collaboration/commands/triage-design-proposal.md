---
description: Triage an incoming design proposal — judge it against the design rubric and decide accept, revise, reject, or needs-info with a rationale.
argument-hint: "[the design proposal to triage: pasted text, a file path, or a link]"
---

# Triage Design Proposal

Use this command when the user wants to judge or decide on an incoming design proposal. It evaluates the design itself — whether the approach is sound and well-framed — not the code that would implement it, and not whether the underlying request was worth accepting.

## Inputs

- `[the design proposal to triage]`: The design to evaluate, as pasted text, a file path, or a link the user provides. If omitted, ask the user for the design to triage.
- The accepted request it answers, related past designs, or project conventions (RFC process, ADR format, design template) may be treated as source context when the tool provides them.

If the design is ambiguous or partial, prefer a **needs-info** decision that names the missing sections over guessing.

## Workflow

1. Follow the `design-proposal` skill's **triage path** as the authoritative procedure, including its rubric and `references/triage.md`.
2. Confirm the Why is settled: check the design answers an accepted request. If the problem's validity or priority is still open, send it back to the change-request stage instead of triaging the design.
3. Judge the design against the rubric: anchored to the Why, approach justified over real alternatives, impact bounded, migration and rollback addressed, risks surfaced, and the right weight.
4. Assign one decision — accept, revise, reject, or needs-info — with a rationale tied to the rubric.

## Constraints

- Judge the design, not the delivered code; reviewing the implementation is a separate downstream stage.
- Do not re-litigate the Why; accept the underlying request as given and judge only the How.
- Do not modify, close, or comment on anything on an external tracker; return the decision for the user to act on.

## Output

Return the decision (accept / revise / reject / needs-info) with a rationale tied to the rubric. For revise, list the exact sections or changes required. For reject, give the reason and any alternative direction. For needs-info, name the missing sections that block evaluation.
