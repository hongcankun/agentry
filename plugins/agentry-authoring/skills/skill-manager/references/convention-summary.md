# Agent Skills convention summary

This reference captures the core convention used by the Agent Skills format.

## Core structure

An Agent Skill is a folder centered on `SKILL.md`.

```text
<skill-name>/
├── SKILL.md
├── scripts/
├── references/
├── assets/
└── ...
```

- `SKILL.md` is required.
- `scripts/` is optional and holds executable helpers.
- `references/` is optional and holds detailed documentation.
- `assets/` is optional and holds templates or reusable resources.

## Progressive disclosure model

Skills are typically consumed in three layers:
1. discovery through metadata in `SKILL.md` frontmatter;
2. activation through the full `SKILL.md` instructions;
3. execution through scripts and referenced files only when needed.

This means:
- keep metadata precise;
- keep `SKILL.md` concise but actionable;
- move details into `references/`;
- move repeatable logic into `scripts/`.

## Metadata expectations

Use YAML frontmatter at the top of `SKILL.md`.

Required:
- `name`: Max 64 characters. Lowercase letters, numbers, and hyphens only. Must not start or end with a hyphen.
- `description`: Max 1024 characters. Non-empty. Describes what the skill does and when to use it.

Optional:
- `license`: License name or reference to a bundled license file.
- `compatibility`: Max 500 characters. Indicates environment requirements (intended product, system packages, network access, etc.).
- `metadata`: Arbitrary key-value mapping for additional metadata.
- `allowed-tools`: Space-separated string of pre-approved tools the skill may use. (Experimental)

Write `description` so it states what the skill does and when to use it.

## Authoring principles

- Prefer clarity over cleverness.
- Keep the skill self-contained and portable.
- Avoid hidden dependencies and unstated assumptions.
- Bundle only the context an agent actually needs.
- Use relative paths when referring to local resources.
- Give scripts and references descriptive names.

## Content placement guide

Use `SKILL.md` for:
- purpose;
- trigger situations;
- main workflow;
- concise operational rules.

Use `references/` for:
- longer explanations;
- detailed schemas;
- examples;
- review checklists;
- domain-specific documentation.

Use `scripts/` for:
- deterministic setup;
- validation;
- code generation helpers;
- repeatable transformations.

Use `assets/` for:
- templates;
- sample resources reused in final outputs;
- static support files.

## Portability checklist

A finished skill should work as a normal folder that another skills-aware agent can discover and use. Avoid relying on hidden team context, machine-specific paths, or undocumented manual steps.
