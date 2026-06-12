---
name: agent-skill-creator
description: Create and refine Agent Skills that follow the open Agent Skills convention, including planning skill scope, writing SKILL.md metadata and instructions, organizing scripts references and assets, and validating the final package. Use when a user asks to create a new skill, turn a repeatable workflow into a reusable skill, or review and fix an existing skill folder.
---

# Agent Skill Creator

Create or improve an Agent Skill as a portable folder centered on `SKILL.md`, with optional `scripts/`, `references/`, and `assets/` directories.

Follow these conventions:
- Keep the skill lightweight. Put only the core guidance in `SKILL.md`.
- Use metadata for discovery: `name` and `description` must clearly tell the agent what the skill is, what it can do, and when to use it.
- Use progressive disclosure: keep detailed docs in `references/`; keep deterministic or repeatable logic in `scripts/`.
- Package the skill as a self-contained folder that another agent can use without hidden context.

## When to use

Use this skill when the task is to:
- create a new Agent Skill from a request, workflow, or idea;
- convert repeated manual steps into a reusable skill package;
- review or repair an existing skill so it matches the Agent Skills convention.

## Expected input

Provide as much of the following as available:
- the skill goal and target user requests;
- the workflow, checklist, or domain knowledge the skill should encode;
- any scripts, templates, examples, or reference documents that should be bundled;
- whether the task is **new creation** or **review/fix of an existing skill**.

If important details are missing, infer reasonable defaults from the user request and keep the skill focused.

## Directory convention

Build the skill around this structure:

```text
<skill-name>/
├── SKILL.md
├── scripts/      # optional executable helpers
├── references/   # optional detailed docs
├── assets/       # optional templates/resources used in outputs
└── ...           # other files only when clearly necessary
```

Use kebab-case for the skill name directory and metadata `name`.

## Workflow

### 1. Define the skill boundary

Clarify:
- the job this skill helps an agent accomplish;
- the concrete capabilities it should provide;
- the situations that should trigger the skill.

Write the description so it includes all three points in one compact sentence.

### 2. Initialize or inspect the skill folder

For a new skill, run:

```bash
python3 scripts/init_skill.py <skill-name> --path <output-directory>
```

For an existing skill, inspect the current folder and keep only files that are part of the actual skill package.

### 3. Write `SKILL.md`

Ensure `SKILL.md` contains:
- YAML frontmatter with `name`, `description`;
- a concise explanation of the skill purpose;
- the main execution workflow the agent can follow directly;
- explicit pointers to `scripts/`, `references/`, and `assets/` when needed.

Keep `SKILL.md` practical. After reading it, an agent should be able to complete most normal uses without loading every reference file.

### 4. Place content at the right level

Use this rule:
- Put durable, high-level instructions in `SKILL.md`.
- Put detailed domain docs, checklists, schemas, or examples in `references/`.
- Put deterministic logic or reusable automation in `scripts/`.
- Put templates, static resources, or output materials in `assets/`.

Avoid duplication between `SKILL.md` and `references/`.

### 5. Validate the package

Run:

```bash
python3 scripts/validate_skill.py <skill-directory>
```

Validation checks for:
- required `SKILL.md` file;
- valid YAML frontmatter;
- required `name` and `description` fields;
- allowed metadata fields only;
- optional folders only if they are correctly named.

### 6. Review quality before delivery

Check the package against `references/authoring-checklist.md`.

At minimum confirm:
- the description is specific and triggerable;
- the folder is self-contained;
- scripts have real logic and meaningful names;
- references add depth without repeating the main instructions;
- the skill is portable and does not rely on hidden local context.

## Output requirements

Deliver a skill folder that:
- can be copied or packaged as a standalone Agent Skill;
- follows the folder convention in `references/convention-summary.md`;
- uses clear file names and relative paths;
- is validated before handoff.

## References

Read these files when needed:
- `references/convention-summary.md` — compact summary of the Agent Skills convention and design principles.
- `references/authoring-checklist.md` — final review checklist for quality and portability.
