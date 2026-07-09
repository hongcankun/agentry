# Rule Review Checklist

Use this checklist when reviewing an agent rule file.

## Clarity

- Each rule is a clear, actionable directive.
- Rules use imperative voice ("Use", "Never", "Prefer").
- No vague or unenforceable statements.
- Each rule covers a single concern.

## Scope

- Conditional rules state when they apply (file, language, or task).
- Project-wide rules are not over-scoped.
- Scope statements match real paths and conventions in the project.

## Consistency

- No two rules contradict each other.
- No duplicate rules phrased differently.
- Terminology is consistent across rules.

## Value

- Each rule adds project-specific guidance, not generic defaults.
- No dead rules referring to removed tools, paths, or workflows.
- The file is concise enough to be read and followed.

## Format

- A modular rule file is named for its policy/topic as a noun (`code-style`), not as an action or role, while the rules inside stay imperative.
- The file is in the correct scope location (project repo vs. user/global home config dir).
- The file matches the project's existing rule convention (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.cursor/rules/`, `.claude/rules/`, `.trae/rules/`).
- Modular rule files include the correct frontmatter for the tool (`globs`/`alwaysApply` for Cursor and Trae; `paths` for Claude Code); root files have none.
- Headings group related rules.
- No unrelated content mixed into the rule file.

## Final check

- The rule set reflects the intended behavior.
- Updates preserved unrelated existing rules.
- The file is ready for the agent to use.
