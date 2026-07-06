# Design triage framework

Detailed guidance behind the `design-proposal` skill's triage path: how to judge an incoming design, which decision to assign, and how to size the required weight. Triage judges the *design* — whether the approach is sound and well-framed — not the code that would implement it, and not whether the underlying request was worth accepting.

## Step 1 — Confirm the Why is settled

A design answers an accepted request. Before judging the design, confirm that request exists and was accepted. If the underlying problem's validity or priority is still open, the design is premature: send it back to the change-request stage rather than triaging a solution to an unagreed problem. Do not re-litigate the Why here — accept it as given and judge only the How.

## Step 2 — Judge against the rubric

Measure the design against the same lens used to author one:

| Rubric field | Question | Fails when |
| --- | --- | --- |
| Anchored to the Why | Does it recap and link the accepted request instead of re-justifying it? | It re-argues whether to do the work, or has no accepted request behind it |
| Approach justified | Are real alternatives weighed, the choice reasoned, and the chosen approach's drawbacks owned? | One approach asserted with no alternatives, strawman options, or no honest downsides |
| Bounded aim (non-goals) | Are the non-goals explicit — what the design does not aim to do? | Scope of intent is open-ended; non-goals are absent; likely to sprawl |
| Bounded impact | Is what the change reaches — and leaves untouched — explicit? | The reach is unclear; the consumers, data, or dependents it affects are unstated |
| Migration & rollback | For breaking or stateful changes, is the path in and out addressed? | A breaking change with no migration, or no way to back out |
| Risks surfaced | Are failure modes, open questions, and mitigations named? | Risks unstated or hand-waved; open questions hidden |
| Right weight | Does the artifact match the change's size and reversibility? | A full RFC for a trivial tweak, or an inline note for a breaking change |

A design can pass the Why-anchor and still fail here: a real, accepted problem can get an unjustified, unbounded, or wrongly-sized solution. That gap is exactly what design triage exists to catch.

## Step 3 — Assign a decision

Choose exactly one:

| Decision | When | What to include |
| --- | --- | --- |
| **Accept** | The approach is sound, bounded, right-sized, and ready to build | Any conditions, and which follow-ups (e.g. ADRs) to record on acceptance |
| **Revise** | The direction is workable but a rubric field is thin or a section is missing | The specific sections or changes required, concretely |
| **Reject** | The approach is unsound, the impact is unacceptable, or a better option clearly wins | A clear, respectful reason and an alternative direction if one exists |
| **Needs-info** | Cannot yet be evaluated — missing context the reviewer needs | The specific missing sections or facts that block evaluation |

**Revise** is the design-stage workhorse and the main difference from change-request triage: most designs are directionally fine but under-argue an alternative, skip migration, or misjudge their weight. Prefer a concrete *revise* ("add the rejected 'in-process cache' alternative and its trade-off"; "the on-disk format change needs a migration section") over a blunt reject. Reserve **reject** for an approach that should not proceed, not one that merely needs more work. Use **needs-info** when the gap is missing input the reviewer needs, and **revise** when the gap is work the author must do.

## Step 4 — Size the required weight

Part of judging a design is judging whether it is the right *weight* (see `references/design-forms.md`). Two failure directions:

- **Under-weight** — a breaking or irreversible change documented as an inline note. Require the missing migration, rollback, and alternatives; this is usually a *revise*, and for a large change may block acceptance until the RFC exists.
- **Over-weight** — a trivial, reversible change carrying a full RFC's ceremony. Note it, but do not block on it: a too-heavy design is a mild waste, not a risk. Accept the approach and suggest trimming next time rather than demanding a rewrite.

State the weight you judged the change to need and why, so the ranking can be revisited if the scope estimate was wrong.

## Handling common patterns

- **Sound approach, missing rollout** — revise, not reject; name the rollout/rollback sections to add rather than discarding a good design.
- **Two viable approaches, no clear winner** — revise to force an explicit trade-off and a stated choice; a design that lists options without deciding is not done.
- **Gold-plated design** — the approach solves more than the accepted request asked for; cut it back to the request's scope and non-goals rather than accepting the extra reach.
- **Design that reopens the Why** — if it argues the problem is different from what was accepted, that is a Why question for the change-request stage; send it upstream instead of expanding the design.
- **No alternatives at all** — treat as *needs-info* or *revise*: an approach with nothing weighed against it has not been designed, only asserted.
