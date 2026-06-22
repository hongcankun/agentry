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

1. Must follow the `review-publishing` skill as the authoritative procedure, including its published comment body format and output contract.
2. Establish the review target and findings source from the command input, selected context, current repository, or previous conversation.
3. Do not run a fresh broad review by default. If no concrete findings are available, stop and ask the user to provide findings or run a review/gate workflow first.
4. Draft inline comments and/or a summary comment from existing findings using the published comment body format. Default to `draft only` unless the current instruction clearly approves publishing.
5. Present the publication plan and ask for explicit confirmation before any remote mutation unless explicit publish approval is already present in the current instruction.
6. If approved, publish only the approved comments or review summary through the available platform tool/API. If tooling or auth is unavailable, return a ready-to-publish draft and state what blocked publication.

## Constraints

- Do not post, update, resolve, approve, request changes, merge, close, or otherwise mutate remote review state unless the user has explicitly approved that exact mutation in the current instruction or in response to the publication plan.
- Treat approval to publish comments as approval only for comment publication. It does not authorize approving, requesting changes, merging, closing, resolving threads, or changing review status.
- Stay platform-agnostic: prefer generic review-target language and use platform-specific commands only after detecting the target and available tooling.

## Output

Return:
- the review target and detected platform/tooling;
- the findings source used;
- the publication mode selected;
- comments drafted, published, skipped, or blocked;
- published URLs, comment ids, or review ids when available;
- any remaining manual steps when publication could not be completed.
