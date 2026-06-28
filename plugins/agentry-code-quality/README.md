# agentry-code-quality

Code review, integrated review orchestration, test-engineering, and review-publishing skills plus specialist subagents that catch correctness, security, maintainability, and test-quality issues with actionable guidance.

## When To Install

- Review code changes before merge.
- Coordinate a multi-track review across code, security, tests, and validation.
- Review a PR/MR and publish actionable findings as review comments.
- Improve, repair, or assess automated tests.
- Run a pre-merge quality gate.
- Publish existing review findings to a review surface.

## Common Use

- Use `/improve-tests` before merge when a feature or bug fix needs stronger automated coverage.
- Use `/quality-gate` for an integrated pre-merge check across code review, testing, and validation.
- Use `/review-pr` when a PR/MR should be reviewed and findings published in one workflow.
- Use `/publish-review` when review findings already exist and only need to be drafted or posted.
- Pair with [`agentry-git`](../agentry-git) when the same workflow should continue into `/prepare-commit`, `/prepare-pr`, or `/finish-pr`.

## Components

| Type | Components |
| --- | --- |
| Skills | [`code-review`](./skills/code-review/SKILL.md), [`test-engineering`](./skills/test-engineering/SKILL.md), [`review-publishing`](./skills/review-publishing/SKILL.md), [`integrated-review`](./skills/integrated-review/SKILL.md) |
| Subagents | [`code-reviewer`](./agents/code-reviewer.md), [`test-engineer`](./agents/test-engineer.md) |
| Commands | [`review-code`](./commands/review-code.md), [`review-pr`](./commands/review-pr.md), [`improve-tests`](./commands/improve-tests.md), [`quality-gate`](./commands/quality-gate.md), [`publish-review`](./commands/publish-review.md) |
| Rules | [`code-quality/code-review`](../../rules/code-quality/code-review.md), [`code-quality/code-style`](../../rules/code-quality/code-style.md), [`code-quality/testing`](../../rules/code-quality/testing.md) |

## Install

After adding the Agentry marketplace from the repository README, install this plugin with one of these options:

```bash
# Claude Code plugin only
claude plugin install agentry-code-quality@agentry

# Trae plugin only
traecli plugin install agentry-code-quality@agentry

# From the repository root: install the plugin and its rules
python3 scripts/agentry.py install --tool claude --global --plugin agentry-code-quality --yes
python3 scripts/agentry.py install --tool trae --global --plugin agentry-code-quality --yes
```
