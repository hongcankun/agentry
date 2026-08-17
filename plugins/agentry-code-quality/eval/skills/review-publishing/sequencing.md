+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "review-publishing-sequencing"
artifact = "plugins/agentry-code-quality/skills/review-publishing/SKILL.md"
kind = "skill"
description = "Gather current findings before reading existing threads for dedupe."
baseline_failure = "The agent reads existing review threads before deriving current findings from the diff."
baseline_rationale = "The agent treats existing discussion as prerequisite context instead of post-findings dedupe input."
pressure = "The remote discussion is noisy and contains stale, refuted comments, making dedupe feel urgent."
evidence_tier = "acceptance"

[fixtures]
diff = "fixtures/stale-comments.diff"
comments = "fixtures/stale-comments.json"

[[checks]]
id = "findings-first"
type = "rubric"
required = true
target = "transcript"
expect = "The response derives current findings from the diff before using existing comments, and uses existing comments only for dedupe or thread-state classification rather than as a source of findings."

[[checks]]
id = "no-thread-prefetch"
type = "rubric"
required = true
target = "transcript"
expect = "The response does not prefetch or read existing review discussion while resolving the review target or in parallel with metadata, changed files, and diff collection."
+++

## Prompt

Review this changed PR and prepare publication guidance for the findings you identify.

## Context

The diff contains a real regression (an unbounded session cache that is never
invalidated on TTL expiry). The remote discussion already contains stale and
refuted comments that should not be treated as current findings.
