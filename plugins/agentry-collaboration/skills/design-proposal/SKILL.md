---
name: design-proposal
description: Author or triage a design proposal — the design (RFC / design doc) that answers how to build an accepted change request. Use when a user wants help drafting a design or RFC for an accepted change, or judging, revising, or deciding on an incoming design proposal.
---

# Design Proposal

A *design proposal* is the design that answers **How** to build an accepted change: an RFC, a design doc, or a short inline design note. This skill helps on both sides of that design — **authoring** a clear proposal and **triaging** an incoming one — using one shared rubric. It picks up where a change request leaves off: the *Why* (problem validity, desired outcome, prioritization) is already settled upstream, when the change request was accepted; this skill designs the solution. It covers the design itself, not the implementation, the code review of the resulting PR, or the orchestration that directs whoever builds it.

Follow these principles:
- **Recap the Why and bound the aim.** Restate the accepted problem and desired outcome briefly and link to them, and say what the design explicitly does *not* aim to do; do not re-litigate whether to do the work. The design's job is the solution, not the justification for the need.
- **Justify the approach against alternatives, and own its drawbacks.** Show the main options considered and why the chosen one wins, and state the costs of the chosen approach honestly. A design with no alternatives is a decision with no reasoning; one with no drawbacks is one that hides them.
- **Bound the impact.** State what the change reaches and, explicitly, what it leaves untouched — its reach and effect, so reviewers can reason about risk. This is distinct from the non-goals of intent.
- **Address migration, rollout, and rollback.** For anything breaking or stateful, say how users move, how it ships, and how to back out.
- **Make risks explicit.** Name the failure modes, the open questions, and the mitigations. Unstated risk is the most expensive kind.
- **Right-size the weight.** Match the artifact to the change's size and reversibility — an inline note for a small reversible change, a full RFC for a large or breaking one. Do not over- or under-document.
- **Judge the design, not the code.** Triage decides whether the approach is sound and well-framed; reviewing the implementation that fulfills it is a separate job.

## When to use

Use this skill when the task is to:
- turn an accepted change request (or a known, agreed problem) into a design proposal an implementer can build from;
- draft an RFC or design doc for a large, breaking, or hard-to-reverse change;
- decide whether an incoming design proposal is sound and the right weight;
- identify what a thin design is missing before it goes to review.

## Expected input

Gather as much of the following as available:

- **Authoring** — the accepted change request or problem statement it answers (the *Why* and the desired outcome); the affected architecture, component, or subsystem; constraints the design must respect (compatibility, deadlines, platform, dependencies); known alternatives or prior art.
- **Triage** — the design text (pasted, a file path, or a link the user provides); the accepted request it claims to answer; the project's design conventions (RFC process, ADR format, template) and any related past designs for consistency.

If the input jumps straight to a solution with no accepted request behind it, note that the *Why* is unvalidated — the design may be solving a problem no one agreed to — and consider settling the change request upstream first. Do not re-author or re-triage the request here.

## Weight tiers

Size the change first, then pick the lightest artifact that still lets a reviewer judge the approach. See `references/design-forms.md` for the full tiering, the form-and-venue decision tree, and the handoffs to neighboring stages.

| Change | Weight | Artifact |
| --- | --- | --- |
| Small, reversible, single-component | Inline design note | A short paragraph in the issue/PR: approach + main risk |
| Medium, mostly reversible, few components | Lightweight design doc | `assets/design-doc.md`: summary, motivation, design, alternatives, impact, risks, observability |
| Large, breaking, or hard to reverse | Full RFC | `assets/rfc.md`: summary, motivation, current state, design, alternatives, drawbacks, prior art, impact, migration, rollout, rollback, risks, observability — circulated for review |

## Workflow

Pick the path from the task, then converge on the shared rubric.

### Authoring path

1. **Anchor to the accepted Why, and set non-goals.** Restate the problem and desired outcome from the change request and link to it, and state what the design explicitly does *not* aim to do. If no accepted request exists, flag the *Why* as unvalidated.
2. **Size the change and pick the weight** using the table above and `references/design-forms.md`. Choose the lightest artifact that still lets a reviewer judge the approach.
3. **Fill the matching template** from `assets/` (or write the inline note directly for the smallest tier), working through its sections in order and keeping detail proportional to the weight. The template owns the per-section guidance — design, alternatives, impact, migration/rollout/rollback, risks — so fill those there rather than re-deriving them here.

### Triage path

1. **Confirm the Why is settled.** Check that the design answers an accepted request. If the underlying problem's validity or priority is still open, send it back to the change-request stage instead of triaging the design.
2. **Judge against the rubric.** Is the approach justified over real alternatives? Are the non-goals explicit and the impact bounded? Are migration, rollback, and risks addressed for the change's size? Is this the right weight? See `references/triage.md`.
3. **Decide.** Assign one decision — **accept**, **revise**, **reject**, or **needs-info** — with a rationale tied to the rubric. For *revise*, name the specific sections or changes required; for *reject*, give the reason and any alternative direction. See `references/triage.md`.

### Converge: the rubric

Both paths turn on the same lens (the principles above): authoring builds a design that satisfies the rubric; triage measures a design against it.

## Output

- **Authoring** — the completed design proposal in Markdown (from the matching template, or an inline note for the smallest tier), ready for the user to circulate. Note the chosen weight and form, link back to the accepted request, and call out any section left thin because the input did not cover it.
- **Triage** — the decision (accept / revise / reject / needs-info) with a rationale tied to the rubric. For *revise*, list the exact sections or changes required; for *reject*, give the reason and any alternative direction; for *needs-info*, name the missing sections that block evaluation.

## References

- `references/design-forms.md`: the weight tiers, the form-and-venue decision tree (inline note vs design doc vs RFC vs ADR), the handoffs to the neighboring change-request (upstream) and implementation / code-review (downstream) stages, and the lifecycle conventions for managing a collection of designs over time.
- `references/triage.md`: the design triage framework — the rubric, decision states (accept / revise / reject / needs-info), and how to size the required weight.
- `assets/rfc.md`, `assets/design-doc.md`: fill-in templates for the full-RFC and lightweight tiers.
