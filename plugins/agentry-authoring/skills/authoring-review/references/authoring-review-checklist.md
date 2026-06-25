# Authoring Review Checklist

Use this checklist to review AI agent extension content and related documentation.

## Accuracy

- Claims match the repository, manifest, generated packaging, command behavior, and documented workflows.
- Referenced files, commands, components, plugins, versions, and install paths exist or are explicitly marked as examples.
- Generated files are treated as derived output when canonical sources exist.
- Examples are realistic and do not promise unsupported behavior.

## Clarity

- The artifact's audience can tell when to use it and what outcome to expect.
- Descriptions include concrete trigger conditions, not only a broad summary.
- Steps are ordered as a user or agent should perform them.
- Constraints and approval requirements are explicit where mistakes would be costly.

## Consistency

- Names, paths, versions, scope, terminology, and responsibilities match related artifacts.
- Repeated claims across README, rules, skills, commands, subagents, and plugin metadata describe the same behavior.
- Cross-plugin references name the other plugin clearly when needed.
- Tool-specific details live in the artifact that owns them, not in reusable generic content.

## Redundancy and Verbosity

- Repeated guidance is intentional and does not create maintenance drift.
- Main instructions stay concise; detailed checklists, schemas, and examples live in references.
- Long lists and procedural blocks are justified by actual user workflow.
- The content avoids filler adjectives, duplicate caveats, and restating obvious mechanics.

## Simplicity and Readability

- The workflow uses the fewest necessary concepts and steps.
- Headings, lists, and examples make the content easy to scan.
- Output contracts are specific enough to be followed without over-constraining simple cases.
- The artifact avoids nested or competing responsibilities.

## Portability

- Content avoids machine-specific paths, private project names, hidden local context, and environment assumptions unless the artifact is explicitly project-scoped.
- Paths are relative where the package should be portable.
- A reusable skill or subagent does not depend on a project rule being installed unless the dependency is bundled or restated.
- Tool-specific fields and formats match the target tool's conventions.

## Trigger Quality

- Skills describe what they can do and when to use them.
- Commands describe explicit user-invoked workflows and expected arguments.
- Rules define always-on policy without duplicating full procedural skills.
- Subagents use noun-based role names, concrete delegation triggers, minimal tools, and a clear output contract.

## Final Review

- Findings are tied to concrete `file:line` evidence.
- Suggested fixes preserve the intended behavior and artifact boundary.
- The verdict reflects whether the reviewed authoring content is ready for its intended handoff: pass, pass with warnings, or request changes.
