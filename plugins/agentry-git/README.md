# agentry-git

Git workflow and Conventional Commits skills for branching, merging, rebasing, pull requests, releases, and well-formed commit messages.

## When To Install

- Prepare focused commits with Conventional Commit messages.
- Create or update pull requests.
- Clean up merged branches safely.
- Prepare and publish project releases.

## Common Use

- Use `/prepare-commit` to stage a focused change set and create a local Conventional Commit on an appropriate branch.
- Use `/prepare-pr` to draft PR title/body, then push and create or update the PR only after explicit confirmation.
- Use `/finish-pr` after merge to fast-forward the base branch, delete the merged local feature branch, and prune stale remote-tracking refs.
- Use `/prepare-release` and `/publish-release` for the release-prep and post-merge publish stages.

## Components

| Type | Components |
| --- | --- |
| Skills | [`git-workflow`](./skills/git-workflow/SKILL.md), [`conventional-commits`](./skills/conventional-commits/SKILL.md) |
| Subagents | None |
| Commands | [`prepare-commit`](./commands/prepare-commit.md), [`prepare-pr`](./commands/prepare-pr.md), [`finish-pr`](./commands/finish-pr.md), [`prepare-release`](./commands/prepare-release.md), [`publish-release`](./commands/publish-release.md) |
| Rules | [`vcs/conventional-commits`](../../rules/vcs/conventional-commits.md), [`vcs/git-workflow`](../../rules/vcs/git-workflow.md) |

## Install

After adding the Agentry marketplace from the repository README, install this plugin with one of these options:

```bash
# Claude Code plugin only
claude plugin install agentry-git@agentry

# Trae plugin only
traecli plugin install agentry-git@agentry

# From the repository root: install the plugin and its rules
python3 scripts/agentry.py install --tool claude --global --plugin agentry-git --yes
python3 scripts/agentry.py install --tool trae --global --plugin agentry-git --yes
```
