# Severity Levels

Classify every finding with a severity so the author can triage quickly. Keep blocking issues separate from optional ones, and do not inflate severity.

## Levels

Each level maps to an action verb so the author knows what is expected:

| Level | Meaning | Action |
|-------|---------|--------|
| **Critical** | Security vulnerability or data-loss risk: auth bypass, injection, data corruption, crash on a common path, or a regression of existing behavior. | **BLOCK** — must fix before merge |
| **High** | Bug or significant quality issue: edge-case bug, missing error handling that will cause failures, a real performance problem at expected scale, or missing tests for risky new logic. | **WARN** — should fix before merge |
| **Medium** | Maintainability or design concern: fragile code, unclear contracts, or gaps that work now but will bite later. | **INFO** — consider fixing |
| **Low** | Minor improvement: readability, naming, small refactors, or non-critical test gaps. | **NOTE** — optional |
| **Nit** | Pure preference or cosmetic: formatting, wording, or style not enforced by tooling. Mark explicitly as optional (e.g. prefix "nit:"). | **NOTE** — optional |

## Classifying

- Judge by **impact** (what goes wrong) and **likelihood** (how often the bad path is hit), not by how easy the fix is.
- Security and correctness defects on common paths start at Critical/High.
- When unsure between two levels, state the assumption that would change your call.
- Blocking = Critical + High. Everything else is non-blocking.

## Communicating

- Lead with the location: `path/to/file.ext:line`.
- State the problem and its concrete impact in one or two sentences.
- Give a specific suggested fix or a clear question — avoid vague "this could be better".
- Group repeated instances of the same issue into one finding with a note that it recurs.
- Distinguish facts ("this dereferences a possibly-null value") from opinions ("I'd prefer a guard clause here").

## Decision logic

Map findings (and validation results, if run) to one recommendation:
- **Approve** — zero Critical/High findings and validation passes. If only Low/Nit remain, approve; if Medium remain, approve with comments. Author may merge after addressing or acknowledging the comments.
- **Request changes** — one or more High findings, or validation fails. These must be resolved before merge.
- **Block** — one or more Critical findings (e.g. a security vulnerability or data loss). Never approve code with a security vulnerability.

Special cases:
- Draft/WIP changes → comment rather than approve or block.
- Docs/config-only changes → lighter review; validation may be skipped.
