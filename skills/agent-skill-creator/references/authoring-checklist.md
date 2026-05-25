# Authoring checklist

Use this checklist before delivering a skill.

## Metadata

- `SKILL.md` exists.
- YAML frontmatter is valid.
- `name` uses kebab-case.
- `description` clearly states what the skill is, what it can do, and when to use it.
- No unsupported metadata fields are present.

## Structure

- Required and optional directories are named correctly.
- File names are descriptive.
- Paths in `SKILL.md` match real files.
- No junk files, editor cache, or unrelated project files are included.

## Instruction quality

- `SKILL.md` gives enough guidance to handle common cases directly.
- `SKILL.md` is concise and action-oriented.
- Details are moved into `references/` instead of bloating the main file.
- Instructions do not depend on hidden assumptions.

## Scripts

- Each script has a real purpose.
- Script names describe the action they perform.
- Scripts can be run independently.
- Any required arguments are documented in `SKILL.md`.

## Portability

- Relative paths are used throughout.
- The folder can be copied or zipped as a standalone skill.
- The skill does not rely on machine-specific absolute paths.
- The skill does not assume access to external context that is not bundled or stated.

## Final check

- The package matches the intended user scenario.
- The level of detail is appropriate.
- The skill is ready for packaging or direct installation.
