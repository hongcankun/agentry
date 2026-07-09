# Design 0002: Rename Non-Conforming Artifacts to the Naming Convention

- **ID:** 0002
- **Form:** RFC
- **Status:** Accepted
- **Answers:** https://github.com/hongcankun/agentry/issues/92
- **Author(s):** hongcankun

## Summary

Issue #92 recorded that skill naming is inconsistent and that the `-manager` skills collide with the agent actor-noun form. PR #94 settled the convention: skills use a capability/activity noun phrase, subagents an actor noun, commands an imperative verb-object, and rules a policy/topic noun. This RFC applies that convention to the artifacts that still violate it. An audit of the whole catalog finds only **8** non-conforming names out of ~40: the seven `-manager` skills (actor-noun form) and one noun-noun command (`quality-gate`). This design renames those eight and leaves every already-conforming name untouched.

## Motivation

The naming convention now lives in the `agentry-authoring` skills and the `authoring-review` checklist, but the catalog does not yet obey it. The desired outcome from #92 is that skill names follow one documented, catalog-consistent convention whose form is clearly distinct from the agent pattern. Until the violators are renamed, the repository ships guidance it does not itself follow — and because Agentry dogfoods its own plugins, the `authoring-review` checklist actively flags the plugin's own seven `-manager` skills as violations. Renaming them makes the catalog self-consistent and removes that standing contradiction.

Whether to do this work is already decided by the accepted issue #92; this design covers only how.

**Non-goals:**

