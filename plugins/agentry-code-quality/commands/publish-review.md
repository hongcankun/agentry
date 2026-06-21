---
description: Publish existing review findings to a PR, MR, or code review surface after explicit approval.
argument-hint: "[PR/MR/review target] [findings or publish intent]"
---

# Publish Review

Use this command when the user wants to publish existing review findings to a code review, pull request, merge request, or equivalent review surface.

## Inputs

- `[PR/MR/review target]`: Optional review URL, PR/MR number, branch, repository, review id, selected context, or plain-language target. If omitted, infer the review target from the current branch or active repository when platform tooling supports it.
- `[findings or publish intent]`: Optional selected findings, prior review output, quality-gate output, audit report, test review notes, or publication mode. Default: `draft only` unless the current instruction explicitly approves publishing. Supported modes include `draft only`, `summary only`, `inline only`, `publish`, `post now`, `publish without another confirmation`, and `do not publish`.
- Selected text, pasted findings, generated reports, or previous conversation context may be treated as the intended findings source when the tool provides them.

If the review target, findings source, publication mode, authorization, or destination platform is unclear, ask one concise clarifying question before preparing comments.

## Workflow

1. Identify the review target and platform from the provided URL, number, branch, selected context, current repository, or available hosting tools. Treat pull requests, merge requests, code reviews, and equivalent review surfaces as valid targets.
2. Detect available platform capabilities without assuming a specific forge:
   - review metadata, base/head branches, changed files, and diff positions;
   - existing comments or reviews for deduplication;
   - inline comments, summary comments, draft reviews, comment updates, and review-status actions.
3. Gather existing findings from the conversation, selected text, files, or prior output from commands such as `review-code`, `audit-security`, `improve-tests`, or `quality-gate`.
4. Do not run a fresh broad review by default. If no concrete findings are available, stop and ask the user to provide findings or run a review/gate command first.
5. Convert only actionable, concrete findings into publishable comments:
   - use inline comments when the finding maps confidently to a changed file and stable line or diff position;
   - use a summary comment for cross-cutting findings, validation evidence, final verdicts, or findings without a reliable inline location;
   - do not duplicate inline comments in the summary comment; summarize inline findings by category or count and reserve the summary for context not already placed inline;
   - keep low-confidence notes, speculative concerns, and broad hardening ideas out of published comments unless the user explicitly asks to include them.
6. Deduplicate against existing comments when the platform exposes them. Prefer updating or skipping equivalent prior comments over posting duplicates.
7. Default to `draft only` unless the current instruction clearly approves publishing. In draft mode, return the exact comments and summary without calling remote mutation APIs.
8. Present the exact publication plan:
   - target review surface;
   - comment count and locations;
   - summary comment body;
   - any findings omitted and why;
   - whether the plan will be drafted only or published;
   - the platform command or API action that will be used if publishing is approved.
9. Check whether the user has already given explicit publication approval in the current instruction. Treat only clear instructions such as "publish", "publish these comments", "post now", "post them now", or "publish without another confirmation" as approval. Ambiguous wording such as "prepare", "draft", "can you publish", or "ready to publish" is not approval.
10. If explicit approval is already present, publish the prepared comments or review summary without asking for another confirmation. Otherwise, ask for explicit confirmation before any remote mutation.
11. If approved, publish only the approved comments or review summary through the available platform tool/API. If tooling or auth is unavailable, return a ready-to-publish draft and state what blocked publication.

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
