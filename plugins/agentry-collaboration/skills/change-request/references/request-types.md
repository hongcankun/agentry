# Request types, concepts, and form selection

Detailed guidance behind the `change-request` skill: how to classify a request, how the neighboring concepts differ, and how to choose the form and venue.

## Taxonomy

Each type shares the rubric (Why-not-How, quantified pain, result-oriented acceptance, bounded scope) but emphasizes different fields.

| Type | The ask | Key evidence | Hardest part | What the recipient weighs |
| --- | --- | --- | --- | --- |
| **Feature Request** | Add or change a capability | Use case + pain | Justifying the value | Should we do it, and to what shape? |
| **Bug Report** | Something behaves wrong | Reproduction steps + logs | Making it reproducible | Can we reproduce it, how bad is it? |
| **Refactor Proposal** | Improve internals, behavior unchanged | Quantified maintenance pain + blast radius | Proving no regression | Is the risk controlled, is it worth it? |

All three share the rubric and differ only in which fields they emphasize. There is no fourth type for who executes it: a human contributor and an AI agent both work from the same request.

### Boundary cases

- **User-perceivable performance or UX improvement** → route to a Feature Request (behavior changes in a way the user feels), unless the project has a dedicated performance issue type. Back it with a before/after measurement.
- **Bug plus a design change** → split into two: a Bug Report to fix the defect and a Refactor Proposal for the redesign. Mixed requests are easy to reject.
- **Small refactor** (a few lines, one file) → a short PR with a one-line rationale, not a full proposal.
- **Refactor touching public API or behavior** → this is no longer "behavior unchanged"; escalate to a Feature Request or RFC.
- **Large, multi-module refactor** → stage it and route through an RFC.

## Neighboring concepts

These are the same request at different points on the path from raw need to shipped change. Confusing them is the common failure.

```
Problem Statement / Feature Request   (input: a need to evaluate)
        ↓  maintainer / product selection and justification
PRD                                   (output: a chosen, defined plan)
        ↓  engineering
Proposal / RFC / Design Doc           (how: a design with a solution)
        ↓
code / PR
```

### Feature Request vs Problem Statement — containment, not either/or

A good Feature Request *contains* a Problem Statement:

```
Feature Request
├── Problem Statement   (background / pain)      → lets the recipient judge validity
├── Desired Outcome     (what you want)          → states your ask
└── (How left open)                              → lets the recipient design it
```

Write a standalone Problem Statement only when you have not yet decided what outcome you want and just need to confirm the problem is real. Otherwise wrap it in a Feature Request.

### Feature Request vs Proposal / RFC — with or without a solution

| Dimension | Feature Request | Proposal / RFC |
| --- | --- | --- |
| Content | Problem + desired outcome (no solution) | Problem + full design |
| Who designs | The maintainer | The proposer |
| When to use | Ordinary need; let the maintainer lead design | You already have a complete design, or the change is large/breaking |

Default to a Feature Request. Writing an RFC when you want the maintainer to lead the design oversteps and locks in the How. Do not open with a PR either — a PR says "I already did it for you" and skips both validity judgment and design.

### Feature Request vs PRD — input vs output

A Feature Request is an *input* (a proposed need, may be rejected). A PRD is an *output* (a justified, committed plan with resourcing behind it). The former is raw material for the latter; do not present a single proposed need as a PRD.

## Form and venue decision tree

```
The ask
├── An undisclosed security vulnerability?
│   └── Yes → private disclosure (Security Advisory / SECURITY.md contact); never a public issue
├── Seeking help or an open, unformed discussion?
│   └── Yes → Discussions (large projects) or an issue with a question label (small projects)
├── A large, breaking design change, and the project has an RFC process?
│   └── Yes → the RFC repo / process with a full design
└── Otherwise (bug / feature / refactor / docs / perf / small design proposal)
    └── A single issue, typed and labeled, using the matching template
```

## Downstream: beyond the request

The request type and its rubric are the same regardless of who executes it. A well-formed request already carries what a reader needs to decide on it — result-oriented acceptance criteria describe the target outcome, and non-goals bound the work. Whoever later executes an accepted request, a human contributor or an AI agent, works from that same request; the executor does not change it.

Deciding *how* to build an accepted request — the implementation approach, the execution constraints an agent cannot infer, and directing that work — is a separate downstream stage. It belongs to design/implementation and orchestration, not to the change request, which stays a Why-focused input. Keep How out of the request itself.
