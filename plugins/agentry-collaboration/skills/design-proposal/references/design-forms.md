# Weight tiers, forms, and handoffs

Detailed guidance behind the `design-proposal` skill: how to size a design, which artifact to pick, and how the design stage hands off to the stages around it.

## Weight tiers

Size the change first, then pick the lightest artifact that still lets a reviewer judge the approach. Over-documenting a trivial change wastes everyone's time; under-documenting a breaking one is where large changes go wrong.

| Tier | Change looks like | Artifact | Must cover |
| --- | --- | --- | --- |
| **Inline note** | Small, reversible, one component; the approach is obvious once stated | A paragraph in the issue or PR | Chosen approach + the one risk worth naming |
| **Lightweight design doc** | Medium; a few components; mostly reversible; one or two real alternatives | `assets/design-doc.md` | Summary, motivation, design, alternatives, impact, main risks, observability |
| **Full RFC** | Large, breaking, hard to reverse, or cross-team | `assets/rfc.md`, circulated for review | Summary, motivation, current state, design, alternatives, drawbacks, prior art, impact, migration, rollout, rollback, risks, observability |

Two forces set the tier: **size** (how many components and people the change touches) and **reversibility** (how cheaply a wrong decision can be undone). A large but trivially reversible change can stay light; a small but irreversible one (a public API shape, a data migration, a wire format) earns a full RFC. When the two disagree, let reversibility win — the cost of being wrong is what a design guards against.

### Boundary cases

- **Small change, irreversible decision** (a new public API, an on-disk format) → escalate to at least a lightweight doc; the impact, not the diff size, sets the weight.
- **Large change, fully reversible, no alternatives worth weighing** → a lightweight doc can be enough; do not force a full RFC just because the diff is big.
- **Two independent designs bundled together** → split them. One artifact per decision keeps alternatives and risks legible and each design separately acceptable.
- **Design that keeps growing new sections** → it is probably answering more than one accepted request; check whether the *Why* was actually one request or several.
- **"Design" that is really a spike or prototype** → prototypes explore feasibility; write the design once the approach is chosen, using what the spike learned.

## The design stage in context

A design proposal sits between an accepted request and the code that implements it. Confusing it with its neighbors is the common failure.

```
Problem Statement / Feature Request   (Why: a need, validated)   ← change-request stage
        ↓  accepted
Design Proposal / RFC / Design Doc    (How: a chosen solution)    ← this skill
        ↓  approved
code / PR                             (the built change)          ← implementation + code review
```

### Design proposal vs change request — How vs Why

| Dimension | Change request | Design proposal |
| --- | --- | --- |
| Question | Why — is this worth doing? | How — what is the solution? |
| Content | Problem + desired outcome, no solution | Recap + full design |
| Decision it seeks | Accept / reject the ask | Accept / revise / reject the approach |
| Owner of the answer | Whoever prioritizes the work | Whoever will design or build it |

The handoff is explicit: a design proposal **quotes and links** the accepted request, restates the problem and desired outcome in a sentence or two, and then spends its length on the solution. It does not re-argue whether the work is worth doing — that decision is already made. If you find yourself justifying the need, you have drifted back into the Why, which the change request already settled.

### Design proposal vs PRD — how vs what-and-why-committed

A PRD is a committed statement of *what* to build and *why*, with resourcing behind it. A design proposal is the *how* that follows it. A PRD says "we will support SSO by Q3"; the design proposal says "here is the OIDC integration, the token store, the migration, and the alternatives we rejected." Do not fold product commitment into a design, and do not treat a design as the decision to fund the work.

### Design proposal vs ADR — the design vs the recorded decision

An Architecture Decision Record captures a single decision and its consequences after the fact, for the record. A design proposal is the forward-looking document that *proposes* the design and invites review. A large design may spawn one or more ADRs once accepted; a small, clear decision may be recorded directly as an ADR without a full RFC. If the project uses ADRs, note which decisions the design should be captured as once accepted.

## Form and venue decision tree

```
The accepted change to design
├── Is the Why still unsettled (validity or priority open)?
│   └── Yes → stop; settle the change request upstream first. Do not design an unaccepted request.
├── Small, reversible, single-component, approach obvious?
│   └── Yes → an inline design note in the issue or PR
├── Large, breaking, hard to reverse, or cross-team, and the project has an RFC process?
│   └── Yes → a full RFC in the RFC repo / process, circulated for review
├── The project records decisions as ADRs and this is one clear decision?
│   └── Yes → an ADR (optionally distilled from a lightweight doc)
└── Otherwise (medium change, a real alternative or two, mostly reversible)
    └── a lightweight design doc attached to the issue or PR
```

Match the venue to the stakes, the same way a change request does: a breaking design gets circulated where the affected parties will see it; a small one lives next to the work. When the project has no RFC process but the change is large or breaking, the design still needs a written artifact and named reviewers — the absence of a process is not a reason to skip the design.

## Handoffs: beyond the design

- **Upstream (change-request stage).** The design consumes an accepted request. If triage reveals the *Why* is not actually settled, the correct move is to send it back to the change-request stage, not to fix the request inside the design.
- **Downstream (implementation).** An accepted design is built by whoever picks it up — a human contributor or an AI agent. Directing that work, sequencing it, and supplying the execution constraints an implementer cannot infer is orchestration, not design; keep it out of the proposal.
- **Downstream (code review).** Reviewing the PR that implements the design — correctness, security, style, tests — is a separate downstream stage, not part of the design. This skill judges whether the *design* is sound; code review judges whether the *code* is.

## Lifecycle: managing designs over time

A repo usually accumulates many designs across the tiers. A few agnostic conventions keep the set legible without prescribing any particular tooling:

- **Carry a status.** Every design doc and RFC records where it stands — draft, in review, accepted, rejected, or superseded — so the collection can be scanned at a glance. Inline notes live with their issue or PR and inherit its state.
- **Keep them discoverable and consistently named.** Land designs in one agreed place with a predictable naming scheme, and index them (a list of designs and their status) so the set is navigable without opening each file. The exact directory, numbering, and index format are a project convention, not part of this skill.
- **Supersede, do not delete.** When a later design replaces an earlier one, mark the old one *superseded* and link forward to its replacement rather than deleting it; the trail of decisions is part of the record.
- **Link to the request.** Each design points back to the accepted change request it answers (the **Answers** field), so a reader can trace How back to Why.
