# Published Comment Format

Use these agnostic defaults for review comment bodies. Adapt labels naturally while preserving the structure.

## Inline Comments

Use inline comments for actionable findings that map confidently to a changed location, diff position, file, object, or component.

```markdown
**Problem [Level]:** <concrete issue tied to this location>

**Impact:** <why it matters>

**Notes:** <optional evidence, constraint, affected scenario, recurrence, shortened log, or platform caveat>

**Suggested fix:** <specific change, remediation, or test/assertion to add>

_Source: <review workflow or finding source>._
```

Rules:

- Use `Critical`, `High`, `Medium`, `Low`, `Nit`, or `Info` in `Problem [Level]` when the source finding has a reliable level.
- If no reliable level exists, use `**Problem:**` without a level. Do not invent or inflate levels while formatting the comment.
- Anchor the comment to the earliest changed line that makes the finding understandable and actionable, usually the condition, assignment, call, declaration, or first statement that introduces the issue. Use a block's closing line, final statement, broad range end, or last line only when that exact line is the actionable defect.
- Omit `Notes` when it adds no useful signal. Use it only for evidence needed to act on the finding, such as constraints, affected scenarios, recurrence, shortened logs, validation details, platform caveats, or concise additional affected locations.
- Keep one inline comment focused on one actionable location-tied finding.
- Do not include overall verdicts, unrelated findings, platform actions, URLs, comment ids, review ids, or status bookkeeping in inline comment bodies.
- For security findings, redact sensitive evidence and avoid exploit instructions.

## Summary Comments

Use summary comments for overall verdicts, change context, reviewer-run validation, track coverage, residual risk, and findings that cannot be mapped to a stable inline location.

```markdown
**Verdict:** <pass | pass with warnings | request changes | block | informational>

**Change summary:** <brief summary in own words>

**Findings:** <severity counts plus high-level categories only; do not repeat individual inline findings>

**Coverage:**
- Code quality: <covered / skipped / degraded + key note>
- Security: <covered / skipped / degraded + key note>
- Tests: <covered / skipped / degraded + key note>

**Validation:** <reviewer-run checks passed, failed, skipped, or blocked>

**Notes:** <optional non-duplicative context, constraints, links, known limitations, or caveats>

**Remaining risk:** <material residual risk or manual follow-up only>

_Source: <review workflow or finding source>; reviewed=<version or patchset>; head=<branch>@<short SHA>; base=<branch>@<short SHA>._
```

Rules:

- Keep the summary compact and useful for scanning.
- Do not repeat individual inline findings, file-specific details, or full remediation text already placed inline.
- Use `Findings` for severity counts, high-level categories, and grouped themes instead of listing every repeated location.
- Omit `Notes` or `Remaining risk` when empty.
- If the source has different coverage tracks, adapt the `Coverage` labels while keeping the same role: what was covered, skipped, or degraded.
- Keep `Validation` scoped to checks the reviewer ran or attempted. Do not fetch or summarize platform-owned PR/MR checks, workflow, pipeline, or check-run status unless the user explicitly asked for that context or supplied CI failure findings.
- Keep `_Source:_` as one italic line, not bullets, blockquotes, or a table.
- Use stable `key=value` fields for reviewed-revision metadata when available, such as `_Source: quality-gate; reviewed=patchset 7; head=feature/foo@abc1234; base=main@def5678._`.
- Omit unavailable metadata fields instead of inventing placeholders.
- Keep platform actions, URLs, comment ids, review ids, and status bookkeeping out of summary comment bodies.

## Final Check

Before returning or sending comments, confirm:
- inline comments use the inline template and normalized levels;
- summary comments use the summary template and do not repeat inline findings;
- platform URLs, ids, and status bookkeeping stay in the agent report, not the comment body.
