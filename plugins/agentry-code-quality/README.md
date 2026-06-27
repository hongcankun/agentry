# agentry-code-quality

Code review and test-engineering skills, slash commands, and specialist subagents that catch correctness, security, maintainability, and test-quality issues with actionable guidance.

## When To Install

- Review code changes before merge.
- Review a PR/MR and publish actionable findings as review comments.
- Improve, repair, or assess automated tests.
- Run a pre-merge quality gate.
- Publish existing review findings to a review surface.

## Components

| Type | Components |
| --- | --- |
| Skills | [`code-review`](./skills/code-review/SKILL.md), [`test-engineering`](./skills/test-engineering/SKILL.md), [`review-publishing`](./skills/review-publishing/SKILL.md) |
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
