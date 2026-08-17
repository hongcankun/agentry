+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "authoring-evaluation-skill-only-round-trip"
artifact = "plugins/agentry-authoring/skills/authoring-evaluation/SKILL.md"
kind = "skill"
description = "Use the bundled runner when no project runner is available."
baseline_failure = "The agent hand-builds cases or summarizes results instead of using the skill-bundled prepare and collect runner."
baseline_rationale = "Skill-only installs should still produce a standard manifest, JSONL-backed results, and scorecard without Agentry's project runner."
pressure = "The user is evaluating from a copied skill folder with no scripts/agentry.py checkout available."
evidence_tier = "normal"

[[checks]]
id = "uses-eval-runner-prepare"
type = "required-text"
required = true
target = "final"
value = "eval_runner.py prepare"

[[checks]]
id = "uses-eval-runner-collect"
type = "required-text"
required = true
target = "final"
value = "eval_runner.py collect"

+++

## Prompt

I copied only the authoring-evaluation skill folder into another project. I have
one scenario Markdown file and want the full prepare, evaluation, and scorecard
round trip without using Agentry's `scripts/agentry.py`. What should I run?

## Context

The copied skill folder includes its `scripts/` directory. There is no Agentry
checkout or project runner in this project.