- Not changing the naming convention itself (settled in PR #94) or re-opening the domain-first-vs-gerund debate.
- Not renaming any already-conforming artifact. The convention exists to keep `code-review` (skill) / `code-reviewer` (agent) / `review-code` (command) as three distinct forms; collapsing them is explicitly out of scope.
- Not splitting, merging, or changing the behavior, scope, or contents of any artifact — this is a rename only.
- Not bumping the top-level project release `version` or editing `CHANGELOG.md`; those are release-prep concerns per `README.md#versioning`.

## Current State

The catalog is defined in `agentry.json` and audited against the PR #94 convention as follows:

- **Skills — 7 violations, one family.** The `agentry-authoring` plugin ships `skill-manager`, `subagent-manager`, `command-manager`, `rule-manager`, `prompt-template-manager`, `plugin-manager`; the `agentry-docs` plugin ships `readme-manager`. `-manager` is an actor noun (`-er`), the form reserved for subagents, so each reads as an agent rather than a capability. Every other skill already conforms: `code-review`, `test-engineering`, `review-publishing`, `integrated-review`, `security-audit`, `git-workflow`, `conventional-commits`, `authoring-review`, `change-request`, `design-proposal`.
- **Agents — 0 violations.** `code-reviewer`, `test-engineer`, `security-auditor`, `authoring-reviewer` are all actor nouns.
- **Commands — 1 violation.** `quality-gate` (agentry-code-quality) is a noun-noun compound, unlike its ~20 imperative verb-object siblings (`review-code`, `audit-security`, `prepare-pr`, `update-readme`, …).
- **Rules — 0 violations.** All are topic nouns (`code-style`, `git-workflow`, …).

Each renamed artifact is dogfooded through a `.trae/` symlink back to its canonical directory, and `scripts/agentry.py install --symlink` builds those link names directly from the component name in `agentry.json`.

## Proposed Design

Rename the eight non-conforming artifacts. Skills adopt the `<domain>-authoring` activity-noun form — the same `-ing` activity noun as the already-conforming `test-engineering`, clustered under the `agentry-authoring` plugin theme, and pairing cleanly with the existing `authoring-review` skill and `authoring-reviewer` agent. The command adopts the imperative verb-object form.

| Kind | Plugin | Current | Proposed |
| --- | --- | --- | --- |
| Skill | agentry-authoring | `skill-manager` | `skill-authoring` |
| Skill | agentry-authoring | `subagent-manager` | `subagent-authoring` |
| Skill | agentry-authoring | `command-manager` | `command-authoring` |
| Skill | agentry-authoring | `rule-manager` | `rule-authoring` |
| Skill | agentry-authoring | `prompt-template-manager` | `prompt-template-authoring` |
| Skill | agentry-authoring | `plugin-manager` | `plugin-authoring` |
| Skill | agentry-docs | `readme-manager` | `readme-authoring` |
| Command | agentry-code-quality | `quality-gate` | `run-quality-gate` |

Each rename follows the coordinated sequence in `AGENTS.md#extension-changes`:

1. **Rename the canonical directory / file.** `git mv plugins/agentry-authoring/skills/skill-manager plugins/agentry-authoring/skills/skill-authoring` (and the six siblings); `git mv plugins/agentry-code-quality/commands/quality-gate.md plugins/agentry-code-quality/commands/run-quality-gate.md`.
2. **Update in-artifact identity.** Each skill's `SKILL.md` frontmatter `name:` and its `# Display Heading`. The command file has no `name:` field (its slug is the filename); update only its `# Quality Gate` heading to `# Run Quality Gate`.
3. **Update `agentry.json`.** The `skills` array of `agentry-authoring` (line 53), the `skills` array of `agentry-docs` (line 64), and the `commands` array of `agentry-code-quality` (line 21). No `skillReferences` mapping is affected — the only mapping is `code-review → code-quality/code-style.md`, which touches none of the eight.
4. **Bump plugin versions.** Minor-bump each affected plugin (a rename is a notable, catalog-visible change): `agentry-authoring` `0.4.2 → 0.5.0`, `agentry-docs` `0.2.1 → 0.3.0`, `agentry-code-quality` `0.12.5 → 0.13.0`. The top-level project `version` is not touched here. The root `README.md` plugin version table (`README.md:65-70`) is hand-maintained, not generated, so its three affected version cells must be updated by hand to match — the component counts do not change.
5. **Regenerate packaging.** `python3 scripts/agentry.py generate` refreshes the two marketplaces and the three `plugin.json` files. These enumerate plugins, not individual component names, so only the bumped versions change.
6. **Update cross-references in content** (the non-mechanical edits found by the audit). Beyond the literal `-manager` slugs, this includes the prose "manager skill(s)" framing, which grep for the hyphenated slugs alone does not catch:
   - `AGENTS.md:45` lists five `-manager` skills by name; update to the new names.
   - `scripts/agentry.py:177` comment names `rule-manager, subagent-manager, and command-manager`; update.
   - Root `README.md`: the "matching manager skills" prose at `:77` and the "relevant manager skill" prose at `:101` (collective wording that goes stale once the `-manager` family is renamed), plus the `/quality-gate` invocation at `:94`, and the three version-table cells noted in step 4.
   - `plugins/agentry-authoring/README.md` (prose bullet at `:13`, including its collective "matching manager skill" wording, plus the component table at `:22`) — six skills.
   - `plugins/agentry-docs/README.md` (bullet at `:15` + table at `:22`) and `plugins/agentry-docs/commands/update-readme.md:19`, which wraps the skill: "Follow the `readme-manager` skill …".
   - `run-quality-gate` (remaining occurrences): `plugins/agentry-code-quality/README.md:17,28`, `review-publishing/SKILL.md:21,31,47,53`, `review-publishing/references/comment-format.md:67`, and `publish-review.md:13`.
7. **Re-point dogfooding symlinks.** Remove the eight stale `.trae/` links and recreate them under the new names via `python3 scripts/agentry.py install --tool trae --plugin <plugin> --symlink --component all` (preview with `--dry-run` / `status` first). Restart the CLI afterward.
8. **Validate.** `python3 scripts/agentry.py generate --check`, `python3 scripts/agentry.py validate`, and `python3 -m unittest discover scripts/tests` all pass, and each renamed artifact resolves through its new-named symlink.

## Alternatives Considered

- **Do nothing / keep an exception note.** Leave the eight as-is and document them as a legacy exception. Rejected: it leaves the dogfooded `authoring-review` checklist permanently flagging the repo's own skills, and the convention stays aspirational. The exception note would also have to live in portable skill content (naming Agentry's own extensions and #92), which violates the repository's portability rule; the only clean home for such a note is `AGENTS.md`, which is a weaker outcome than simply conforming.
- **Rename the entire catalog to a fresh scheme (e.g. verb-first gerund).** Rejected: ~93% of names already conform, so this churns correct names for no benefit and, worse, a single fresh scheme collapses the `code-review` / `code-reviewer` / `review-code` three-form distinction the convention was created to protect. It would also require rewriting the PR #94 convention days after shipping it and cannot even express the reference (`git-workflow`) or artifact-noun (`change-request`) skills as verbs.
- **`-management` suffix instead of `-authoring`.** Rejected as weaker: "management" is vaguer than the create/update/review these skills actually perform, and `-authoring` ties directly to the `agentry-authoring` plugin theme, the `authoring-review` sibling skill, and the `authoring-reviewer` agent.
- **Rename only the 7 skills and defer `quality-gate`.** Reasonable and low-risk, but the audit shows `quality-gate` is the one genuine command violation and its fix is cheap; folding it in keeps the catalog fully conforming after a single coordinated change rather than leaving a known straggler.

## Drawbacks

- **It is a breaking rename of public identity.** Skill and command names are how users invoke and install these artifacts; anyone with muscle memory, saved invocations, external references, or scripted installs of `/quality-gate` or the `-manager` skills must adopt the new names. There is no alias mechanism, so old names simply stop resolving.
- **Coordination surface is wide.** Eight artifacts span three plugins, three plugin-version bumps, generated packaging, eight symlinks, four README files (the root README plus three plugin READMEs), `AGENTS.md`, and a source-comment — a single missed reference leaves a dangling name. The audit in this RFC enumerates the full set to mitigate this, but the change must be landed atomically.
- **`prompt-template-authoring` is long** (26 characters). It stays well under the 64-character skill-name limit and reads clearly, so this is cosmetic.

## Prior Art

The catalog itself is the prior art: `test-engineering` (skill) beside `test-engineer` (agent), and `code-review` (skill) beside `code-reviewer` (agent) beside `review-code` (command), already demonstrate the target split. PR #94 (answering #92) is the immediate predecessor that documented the convention this design enforces. Design 0001 established the `docs/designs/` RFC format this document follows.

## Impact

**Reaches:**

- Canonical sources: 7 skill directories under two plugins, 1 command file, and their in-file `name:`/heading identity.
- `agentry.json`: three component arrays and three plugin `version` fields.
- Generated packaging: `.claude-plugin/marketplace.json`, `.trae-plugin/marketplace.json`, and the three affected `plugins/*/.claude-plugin/plugin.json` (version fields only).
- Dogfooding: eight `.trae/` symlinks (seven under `skills/`, one under `commands/`).
- Content cross-references: `AGENTS.md`, `scripts/agentry.py` (one comment), root `README.md` (manager-skill prose, `/quality-gate` invocation, and the hand-maintained version table), `plugins/agentry-authoring/README.md`, `plugins/agentry-docs/README.md`, `plugins/agentry-code-quality/README.md`, `update-readme.md`, `review-publishing/SKILL.md`, `review-publishing/references/comment-format.md`, `publish-review.md`.

**Leaves untouched:**

- All conforming artifacts: every other skill, all four agents, ~20 commands, and all rules.
- The single `skillReferences` mapping (`code-review → code-quality/code-style.md`).
- All rule files under `rules/` (zero occurrences of the eight names) and `.github/`.
- `CHANGELOG.md` historical entries that mention the old names (lines 89, 90, 92, 97, 110, 122) — left as accurate release history per the release-prep-only CHANGELOG convention.
- Descriptive prose using "quality gate(s)" as a concept rather than the `/quality-gate` slug (root `README.md:65,74,99`, `agentry-code-quality/README.md:11`), and the two false-positive "plugin manager" mentions (`plugin-conventions.md:30`, `plugin-review-checklist.md:8`) that refer to an external plugin-manager UI.

## Migration and Rollout

- **Users.** Because the project is pre-1.0, breaking renames are acceptable (per #92). There is no automatic alias; the new names take effect on the release that lands this change. The per-plugin minor version bumps signal the change, and the plugin READMEs and top-level README are updated so install and invocation guidance reference the new names on the same release.
- **Landing.** Execute as one atomic PR so the manifest, packaging, symlinks, and every cross-reference move together — a partial rename would leave the catalog internally inconsistent and break dogfooding here. Use `git mv` so history follows each renamed file.
- **Local dogfooding.** After merge, contributors re-run `scripts/agentry.py install --tool trae --plugin <plugin> --symlink --component all` for the three affected plugins (or `install`/`uninstall` with `--dry-run` first) and restart the CLI to pick up the re-pointed symlinks.

## Rollback

The rename is fully reversible while pre-1.0: a follow-up change can `git mv` the directories back, restore the `agentry.json` keys and versions, regenerate, and re-point symlinks. Nothing is stateful or destructive. The only cost of a late rollback is a second identity churn for anyone who already adopted the new names, so the decision should be settled before release rather than reverted after.

## Risks

- **Dangling reference risk.** The main failure mode is missing one cross-reference and shipping a name that no longer resolves. Mitigation: the Impact section enumerates every occurrence from a full-repo audit; before merge, grep the repo for each of the eight old names and confirm only intended historical (CHANGELOG) and false-positive prose remain.
- **Stale symlink risk.** Old `.trae/` links silently keep working until the directory is gone, masking a miswired install. Mitigation: run `scripts/agentry.py status` after re-install to confirm no drift, and verify each new-named link resolves.

## Observability

Success is confirmed by objective, repo-local signals rather than runtime telemetry:

- `python3 scripts/agentry.py validate` and `generate --check` pass with the renamed manifest.
- `python3 -m unittest discover scripts/tests` passes.
- A repo-wide search for each old name — both the hyphenated slug (`skill-manager`) and the prose family wording (`manager skill(s)`, `quality gate`) — returns only intended historical (`CHANGELOG.md`) and false-positive matches.
- The `authoring-review` checklist, run against the catalog, no longer flags any skill for the actor-noun form — the acceptance signal tied directly to #92's desired outcome.
- Each renamed artifact is discoverable and installable under its new name, and its dogfooding symlink resolves.

## Additional Context

- Answers issue #92 (accepted refactor request). Builds directly on PR #94, which documented the convention.
- Follows the coordination steps in `AGENTS.md#extension-changes` and `AGENTS.md#dogfooding`, and the `docs/designs/` conventions from Design 0001.
- `AGENTS.md:45` names four of the renamed skills as the artifacts to use when authoring extensions; that line is itself part of the cross-reference update, not just documentation of the change.
