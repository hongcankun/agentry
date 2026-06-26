# agentry-authoring

Authoring skills and review support for building AI agent extensions: create and review skills, subagents, commands, rules, prompt templates, plugins, and marketplaces that follow open agent conventions.

## When To Install

- Create or update AI agent extension artifacts.
- Review extension content for accuracy, clarity, consistency, and portability.
- Manage plugin membership, marketplace metadata, and cross-artifact documentation.

## Components

| Type | Components |
| --- | --- |
| Skills | [`skill-manager`](./skills/skill-manager/SKILL.md), [`subagent-manager`](./skills/subagent-manager/SKILL.md), [`command-manager`](./skills/command-manager/SKILL.md), [`rule-manager`](./skills/rule-manager/SKILL.md), [`prompt-template-manager`](./skills/prompt-template-manager/SKILL.md), [`plugin-manager`](./skills/plugin-manager/SKILL.md), [`authoring-review`](./skills/authoring-review/SKILL.md) |
| Subagents | [`authoring-reviewer`](./agents/authoring-reviewer.md) |
| Commands | [`review-authoring`](./commands/review-authoring.md) |
| Rules | [`authoring/authoring-review`](../../rules/authoring/authoring-review.md) |

## Install

After adding the Agentry marketplace from the repository README, install this plugin with one of these options:

```bash
# Claude Code plugin only
claude plugin install agentry-authoring@agentry

# Trae plugin only
traecli plugin install agentry-authoring@agentry

# From the repository root: install the plugin and its rules
python3 scripts/agentry.py install --tool claude --global --plugin agentry-authoring --yes
python3 scripts/agentry.py install --tool trae --global --plugin agentry-authoring --yes
```
