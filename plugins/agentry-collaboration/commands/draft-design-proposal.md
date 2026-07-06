---
description: Draft a well-framed design proposal — an inline note, lightweight design doc, or full RFC — for an accepted change request.
argument-hint: "[the accepted change, problem, or design to propose]"
---

# Draft Design Proposal

Use this command when the user wants to turn an accepted change request (or a known, agreed problem) into a clear design proposal that answers *how* to build it.

## Inputs

- `[the accepted change, problem, or design to propose]`: The accepted change request or problem the design answers, plus any known approach, constraints, or alternatives. If omitted, ask the user what accepted change the design should address.
- Selected files, the linked request, architecture notes, or prior discussion may be treated as source context when the tool provides them.

If no accepted change request stands behind the input, flag that the *Why* is unvalidated and consider settling the change request upstream first; do not re-justify the need here.

## Workflow

1. Follow the `design-proposal` skill's **authoring path** as the authoritative procedure, including its rubric, `references/design-forms.md`, and the templates in `assets/`.
2. Anchor to the accepted Why: recap the problem and desired outcome and link to the request.
3. Size the change and pick the weight (inline note, lightweight design doc, or full RFC) — the lightest artifact that still lets a reviewer judge the approach.
4. State the proposed design, weigh the real alternatives, bound the impact and non-goals, and address migration, rollout, rollback, and risks proportional to the weight.
5. Fill the matching template, keeping detail proportional to the change's size and reversibility.

## Constraints

- Design the How; do not re-author or re-triage the Why — that stays with the upstream change-request stage.
- Do not implement the change, generate the code, or direct whoever will build it.
- Do not invent constraints, metrics, or context the user did not provide; mark any section left thin because the input did not cover it.
- Do not file, post, push, or open anything on an external tracker; return the artifact for the user to circulate.

## Output

Return the completed design proposal in Markdown, plus a note of the chosen weight and form, a link back to the accepted request, and any section that needs more input from the user.
