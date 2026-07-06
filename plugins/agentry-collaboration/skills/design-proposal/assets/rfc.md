<!-- Full RFC template. Fill each section; delete guidance in parentheses. Use this tier for large, breaking, or hard-to-reverse changes. Recap the accepted Why briefly, then spend the length on the How. -->

# RFC: (title of the design)

- **Status:** (draft / in review / accepted / rejected / superseded)
- **Answers:** (link to the accepted change request / issue this designs)
- **Author(s):** (names)

## Summary

(One paragraph: the problem in a sentence and the approach you propose. The elevator pitch a reviewer reads before the details — enough to know what this design does and why.)

## Motivation

(Restate the core of the accepted change request — the problem and the desired outcome — and link it under **Answers** above. Recap, do not re-argue: whether to do the work is already decided. Just enough for a reader to evaluate the design without opening the request.)

**Non-goals:** (what this design explicitly does *not* aim to do — aims deliberately left out of scope, distinct from what the change technically touches. Keep the design from quietly sprawling.)

## Current State

(How the relevant system, flow, or architecture works today — the baseline this design departs from — and the specific pain or limitation in it. Enough for a reviewer to judge whether the proposed approach fits reality. Omit for a greenfield design with no existing baseline.)

## Proposed Design

(The chosen approach, at a level of detail an implementer can build from and a reviewer can evaluate. Architecture, key components, data/interface changes, and how they fit the existing system. Diagrams or interface sketches where they help.)

## Alternatives Considered

(The main options weighed and why the chosen approach wins. Include the "do nothing" or minimal option when it is real. Strawman alternatives fool no one — weigh options that were genuinely viable.)

- **(Alternative A):** (what it is; why rejected)
- **(Alternative B):** (what it is; why rejected)

## Drawbacks

(The costs and downsides of the *chosen* approach — not the roads not taken, but the price of the road taken. Complexity added, constraints imposed, debt incurred. State them plainly; every design has some.)

## Prior Art

(How have other projects, teams, or tools solved this, and what did they learn — good and bad? Reuse the lessons; note where you intentionally diverge. Omit if there is genuinely none.)

## Impact

(What this change reaches — the components, interfaces, data, consumers, or dependents it touches — and, explicitly, what it leaves untouched. This is reach and effect, not intent; the scope of aims lives in Motivation's non-goals.)

## Migration and Rollout

(How existing users or data move to the new design, and how it ships — for example a version release and deprecation window, feature flags, or a phased rollout, as fits the change. For anything breaking or stateful this is mandatory, not optional.)

## Rollback

(How to back out if the change goes wrong after shipping, and what becomes hard to undo once it is live.)

## Risks and Open Questions

(Failure modes and their mitigations. Unresolved questions the reviewer should weigh in on. Say what you are unsure about rather than hiding it.)

## Observability

(How the running design will be observed — both to confirm it achieved the accepted outcome (the success signals or metrics tied to the change request's acceptance criteria) and to operate it over time (the signals — logs, metrics, traces, diagnostics, or equivalents — that let operators or users see its health and diagnose it). This is design-level "what to observe", not code testing or instrumentation wiring, which are separate downstream stages.)

## Additional Context

(Related designs or ADRs, dependencies. Decisions to record as ADRs once this is accepted, if the project uses them.)
