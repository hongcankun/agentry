# agentry-authoring

Authoring skills and review support for building AI agent extensions: create and review skills, subagents, commands, rules, prompt templates, plugins, and marketplaces that follow open agent conventions.

## When To Install

- Create or update AI agent extension artifacts.
- Review extension content for accuracy, clarity, consistency, and portability.
- Evaluate whether an artifact change improves agent behavior before shipping it.
- Manage plugin membership, marketplace metadata, and cross-artifact documentation.

## Common Use

- Use the matching authoring skill while creating or updating an artifact: `skill-authoring`, `subagent-authoring`, `command-authoring`, `rule-authoring`, `prompt-template-authoring`, or `plugin-authoring`.
- Use `/review-authoring` after changing skills, commands, rules, subagents, prompt templates, plugin metadata, or docs that describe those artifacts.
- Use the `authoring-reviewer` subagent for an isolated cross-artifact review when delegation is available.
- Use `authoring-evaluation` and `/evaluate-authoring` to prove an artifact change improves behavior with before/after scenarios; its bundled runner can prepare and collect skill-only current-side runs, and `evaluation-sandbox` covers true tool activation.
- Pair with [`agentry-docs`](../agentry-docs) when README updates are part of the same extension change.

## Components

| Type | Components |
| --- | --- |
| Skills | [`skill-authoring`](./skills/skill-authoring/SKILL.md), [`subagent-authoring`](./skills/subagent-authoring/SKILL.md), [`command-authoring`](./skills/command-authoring/SKILL.md), [`rule-authoring`](./skills/rule-authoring/SKILL.md), [`prompt-template-authoring`](./skills/prompt-template-authoring/SKILL.md), [`plugin-authoring`](./skills/plugin-authoring/SKILL.md), [`authoring-review`](./skills/authoring-review/SKILL.md), [`authoring-evaluation`](./skills/authoring-evaluation/SKILL.md), [`evaluation-sandbox`](./skills/evaluation-sandbox/SKILL.md) |
| Subagents | [`authoring-reviewer`](./agents/authoring-reviewer.md) |
| Commands | [`review-authoring`](./commands/review-authoring.md), [`evaluate-authoring`](./commands/evaluate-authoring.md) |
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
