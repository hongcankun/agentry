# Authoring checklist

Use this checklist before delivering a skill.

## Metadata

- `SKILL.md` exists.
- YAML frontmatter is valid.
- `name` uses kebab-case.
- `description` states what the skill does and when to use it, with no embedded step-by-step workflow.
- No unsupported metadata fields are present.

## Structure

- Required and optional directories are named correctly.
- File names are descriptive.
- Paths in `SKILL.md` match real files.
- No junk files, editor cache, or unrelated project files are included.

## Instruction quality

- `SKILL.md` gives enough guidance to handle common cases directly.
- `SKILL.md` is concise and action-oriented.
- Every paragraph earns its tokens: no restated language defaults or context the agent already has.
- Details are moved into `references/` instead of bloating the main file.
- Instructions do not depend on hidden assumptions.

## Craft

- The guidance form matches the failure mode: prohibition plus self-check for skipped rules, a positive recipe for wrong-shaped output, a required slot for omitted elements, a conditional for conditional behavior.
- Non-obvious rules state a short rationale.
- Prescriptiveness matches task fragility: prose for open-ended judgment, an exact command or script for fragile or destructive steps.
- Terminology is consistent: one term per concept, no alternating synonyms.
- No time-sensitive statements (or they are contained in an "old patterns" note).
- Examples use one strong, complete case rather than the same pattern in many languages.
- The skill offers a default with an escape hatch, not a menu of equivalent options.
- References are one level deep from `SKILL.md`.
- The description and body cover the terms an agent would search for: symptoms, tool names, and synonyms.

## Scripts

- Each script has a real purpose.
- Script names describe the action they perform.
- Scripts can be run independently.
- Scripts solve the problem rather than punting vague failures back to the agent.
- Constants are documented; no unexplained constants.
- Any required arguments are documented in `SKILL.md`, and execution intent (run vs. read as reference) is explicit.

## Portability

- Relative paths are used throughout.
- The folder can be copied or zipped as a standalone skill.
- The skill does not rely on machine-specific absolute paths.
- The skill does not assume access to external context that is not bundled or stated.

## Final check

- The package matches the intended user scenario.
- The level of detail is appropriate.
- The skill is ready for packaging or direct installation.
