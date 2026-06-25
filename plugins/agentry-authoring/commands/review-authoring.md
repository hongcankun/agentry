---
description: Review skills, commands, rules, subagents, prompt templates, plugin metadata, or related docs for authoring quality and cross-artifact consistency.
argument-hint: "[authoring target or intent]"
---

# Review Authoring

Use this command when the user wants an explicit authoring-quality review of AI agent extension content or documentation that describes those extensions.

## Inputs

- `[authoring target or intent]`: Optional path, plugin name, branch, commit range, diff, selected files, or plain-language review intent. If omitted, review current uncommitted or unmerged authoring-related changes.
- Selected files, pasted diffs, prior discussion, or generated metadata may be treated as the intended review scope when the tool provides them.

If the review scope, base branch, or intended artifact type is unclear, ask one concise clarifying question before doing a broad review.

## Workflow

1. Follow the `authoring-review` skill as the authoritative review procedure, including its references and output contract.
2. Establish the exact review scope and intent:
   - for local work, inspect repository state and determine changed files with `git status --short --branch` and the relevant `git diff` command;
   - for a branch or commit range, identify the base/target and inspect the range diff;
   - for a plugin name, inspect that plugin's skills, commands, agents, generated metadata, README entry, and manifest registration when present;
   - for named files, review only those files unless related artifacts are needed to verify consistency.
3. Prefer delegating the review to `authoring-reviewer` when subagents are available, because it has isolated context and the same review contract.
4. If subagents are unavailable, run the review directly by following the `authoring-review` skill.
5. Verify cross-artifact consistency when practical by checking canonical manifests, generated packaging state, README/plugin listings, project guidance, local install or dogfooding entries, and referenced paths.
6. Run lightweight validators when they materially improve confidence, such as skill validation, plugin validation, generated-packaging sync checks, or relevant status/inventory commands.
7. Filter out subjective rewrite preferences. Report only issues with concrete accuracy, clarity, consistency, redundancy, verbosity, portability, trigger-quality, or maintainability impact.

## Constraints

- Review only; do not edit, stage, commit, push, publish, or mutate remote state unless the user explicitly asks in a separate instruction.
- Stay within authoring content quality. If implementation behavior, security-specific risk, or test adequacy is central to the target, flag it as out of scope for this command and recommend separate specialist coverage.
- Treat generated packaging as evidence of sync, not as the canonical source when manifest or source files exist.
- Keep the review scoped to the requested artifacts unless adjacent files are necessary to prove or disprove drift.
- A clean review is valid. Do not invent style nits to fill the report.

## Output

Return:
- a concise scope summary naming the authoring surfaces inspected;
- findings grouped by severity, each with `file:line`, problem, impact, and suggested fix;
- a short cross-artifact alignment summary;
- validation results, including checks run, skipped, or blocked;
- a one-line verdict: pass, pass with warnings, or request changes.
