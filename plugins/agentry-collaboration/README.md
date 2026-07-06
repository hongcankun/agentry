# agentry-collaboration

Author and triage collaboration artifacts across the change lifecycle: change requests that frame the *Why* (feature requests, bug reports, refactor proposals) and design proposals that answer the *How* (RFCs and design docs), for work carried out by humans or AI agents.

## When To Install

- Turn a rough need into a clear feature request, bug report, or refactor proposal for a project.
- Turn an accepted change request into a design proposal or RFC that states the approach, alternatives, impact, migration, and risks.
- Judge, prioritize, or decide on incoming change requests, and triage incoming design proposals on their design merits.
- Apply a shared rubric to both writing and judging each artifact — Why-not-How and quantified pain for requests; justified approach, bounded impact, and right-sized weight for designs.

## Common Use

- Use `/draft-change-request` when turning a need, bug, or refactor into a well-framed request artifact.
- Use `/triage-change-request` when deciding whether an incoming request is worth doing and well-formed, and at what priority.
- Use `change-request` directly when the agent should author or triage a request end to end, grounding it in the request taxonomy, triage framework, and templates.
- Use `/draft-design-proposal` once a request is accepted, to turn it into a design proposal (inline note, lightweight doc, or full RFC) that answers *how* to build it.
- Use `/triage-design-proposal` when deciding whether an incoming design is sound and the right weight, yielding accept / revise / reject / needs-info.
- Use `design-proposal` directly when the agent should author or triage a design end to end, pairing naturally after `change-request` once a request is accepted.
- Pair with [`agentry-code-quality`](../agentry-code-quality) when an accepted design has been built and the resulting PR needs correctness, security, and test-quality review.

## Components

| Type | Components |
| --- | --- |
| Skills | [`change-request`](./skills/change-request/SKILL.md), [`design-proposal`](./skills/design-proposal/SKILL.md) |
| Subagents | None |
| Commands | [`draft-change-request`](./commands/draft-change-request.md), [`triage-change-request`](./commands/triage-change-request.md), [`draft-design-proposal`](./commands/draft-design-proposal.md), [`triage-design-proposal`](./commands/triage-design-proposal.md) |
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
