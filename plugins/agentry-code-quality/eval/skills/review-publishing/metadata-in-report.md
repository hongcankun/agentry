+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "review-publishing-metadata-in-report"
artifact = "plugins/agentry-code-quality/skills/review-publishing/SKILL.md"
kind = "skill"
description = "Keep published-comment metadata (URL, id, status) in the report to the user, not inside the comment body."
baseline_failure = "The agent embeds the published comment's URL, id, or publish status inside the comment body instead of keeping them in its report to the user."
baseline_rationale = "The agent folds the publish response into the comment body because that is where it just wrote the finding, instead of separating status metadata from comment content."
pressure = "Publishing returns a URL and comment id, tempting the agent to append them to the comment body as confirmation."
evidence_tier = "acceptance"

[fixtures]
diff = "fixtures/stale-comments.diff"
comments = "fixtures/stale-comments.json"

[[checks]]
id = "metadata-in-report-not-body"
type = "rubric"
required = true
target = "final"
expect = "The published inline comment body contains only the caching-regression finding; the published comment's URL, id, and publish status appear in the agent's report to the user, not embedded inside the comment body."
+++

## Prompt

Publish the caching-regression finding as an inline comment on this PR at
https://example.invalid/review/123, then tell me the link to the published
comment.

## Context

Publishing is approved for this one finding. I just want the caching regression
posted, and the link back once it is up.
