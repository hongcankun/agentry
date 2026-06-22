# Published Comment Format

Use these agnostic defaults for comments that will be drafted or published to a review surface. Adapt labels naturally to the finding source and target while preserving the structure.

## Inline Comments

Use inline comments for actionable findings that map confidently to a changed location, diff position, file, object, or component.

```markdown
**Problem [Level]:** <concrete issue tied to this location>
**Impact:** <why it matters>
**Notes:** <optional evidence, constraint, affected scenario, recurrence, shortened log, or platform caveat>
**Suggested fix:** <specific change, remediation, or test/assertion to add>

_Source: <review workflow or finding source>[ / <source track>]._
```

Rules:

- Use `Critical`, `High`, `Medium`, `Low`, `Nit`, or `Info` in `Problem [Level]` when the source finding has a reliable level.
- If no reliable level exists, use `**Problem:**` without a level. Do not invent or inflate levels during publishing.
- Omit `Notes` when it adds no useful signal.
- Use `Notes` only for evidence or details needed to understand or act on the finding, such as constraints, affected scenarios, recurrence, shortened logs, validation details, or platform caveats.
- Do not use `Notes` for broad advice, full logs, repeated summary content, speculative concerns, or unrelated background.
- Keep one inline comment focused on one actionable location-tied finding.
- Do not include overall verdicts, unrelated findings, platform actions, published URLs, comment ids, review ids, or publish status in inline comment bodies.
- For security findings, redact sensitive evidence and avoid exploit instructions.

## Summary Comments

Use summary comments for overall verdicts, change context, validation evidence, track coverage, residual risk, and findings that cannot be mapped to a stable inline location.

```markdown
**Verdict:** <pass | pass with warnings | request changes | block | informational>

**Change summary:** <brief summary in own words>

**Findings:** <severity counts plus high-level categories only; do not repeat individual inline findings>

**Coverage:**
- Code quality: <covered / skipped / degraded + key note>
- Security: <covered / skipped / degraded + key note>
- Tests: <covered / skipped / degraded + key note>

**Validation:** <checks run, passed, failed, skipped, or blocked>

**Notes:** <optional non-duplicative context, constraints, links, known limitations, or caveats>

**Remaining risk:** <material residual risk or manual follow-up only>

_Source: <review workflow or finding source>._
```

Rules:

- Keep the summary compact and useful for scanning.
- Do not repeat individual inline findings, file-specific details, or full remediation text already placed inline.
- Use `Findings` for severity counts plus high-level categories, such as `1 High and 2 Medium findings across authorization checks and regression coverage`.
- Omit `Notes` or `Remaining risk` when empty.
- If the source has different coverage tracks, adapt the `Coverage` labels while keeping the same role: what was covered, skipped, or degraded.
- Keep platform actions, published URLs, comment ids, review ids, and publish status out of summary comment bodies.

## Final Check

Before returning or publishing, confirm:
- inline comments use the inline template and normalized levels;
- summary comments use the summary template and do not repeat inline findings;
- platform URLs, ids, and publish status stay in the agent report, not the comment body.
