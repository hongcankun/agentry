# agentry-collaboration

Author and triage change requests — feature requests, bug reports, and refactor proposals — for work carried out by humans or AI agents.

## When To Install

- Turn a rough need into a clear feature request, bug report, or refactor proposal for a project.
- Judge, prioritize, or decide on incoming change requests.
- Apply one shared rubric — Why-not-How, quantified pain, result-oriented acceptance, bounded scope — to both writing and judging requests.

## Common Use

- Use `/draft-change-request` when turning a need, bug, or refactor into a well-framed request artifact.
- Use `/triage-change-request` when deciding whether an incoming request is worth doing and well-formed, and at what priority.
- Use `change-request` directly when the agent should author or triage a request end to end, grounding it in the request taxonomy, triage framework, and templates.

## Components

| Type | Components |
| --- | --- |
| Skills | [`change-request`](./skills/change-request/SKILL.md) |
| Subagents | None |
| Commands | [`draft-change-request`](./commands/draft-change-request.md), [`triage-change-request`](./commands/triage-change-request.md) |
| Rules | None |

## Install

After adding the Agentry marketplace from the repository README, install this plugin with one of these options:

```bash
# Claude Code plugin only
claude plugin install agentry-collaboration@agentry

# Trae plugin only
traecli plugin install agentry-collaboration@agentry

# From the repository root: orchestrate the plugin install
python3 scripts/agentry.py install --tool claude --global --plugin agentry-collaboration --yes
python3 scripts/agentry.py install --tool trae --global --plugin agentry-collaboration --yes
```
