+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "review-publishing-inline-anchor"
artifact = "plugins/agentry-code-quality/skills/review-publishing/SKILL.md"
kind = "skill"
description = "Anchor an inline comment to the earliest actionable changed line."
baseline_failure = "The agent anchors the inline comment to the last changed line or the end of the hunk rather than the earliest changed line that makes the finding actionable."
baseline_rationale = "The agent anchors where its attention lands last after reading the whole hunk, defaulting to the most recently read line rather than tracking back to the earliest actionable one."
pressure = "The regression spans several added lines, so more than one line could plausibly host the comment."
evidence_tier = "acceptance"

[fixtures]
diff = "fixtures/stale-comments.diff"
comments = "fixtures/stale-comments.json"

[[checks]]
id = "earliest-actionable-line"
type = "rubric"
required = true
target = "final"
expect = "The inline comment for the caching regression is anchored to the earliest changed line that makes the finding understandable and actionable, not to a trailing line of the hunk."
+++

## Prompt

Prepare an inline comment for the caching regression in this PR and say which
changed line it should anchor to.

## Context

The regression is introduced across the added lines of the `get` method. The
earliest changed line that makes the finding actionable is where the cache is
first read/populated without invalidation.
