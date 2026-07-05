---
description: Triage an incoming change request — judge it against the rubric and decide accept, reject, needs-info, or duplicate with a priority.
argument-hint: "[the request to triage: pasted text, a file path, or a link]"
---

# Triage Change Request

Use this command when the user wants to judge, prioritize, or decide on an incoming change request. It evaluates the request itself — whether it is worth doing and well-framed — not the code that would fulfill it.

## Inputs

- `[the request to triage]`: The request to evaluate, as pasted text, a file path, or a link the user provides. If omitted, ask the user for the request to triage.
- Existing requests, a backlog, or project conventions (`CONTRIBUTING`, issue templates, RFC process, priority scheme) may be treated as source context when the tool provides them.

If the request is ambiguous or partial, prefer a **needs-info** decision that names the missing fields over guessing.

## Workflow

1. Follow the `change-request` skill's **triage path** as the authoritative procedure, including its rubric and `references/triage.md`.
2. Check for prior art and duplicates against any existing requests the user provides.
3. Judge the request against the rubric: Why-not-How, quantified pain, result-oriented acceptance, bounded scope, right form and venue.
4. Assign one decision — accept, reject, needs-info, or duplicate — with a priority and a brief rationale.

## Constraints

- Judge the request, not the delivered implementation; do not review or design the code that would fulfill it.
- Prioritize by impact and cost, not by who asked or how loudly.
- Do not modify, close, or comment on anything on an external tracker; return the decision for the user to act on.

## Output

Return the decision (accept / reject / needs-info / duplicate) with priority and rationale tied to the rubric. For needs-info, list the exact questions or fields the requester must supply. For duplicate, point to the canonical request.
