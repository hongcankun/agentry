# Published Comment Format

Use these agnostic defaults for review comment bodies. Adapt labels naturally to the finding source and target while preserving the structure.

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
- Anchor the comment to the earliest changed line that makes the finding understandable and actionable, usually the condition, assignment, call, declaration, or first statement that introduces the issue.
- Do not anchor to a block's closing line, final statement, or broad range end just because the issue is detected after reading the whole block. Use the last line only when that exact line is the actionable defect.
- Omit `Notes` when it adds no useful signal.
- Use `Notes` only for evidence needed to understand or act on the finding, such as constraints, affected scenarios, recurrence, shortened logs, validation details, or platform caveats.
- Do not use `Notes` for broad advice, full logs, repeated summary content, speculative concerns, or unrelated background.
- Keep one inline comment focused on one actionable location-tied finding.
- When a comment represents a cluster, keep `Problem` and `Suggested fix` focused on the representative location, and use `Notes` only for concise additional affected locations or recurrence evidence.
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

_Source: <review workflow or finding source>; reviewed <version/patchset and base/head revisions when available>._
```

Rules:

- Keep the summary compact and useful for scanning.
- Do not repeat individual inline findings, file-specific details, or full remediation text already placed inline.
- Use `Findings` for severity counts plus high-level categories, such as `1 High and 2 Medium findings across authorization checks and regression coverage`.
- When findings were grouped, include the grouped themes and counts instead of listing every repeated location.
- Omit `Notes` or `Remaining risk` when empty.
- If the source has different coverage tracks, adapt the `Coverage` labels while keeping the same role: what was covered, skipped, or degraded.
- Keep `Validation` scoped to checks the reviewer ran or attempted. Do not summarize platform-owned PR/MR workflow, pipeline, or check-run status unless the user explicitly asked for that context or supplied CI failure findings.
- Include concise reviewed-revision metadata in the `_Source:_` footer when available, such as `reviewed patchset 7, head feature/foo@abc1234 against main@def5678`.
- Keep platform actions, URLs, comment ids, review ids, and status bookkeeping out of summary comment bodies.

## Final Check

Before returning or sending comments, confirm:
- inline comments use the inline template and normalized levels;
- summary comments use the summary template and do not repeat inline findings;
- grouped findings are described compactly by theme, count, or a few useful locations;
- platform URLs, ids, and status bookkeeping stay in the agent report, not the comment body.
