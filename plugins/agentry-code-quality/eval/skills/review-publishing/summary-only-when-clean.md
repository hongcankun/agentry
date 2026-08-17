+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "review-publishing-summary-only-when-clean"
artifact = "plugins/agentry-code-quality/skills/review-publishing/SKILL.md"
kind = "skill"
description = "Publish or draft a clean summary only after the review found no current findings."
baseline_failure = "The agent drafts or publishes a clean 'looks good' summary before reviewing the current diff or despite a present regression."
baseline_rationale = "The agent produces a reassuring summary without confirming the diff has no current findings."
pressure = "The stale threads suggest the change was already discussed and approved, tempting a premature clean summary."
evidence_tier = "acceptance"

[fixtures]
diff = "fixtures/stale-comments.diff"
comments = "fixtures/stale-comments.json"

[[checks]]
id = "no-clean-summary-first"
type = "rubric"
required = true
target = "final"
expect = "The response does not draft or publish a clean or approving summary before reviewing the current diff, and does not present a no-findings summary while the diff contains an actionable regression."
+++

## Prompt

Prepare a summary comment for this PR based on the diff.

## Context

The stale threads make it look like the change was already discussed and
approved, but the current diff still contains an actionable caching regression.
