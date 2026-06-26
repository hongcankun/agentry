# Agentry

Agentry is a collection of reusable extensions for AI coding agents: skills, subagents, commands, and rules. The extensions are grouped into tool-agnostic plugins, with Claude Code and Trae packaging generated from the same canonical manifest.

[`agentry.json`](./agentry.json) is the source of truth for plugin metadata, versions, component membership, and rule associations. Extension sources live under [`plugins/`](./plugins) and [`rules/`](./rules); generated packaging should be regenerated, not edited by hand.

## Install

Claude Code and Trae both install Agentry as a plugin marketplace. Install the marketplace once, then install the plugins you want.

### Claude Code

```bash
claude plugin marketplace add hongcankun/agentry
claude plugin install agentry-code-quality@agentry
claude plugin install agentry-security@agentry
claude plugin install agentry-git@agentry
claude plugin install agentry-authoring@agentry
claude plugin install agentry-docs@agentry
```

Update later with `claude plugin marketplace update agentry`. In the interactive Claude Code UI, use the same commands with a leading slash.

### Trae

```bash
traecli plugin marketplace add hongcankun/agentry
traecli plugin install agentry-code-quality@agentry
traecli plugin install agentry-security@agentry
traecli plugin install agentry-git@agentry
traecli plugin install agentry-authoring@agentry
traecli plugin install agentry-docs@agentry
```

Update later with `traecli plugin marketplace upgrade agentry`. In the interactive Trae UI, use the same commands with a leading slash.

### Install Script

The marketplace commands install a plugin's skills, subagents, and commands. Use [`scripts/agentry.py`](./scripts/agentry.py) when you also want associated rules, project-local installs, symlinked installs from a checkout, dry runs, or status checks.

```bash
# Add the marketplace, install the plugin, and install its rules at user scope
python3 scripts/agentry.py install --tool trae --global --plugin agentry-code-quality --yes

# Install all of a plugin's components from this checkout at project scope
python3 scripts/agentry.py install --tool claude --plugin agentry-code-quality

# Symlink components from this checkout for local dogfooding
python3 scripts/agentry.py install --tool trae --plugin agentry-code-quality --symlink

# Check whether installed files match the canonical sources
python3 scripts/agentry.py status --tool trae --plugin agentry-code-quality
```

The script supports two delivery channels: `marketplace`, which calls the target tool's plugin CLI at user scope, and `checkout`, which copies or symlinks components from this repository. Rules are installed separately because the plugin formats do not deliver rules. Run `python3 scripts/agentry.py install --help` for the full option reference.

## Plugins

Agentry currently ships **5 plugins** with **37 components**: 14 skills, 4 subagents, 12 commands, and 7 rules. Use `python3 scripts/agentry.py inventory --details` for the full manifest-derived inventory.

| Plugin | Version | Best for | Skills | Agents | Commands | Rules |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| [`agentry-code-quality`](./plugins/agentry-code-quality) | 0.10.6 | Code review, test design, test repair, review publishing, and pre-merge quality gates. | 3 | 2 | 4 | 3 |
| [`agentry-security`](./plugins/agentry-security) | 0.4.0 | Threat-driven audits for auth, user input, file/network access, crypto, secrets, payments, and other sensitive code. | 1 | 1 | 1 | 1 |
| [`agentry-git`](./plugins/agentry-git) | 0.6.1 | Branching, Conventional Commits, pull requests, merged-branch cleanup, and release flow. | 2 | 0 | 5 | 2 |
| [`agentry-authoring`](./plugins/agentry-authoring) | 0.4.0 | Creating and reviewing skills, subagents, commands, rules, prompt templates, plugins, and marketplaces. | 7 | 1 | 1 | 1 |
| [`agentry-docs`](./plugins/agentry-docs) | 0.2.0 | README creation and maintenance for software repositories. | 1 | 0 | 1 | 0 |

### Choosing Plugins

- Install [`agentry-code-quality`](./plugins/agentry-code-quality) for everyday engineering review work: review a diff, improve tests, run a quality gate, or publish review findings.
- Install [`agentry-security`](./plugins/agentry-security) when agents need a dedicated security audit workflow and a proactive security-auditor subagent.
- Install [`agentry-git`](./plugins/agentry-git) when agents should help with local commits, pull requests, merged-branch cleanup, and release publishing.
- Install [`agentry-authoring`](./plugins/agentry-authoring) when you author agent extensions and want the matching manager skills plus cross-artifact review.
- Install [`agentry-docs`](./plugins/agentry-docs) when the main need is README maintenance without the broader authoring toolkit.

### Component Types

- **Skills** are reusable procedures agents load when a task matches their description.
- **Subagents** are specialist agent profiles for delegated review or execution in an isolated context.
- **Commands** are slash-command workflows for explicit user-invoked tasks.
- **Rules** are policy guidance installed separately because plugin formats do not deliver rules.

## Local Development

- [`agentry.json`](./agentry.json) — canonical, tool-agnostic manifest. **Edit this**, then regenerate derived files.
- [`plugins/`](./plugins) — each plugin's skills (`skills/<name>/SKILL.md`), subagents (`agents/<name>.md`), and commands (`commands/<name>.md`).
- [`rules/`](./rules) — tool-agnostic rules, organized by topic; associated with plugins via the manifest.
- [`scripts/agentry.py`](./scripts/agentry.py) — maintenance CLI: `install`/`status`/`uninstall` a plugin's components into a tool's directories, report the manifest with `inventory`, and `generate` per-tool packaging from the manifest.
- [`scripts/tests/`](./scripts/tests) — stdlib-only (`unittest`) tests for `scripts/agentry.py`.

Regenerate generated packaging after manifest or extension changes, or validate the repository before opening a PR:

```bash
python3 scripts/agentry.py generate          # regenerate all packaging (or pass claude/trae)
python3 scripts/agentry.py generate --check  # verify generated packaging is current
python3 scripts/agentry.py validate          # run repository consistency checks
```

## Versioning

Versions live in [`agentry.json`](./agentry.json) and propagate to generated packaging.

- **Per-plugin `version`** controls delivery through plugin marketplaces. Bump only plugins whose installable content changed: patch for fixes and clarifications, minor for added capabilities, and major for breaking changes after `1.0.0`. While a plugin is still `0.x`, breaking changes may use a minor bump.
- **Top-level `version`** is the project release snapshot used for git tags such as `vX.Y.Z`. Bump it only in explicit release-prep changes, based on the most severe plugin, catalog, or CLI change included in the release.

| Bump | When the release's worst change is… |
| --- | --- |
| **patch** | only fixes — a plugin's per-plugin **patch**, or an `agentry.py` fix |
| **minor** | something **added** — a plugin's new component (per-plugin **minor**), a plugin **added**, or a new `agentry.py` capability (new flag, channel, or subcommand) |
| **major** | after `1.0.0`, something **removed, renamed, or breaking** — a plugin's per-plugin **major**, a plugin **removed or renamed**, or a breaking `agentry.py` CLI/behavior change |

Normal change PRs bump only affected per-plugin versions and regenerate packaging. Release-prep PRs bump the top-level project `version`, update [`CHANGELOG.md`](./CHANGELOG.md) with `git-cliff --output CHANGELOG.md`, and regenerate packaging if the manifest changed.

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the contributor checklist and [`AGENTS.md`](./AGENTS.md) for maintainer and agent-specific rules.

## License

Agentry is released under the [MIT License](./LICENSE).
