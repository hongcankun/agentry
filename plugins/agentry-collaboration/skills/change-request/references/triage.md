# Triage decision framework

Detailed guidance behind the `change-request` skill's triage path: how to judge an incoming request, which decision to assign, and how to prioritize. Triage judges the *request* — whether it is worth doing and well-framed — not the code that would fulfill it.

## Step 1 — Check for prior art

Before evaluating, search the existing requests and discussions. If the ask duplicates an open request, assign **duplicate** and point to it rather than re-litigating; if a closed request already decided it, reference that decision. Deduplication protects the backlog and the requester's time.

## Step 2 — Judge against the rubric

Measure the request against the same lens used to author one:

| Rubric field | Question | Fails when |
| --- | --- | --- |
| Why, not How | Is the underlying problem stated, rather than just a solution? | Only a solution is given; the real need is hidden |
| Quantified pain | Is the impact backed by evidence (frequency, cost, blast radius)? | "Would be nice" with no evidence of importance |
| Result-oriented acceptance | Is success observable behavior, not a fixed implementation? | Acceptance dictates internal APIs, algorithms, or thresholds you do not own |
| Bounded scope | Are the boundaries and non-goals clear? | Open-ended; likely to sprawl |
| Right form and venue | Is this the correct type and channel? | A security report filed publicly; a question filed as a bug; a breaking change skipping RFC |

## Step 3 — Assign a decision

Choose exactly one:

| Decision | When | What to include |
| --- | --- | --- |
| **Accept** | Real, well-framed, worth doing now or soon | Priority and any conditions or scope notes |
| **Reject** | Out of scope, not worth the cost, or contradicts direction | A clear, respectful reason and an alternative if one exists |
| **Needs-info** | Plausibly valid but missing rubric fields | The specific questions or fields required to proceed |
| **Duplicate** | Overlaps an existing request | A link to the canonical request |

For **needs-info**, be concrete: name the missing fields (e.g. "quantify how often this occurs", "state the desired outcome, not the proposed fix", "list what is explicitly out of scope") rather than asking for "more detail".

## Step 4 — Prioritize accepted requests

Prioritize by impact and cost, not by who asked or how loudly. Useful signals:

- **Impact** — how many users/systems are affected, and how badly (blocking vs inconvenient).
- **Frequency** — how often the pain occurs.
- **Cost of delay** — does it worsen over time, block other work, or carry a deadline?
- **Effort and risk** — rough size and the chance of regression.
- **Strategic fit** — alignment with the project's direction and non-goals.

Express the result in whatever scheme the project uses (e.g. P0–P3, or Must/Should/Could). State the reasoning briefly so the ranking can be revisited.

## Handling common patterns

- **High-quality but low-priority** — accept and rank honestly; do not reject a good request just because it is not urgent.
- **Valid problem, wrong solution** — accept the problem, set aside the proposed How, and let design proceed from the outcome.
- **Popular but unjustified** — many requests or upvotes signal demand, not validity; still require quantified pain before accepting.
- **Emotional or terse report** — extract the underlying problem and route to needs-info for the missing rubric fields rather than rejecting on tone.
