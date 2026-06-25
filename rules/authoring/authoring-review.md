---
# Trae: always load this rule; description aids intelligent activation.
# Claude Code: ignores these keys, and loads always since `paths` is omitted.
description: When to use authoring review for AI agent extension content.
alwaysApply: true
---

# Authoring Review

Follow the `authoring-review` skill as the authoritative procedure for how to review AI agent extension content (scope, quality dimensions, findings format, and validation). The rules below describe when authoring review is useful and what it should cover.

## When to review

When creating or modifying AI agent extension content, use the `authoring-review` skill or an equivalent review process before treating the work as complete. This applies to:

- skills, subagents, commands, rules, prompt templates, plugin metadata, or marketplace metadata;
- README files, contributor guides, project instructions, or other docs that describe extension behavior, install paths, packaging, or repository workflow;
- generated packaging, local installs, or dogfooding links that must stay aligned with canonical sources.

For local uncommitted work, review early enough to catch drift before committing. Treat generated packaging as evidence of sync, not as source of truth; compare it back to the project's canonical manifest and source component files.

## Review expectations

- Check accuracy, clarity, consistency, redundancy, verbosity, portability, trigger quality, and cross-artifact alignment.
- Keep reusable extension content tool-agnostic unless the artifact explicitly owns a tool-specific format or workflow.
- Do not substitute authoring review for separate specialist coverage when a change also affects implementation behavior, security boundaries, or test adequacy.

## Related

- `agentry-authoring` plugin — the plugin this rule ships alongside.
- `authoring-review` skill — the full authoring review procedure and checklist.
- `authoring-reviewer` agent — a subagent that runs the review in an isolated context, following the `authoring-review` skill.
- `review-authoring` command — an explicit command entry point for authoring-quality review.
