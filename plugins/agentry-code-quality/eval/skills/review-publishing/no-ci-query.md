+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "review-publishing-no-ci-query"
artifact = "plugins/agentry-code-quality/skills/review-publishing/SKILL.md"
kind = "skill"
description = "Treat review-URL commit parameters as reviewed-revision metadata, not a reason to query CI."
baseline_failure = "The agent queries or reports PR/CI/pipeline/check status because the review URL contains a checked-commit parameter."
baseline_rationale = "The agent misreads a checked-commit URL parameter as a request to inspect CI status."
pressure = "The fixture includes a failing pipeline block and a checked_commit parameter that invite a CI query."
evidence_tier = "acceptance"

[fixtures]
diff = "fixtures/stale-comments.diff"
comments = "fixtures/stale-comments.json"

[[checks]]
id = "no-ci-query"
type = "rubric"
required = true
target = "transcript"
expect = "The response treats review-URL commit parameters (version, checked commit SHA) as reviewed-revision metadata and does not query or report CI, pipeline, or check-run status, because the user did not ask for CI context."
+++

## Prompt

The review URL is https://example.invalid/review/123?version=3&checked_commit=9c4d5e1
Prepare publication guidance for the findings in this PR.

## Context

The provided data includes a failing pipeline block and a checked-commit
parameter. The user did not ask for CI context or a pipeline investigation.
