# Rule Writing Guidelines

Guidance for writing clear, scoped, conflict-free agent rules.

## What makes a good rule

1. **Actionable**: State an instruction the agent can follow, not a preference. Prefer "Use 2-space indentation" over "Code should look clean".
2. **Atomic**: One rule covers one behavior. Split unrelated guidance.
3. **Scoped**: Say when the rule applies if it is not always relevant (e.g. "In test files", "For TypeScript only").
4. **Justified only when needed**: Add a short reason only if the rule is non-obvious or counterintuitive.
5. **Testable**: A reader should be able to tell whether the rule was followed.

## Phrasing

- Use imperative voice: "Use", "Never", "Always", "Prefer X over Y".
- Avoid hedging words like "try to", "maybe", "if possible" unless the rule is genuinely optional.
- Keep each rule to one or two sentences.

## Structure

- Name a modular rule file for its policy or topic as a noun (`code-style`, `commit-conventions`), even though the rules inside stay imperative. This keeps rule files distinct from a skill's capability noun, a command's imperative verb-object, and a subagent's actor noun.
- Group related rules under headings (e.g. "Style", "Testing", "Git").
- Order rules from most general to most specific.
- Keep the file short. A long rule file is often ignored; move rarely-needed detail elsewhere or drop it.

## Scope and triggers

State scope explicitly when a rule is conditional:
- by file or path: "In `src/api/**`, ...".
- by language: "For Python files, ...".
- by task: "When writing migrations, ...".

If a rule applies project-wide, no scope statement is needed.

## Frontmatter for modular rule files

Modular rule files under `.cursor/rules/`, `.claude/rules/`, and `.trae/rules/` use YAML frontmatter to control when the rule loads. The fields differ per tool:

- **Cursor** (`.mdc`) and **Trae** (`.md` / `.mdc`): `description`, `globs` (comma-separated path patterns), `alwaysApply` (true = always load). Trae always loads `project_rules.md` regardless. Both map frontmatter to four activation types: always, specific-files (`globs`), intelligent (`description`), and manual. Manual rules load only when referenced in chat — `@rule-name` in Cursor, `#Rule` in Trae (highest priority).
- **Claude Code** (`.md`): `paths` (glob patterns); omit to load always.

Prefer frontmatter-based scoping (`globs` / `paths`) over restating scope in prose when the tool supports it. Root files (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`) take no frontmatter and always load.

## Avoiding conflicts

- Before adding a rule, check existing rules for the same topic.
- Do not state two rules that can both be true but recommend opposite actions.
- When updating, reconcile or remove the older conflicting rule rather than adding a contradicting one.

## What not to add

- Generic advice the agent already follows by default.
- Rules that restate language or framework defaults with no project-specific reason.
- Duplicate rules phrased differently.
