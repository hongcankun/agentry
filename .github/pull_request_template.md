## Summary

<!-- What changed and why. -->

## Changes

<!-- Bullet the added/changed/removed skills, subagents, rules, or plugins. -->

## Checklist

- [ ] Edited the canonical `agentry.json` (not generated packaging)
- [ ] Bumped the affected plugin `version` (and top-level `version` if the catalog changed)
- [ ] Ran `python3 scripts/agentry.py generate` and committed the result
- [ ] `python3 scripts/agentry.py generate --check` passes
- [ ] `python3 -m unittest discover scripts/tests` passes
- [ ] Updated `README.md` if the plugin/skill/rule list changed
- [ ] Validated new/changed components with the matching `agentry-authoring` skill
