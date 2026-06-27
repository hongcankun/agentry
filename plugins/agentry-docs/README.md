# agentry-docs

Lightweight documentation authoring for software repositories, currently focused on accurate README creation and maintenance.

## When To Install

- Create a new project README.
- Refresh or simplify an existing README.
- Keep repository documentation clear and aligned with project structure.
- Install only README-focused documentation help without the broader extension-authoring toolkit.

## Components

| Type | Components |
| --- | --- |
| Skills | [`readme-manager`](./skills/readme-manager/SKILL.md) |
| Subagents | None |
| Commands | [`update-readme`](./commands/update-readme.md) |
| Rules | None |

## Install

After adding the Agentry marketplace from the repository README, install this plugin with one of these options:

```bash
# Claude Code plugin only
claude plugin install agentry-docs@agentry

# Trae plugin only
traecli plugin install agentry-docs@agentry

# From the repository root: orchestrate the plugin install
python3 scripts/agentry.py install --tool claude --global --plugin agentry-docs --yes
python3 scripts/agentry.py install --tool trae --global --plugin agentry-docs --yes
```
