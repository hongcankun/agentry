---
name: review-publishing
description: Draft and publish existing review findings to PRs, MRs, or code review surfaces by mapping findings to inline or summary comments, deduplicating noise, and requiring explicit approval for remote mutations. Use when the user asks to publish, post, draft, or prepare review comments from existing findings.
---

# Review Publishing

Prepare existing review findings for a code review surface, then publish them only when the user has explicitly approved the exact remote mutation. This skill turns findings into useful review comments; it does not discover new findings or decide review status by default.

Follow these principles:
- Publish existing findings only. Do not run a fresh broad review unless the user separately asks for a review or gate workflow.
- Default to `draft only`; prepare exact comments and summary text without mutating remote state.
- Keep inline comments and summary comments distinct. Do not duplicate inline findings in the summary.
- Treat comment publication as separate from approve, request changes, merge, close, resolve, or any other review-status action.
- Stay platform-agnostic. Detect the review target and available tooling before using platform-specific commands or APIs.

## When to use

Use this skill when the task is to:
- publish existing code-review, security-audit, test-review, or quality-gate findings;
- draft inline comments or a summary comment for a PR, MR, code review, or equivalent review surface;
- deduplicate and map findings to review comments;
- prepare comments in `draft only`, `summary only`, or `inline only` mode;
- publish comments after the user explicitly approves comment publication.

## Expected input

Gather as much of the following as available:
- the review target: PR/MR URL or number, branch, repository, review id, selected context, or plain-language target;
- existing findings: prior review output, quality-gate report, audit report, test review notes, pasted findings, selected text, or generated report;
- publication intent: `draft only`, `summary only`, `inline only`, `publish`, `post now`, `publish without another confirmation`, or `do not publish`;
- platform capabilities: metadata, base/head branches, changed files, diff positions, existing comments, and available CLI/API tooling.

If the target, findings source, publication mode, authorization, or platform is unclear, ask one concise clarifying question before preparing comments.

## Workflow

### 1. Resolve the review target

Identify the review target and platform from the provided URL, number, branch, selected context, current repository, or available hosting tools. Treat pull requests, merge requests, code reviews, and equivalent review surfaces as valid targets.

Detect available platform capabilities without assuming a specific forge:
- review metadata, base/head branches, changed files, and diff positions;
- existing comments or reviews for deduplication;
- inline comments, summary comments, draft reviews, comment updates, and review-status actions.

### 2. Gather existing findings

Use findings from the conversation, selected text, files, or prior outputs such as `review-code`, `audit-security`, `improve-tests`, or `quality-gate`.

Do not invent findings or run a fresh broad review by default. If no concrete findings are available, stop and ask the user to provide findings or run a review/gate workflow first.

### 3. Convert findings into comments

Convert only actionable, concrete findings into publishable comments:
- use inline comments when a finding maps confidently to a changed file and stable line or diff position;
- use a summary comment for cross-cutting findings, validation evidence, final verdicts, or findings without a reliable inline location;
- do not duplicate inline comments in the summary comment; summarize inline findings by category or count and reserve the summary for context not already placed inline;
- keep low-confidence notes, speculative concerns, and broad hardening ideas out of published comments unless the user explicitly asks to include them.

Deduplicate against existing comments when the platform exposes them. Prefer updating or skipping equivalent prior comments over posting duplicates.

Before drafting comment bodies, read `references/comment-format.md`; before presenting or publishing them, check the draft against that format. Keep inline comments location-focused, keep summary comments non-duplicative, and keep platform actions, published URLs, comment ids, review ids, and publish status in the agent report rather than in the published comment body.

Published inline comments must use `Problem [Level]`, `Impact`, optional `Notes`, `Suggested fix`, and `_Source: ..._`. Published summary comments must use `Verdict`, `Change summary`, `Findings`, `Coverage`, `Validation`, optional `Notes`, optional `Remaining risk`, and `_Source: ..._`.

### 4. Decide publication mode

Default to `draft only` unless the current instruction clearly approves publishing. In draft mode, return the exact comments and summary without calling remote mutation APIs.

Treat only clear instructions such as `publish`, `publish these comments`, `post now`, `post them now`, or `publish without another confirmation` as approval. Ambiguous wording such as `prepare`, `draft`, `can you publish`, or `ready to publish` is not approval.

### 5. Present or publish

Before publishing, present the exact publication plan:
- target review surface;
- comment count and locations;
- summary comment body;
- any findings omitted and why;
- whether the plan will be drafted only or published;
- whether drafted comment bodies were checked against the published comment format;
- the platform command or API action that will be used if publishing is approved.

If explicit approval is already present, publish the prepared comments or review summary without asking for another confirmation. Otherwise, ask for explicit confirmation before any remote mutation.

If approved, publish only the approved comments or review summary through the available platform tool/API. If tooling or auth is unavailable, return a ready-to-publish draft and state what blocked publication.

## Constraints

- Do not post, update, resolve, approve, request changes, merge, close, or otherwise mutate remote review state unless the user has explicitly approved that exact mutation in the current instruction or in response to the publication plan.
- Treat approval to publish comments as approval only for comment publication. It does not authorize approving, requesting changes, merging, closing, resolving threads, or changing review status.
- Do not invent findings, validation results, URLs, comment ids, or platform capabilities.
- Do not publish secrets, credentials, exploit payloads, or harmful code. Redact sensitive evidence when needed.
- Stay platform-agnostic: prefer generic review-target language and use platform-specific commands only after detecting the target and available tooling.
- Respect the requested publication mode. In `draft only` or `do not publish` mode, never call a remote mutation API.

## Output

Return:
- the review target and detected platform/tooling;
- the findings source used;
- the publication mode selected;
- comments drafted, published, skipped, or blocked;
- published URLs, comment ids, or review ids when available;
- any remaining manual steps when publication could not be completed.

## References

- `references/comment-format.md` — agnostic published inline and summary comment body formats, including level labels, optional notes, source footers, and non-duplication rules.
