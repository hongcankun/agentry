---
name: authoring-review
description: Review AI agent authoring content for accuracy, clarity, consistency, redundancy, verbosity, portability, trigger quality, and cross-artifact alignment. Use when reviewing skills, commands, rules, subagents, prompt templates, plugin metadata, or documentation that describes those extension components.
---

# Authoring Review

Review AI agent extension content and its supporting documentation as portable product surface. This skill focuses on whether authored content is correct, clear, consistent, concise, reusable, and aligned with related artifacts.

## When to use

Use this skill when asked to review, audit, or quality-check:
- skills, commands, rules, subagents, prompt templates, plugin manifests, or marketplace metadata;
- README files, contributor guides, project instructions, or other docs that describe extension behavior, install paths, workflows, or packaging;
- cross-artifact changes where the same behavior is described in multiple places.

Implementation behavior, security risk, and test adequacy are outside this skill's scope. Note those concerns when they affect the reviewed artifacts, but handle them with separate specialist coverage.

## Workflow

1. **Establish scope and intent.** Identify the artifacts under review and what each one is meant to teach, trigger, enforce, package, or document. If reviewing local work, inspect the relevant diff first.
2. **Load governing context.** Read the project guidance, manifest entries, neighboring components, relevant README sections, and artifact-specific references needed to judge correctness. Treat generated files as evidence of generated state, not as the source of truth when canonical sources exist.
3. **Review artifact quality.** Check that names, descriptions, triggers, metadata, tools, paths, examples, procedures, and output contracts match the component's intended role and target conventions. When a finding depends on artifact-specific conventions, consult the relevant authoring workflow or local convention for that artifact when available.
4. **Review cross-artifact alignment.** Compare repeated claims across skills, commands, rules, subagents, plugin metadata, README sections, and project guidance. Flag drift where surfaces describe different behavior, version, scope, install path, or responsibility.
5. **Assess writing quality.** Prefer precise, actionable, tool-agnostic wording. Flag avoidable redundancy, vague adjectives, long procedural blocks that belong in references, missing caveats, and instructions that are harder to follow than necessary.
6. **Validate when useful.** Run lightweight checks when they materially improve confidence: search for duplicated or stale terms, check referenced paths, inspect generated manifests, run package validators, or verify documented commands.
7. **Filter and classify.** Report only concrete, actionable issues. Avoid speculative rewrites and subjective style preferences without a clear accuracy, usability, portability, or maintenance impact.

## Output

Return a self-contained review with:
- the review scope and authoring surfaces inspected;
- findings grouped by severity, each with `file:line`, problem, impact, and suggested fix;
- a brief cross-artifact alignment summary;
- validation evidence for checks run, or a note that the review was static/read-only;
- a final verdict: pass / pass with warnings / request changes.

## References

Read `references/authoring-review-checklist.md` when doing a full review or when the change touches multiple artifact types.
