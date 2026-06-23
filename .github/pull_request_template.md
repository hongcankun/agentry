## Summary

<!-- What changed and why. -->

## Changes

<!-- Bullet the added/changed/removed skills, subagents, rules, or plugins. -->

## Notes

<!-- Optional: call out validation caveats, design decisions, runtime checks, known limitations, or follow-up work. Write N/A if there are no notes. -->

## Checklist

- [ ] Edited the canonical `agentry.json` (not generated packaging)
- [ ] Bumped the affected plugin `version`, and the top-level project release `version` per the rollup (README → Versioning)
- [ ] Ran `python3 scripts/agentry.py generate` and committed the result
- [ ] `python3 scripts/agentry.py generate --check` passes
- [ ] `python3 -m unittest discover scripts/tests` passes
- [ ] Updated `README.md` if the plugin/skill/rule list changed
- [ ] Validated new/changed components with the matching `agentry-authoring` skill
