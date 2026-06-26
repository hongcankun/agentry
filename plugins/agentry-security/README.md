# agentry-security

Security audit skill, command, and specialist subagent for threat-driven code review across auth, user input, file and network access, cryptography, secrets, payments, and other sensitive surfaces.

## When To Install

- Audit security-sensitive code changes.
- Map attack surface and trust boundaries.
- Hunt for vulnerabilities with exploit scenarios and concrete remediations.

## Components

| Type | Components |
| --- | --- |
| Skills | [`security-audit`](./skills/security-audit/SKILL.md) |
| Subagents | [`security-auditor`](./agents/security-auditor.md) |
| Commands | [`audit-security`](./commands/audit-security.md) |
| Rules | [`security/security-audit`](../../rules/security/security-audit.md) |

## Install

After adding the Agentry marketplace from the repository README, install this plugin with one of these options:

```bash
# Claude Code plugin only
claude plugin install agentry-security@agentry

# Trae plugin only
traecli plugin install agentry-security@agentry

# From the repository root: install the plugin and its rules
python3 scripts/agentry.py install --tool claude --global --plugin agentry-security --yes
python3 scripts/agentry.py install --tool trae --global --plugin agentry-security --yes
```
