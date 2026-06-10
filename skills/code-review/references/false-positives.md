# False Positives and the Pre-Report Gate

The primary failure mode of an automated reviewer is manufacturing findings: speculative nits, issues already handled elsewhere, and "security theater." Noise erodes trust and buries the findings that matter. Use this gate to keep only real problems. A clean review with zero findings is a valid, good outcome.

## Pre-report gate

Before reporting a candidate finding, answer all four questions:

1. **Location** — Can I cite the exact `file:line` where the problem lives?
2. **Failure mode** — Can I describe a concrete way it goes wrong (specific input → state → bad outcome)?
3. **Context** — Did I read the surrounding code (callers, guards, types, framework behavior), not just the diff hunk?
4. **Defensibility** — Is the severity justified, and would a senior engineer on this team actually change this in review?

If any answer is "no" or "unsure", downgrade the finding or drop it. High and Critical findings additionally require proof: the exact snippet, the failure scenario, and why existing guards do not already catch it.

## Skip rules

- Skip pure stylistic or formatting preferences, especially anything a linter/formatter owns.
- Skip issues in unchanged code, unless it is a Critical security risk the change exposes.
- Consolidate repeated instances of one issue into a single finding.
- Prioritize bugs, security, and data-loss risks over everything else.

## Common false positives to avoid

Do not flag these unless context proves a real problem:

- "Consider adding error handling" when the caller or framework already handles the error.
- Input validation that is already done upstream or at a trust boundary.
- Well-known constants treated as "magic numbers" (e.g. `1000` for ms, `200`/`404` HTTP codes).
- "Function too long" / "file too long" on switch statements, config maps, generated code, or test files.
- Missing docstrings/JSDoc on small self-describing helpers.
- `const` vs `let` and other preferences a formatter or linter enforces.
- Possible null/undefined dereference that is actually guarded earlier.
- "N+1 query" on a fixed, small, in-memory loop with no database calls.
- Missing `await` on intentional fire-and-forget calls.
- Suggesting language/type-system changes that don't fit the file (e.g. proposing TypeScript in a `.js` file).
- Hardcoded values inside tests, fixtures, or examples.
- "Security theater" — defenses against threats that don't apply to this code's trust boundary.

Litmus test for any borderline finding: *would a senior engineer on this team actually change this in review?* If not, drop it.

## Reviewing AI-generated changes

When the change was produced by an AI agent, weight attention toward the failure modes that tooling and the author are most likely to miss:

- behavioral regressions and unhandled edge cases;
- security and trust-boundary mistakes;
- hidden coupling and architecture drift from existing patterns;
- unnecessary complexity or abstraction that adds cost without benefit.
