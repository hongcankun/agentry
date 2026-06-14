# Review Dimensions

Evaluate a change across these dimensions. Weight effort toward the areas where the change carries the most risk; not every dimension is relevant to every diff.

`references/code-style.md` is the project's style standard underpinning several dimensions below (notably readability, error handling, and design); enforce a change against it where relevant.

## Correctness

- The code does what the description/issue says it does.
- Edge cases are handled: empty inputs, nulls, zero, negatives, large values, boundaries, off-by-one.
- Control flow and conditionals are right; no inverted logic or unreachable branches.
- Concurrency: shared state, race conditions, deadlocks, and ordering assumptions.
- No regressions in nearby behavior the change touches.

## Security

- Untrusted input is validated and sanitized at boundaries.
- No injection vectors: SQL, command, path traversal, XSS, SSRF, template/log injection.
- AuthN/AuthZ checks are present and correct for new endpoints or actions.
- Secrets are not hardcoded or logged; sensitive data is not exposed.
- Safe crypto and randomness; no rolled-your-own crypto.
- Dependencies added are reputable and necessary.

## Error handling and resilience

- Errors are caught, propagated, or surfaced appropriately — not silently swallowed.
- Failure modes are handled: timeouts, retries, partial failures, resource cleanup.
- Resources (files, connections, locks) are released on all paths.
- Error messages are useful and do not leak sensitive detail.

## Readability and maintainability

- Names clearly convey intent; no misleading or cryptic identifiers.
- Functions and modules have a single clear responsibility and reasonable size.
- Comments explain *why* where logic is non-obvious; no commented-out or dead code.
- Consistent with the project's existing style and conventions.
- No needless complexity, premature abstraction, or copy-paste duplication.
- No leftover debug statements (`console.log`, prints) or stray TODO/FIXME without a tracking reference.

Useful size/complexity **signals** (not hard rules — flag only when they hurt readability, never mechanically): functions beyond ~50 lines, files beyond ~800 lines, or nesting deeper than ~4 levels often indicate something worth splitting or flattening with early returns. Defer to the project's own configured limits where they exist.

## Design and architecture

- The change fits existing patterns and module boundaries.
- Abstractions are at the right level; coupling is minimized.
- Public APIs/contracts are sensible and backward-compatible where required.
- The scope matches the intent — no unrelated changes smuggled in.

## Performance

- No obvious inefficiency for the expected input sizes (e.g. N+1 queries, quadratic loops on large data, repeated work).
- Appropriate data structures and caching where it matters.
- Avoids blocking the hot path with expensive synchronous work.
- Optimize only where it matters; do not flag micro-optimizations as defects.

## Testing

- New logic and bug fixes are covered by tests; a bug fix includes a regression test.
- Tests assert meaningful behavior and cover edge cases, not just the happy path.
- Tests are deterministic and isolated; no reliance on timing or external state.

## Documentation

- Public APIs, config, and user-facing behavior changes are documented.
- README/changelog/migration notes updated when relevant.
- Code comments and docstrings match the new behavior.
