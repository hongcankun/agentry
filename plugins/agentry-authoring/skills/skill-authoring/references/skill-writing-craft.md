# Skill Writing Craft

Guidance for writing a skill that an agent can find, load, and act on well. This covers craft beyond the format rules in `convention-summary.md`. Proving that a skill change actually improved agent behavior is a separate downstream evaluation stage, not part of authoring.

## Contents

- Description: what and when, never the workflow
- Concision as a shared resource
- Match the guidance form to the failure mode
- Degrees of freedom
- Examples and defaults
- Terminology
- Organizing references
- Discovery and scripts

## Description: what and when, never the workflow

The description decides whether an agent loads the skill at all. State **what** the skill does and **when** to use it — triggers, symptoms, and contexts.

Do **not** summarize the skill's step-by-step workflow in the description. A description that recites the process becomes a shortcut the agent follows instead of reading the body, so it may run a shortened or wrong version of the workflow. Keep the process in `SKILL.md`; keep the description about relevance.

- Good: "Use when creating a new skill or fixing a skill folder."
- Avoid: "Create a skill by initializing the folder, writing metadata, then validating." (This is the workflow, not a trigger.)

## Concision as a shared resource

The context window is shared with everything else the agent is doing. Only add context the agent does not already have. Challenge each paragraph: does it earn its tokens, or is it something the agent knows by default? Cut restated language defaults, generic advice, and duplicate explanations.

## Match the guidance form to the failure mode

Pick the form of guidance based on how the agent tends to go wrong. The fix for one failure mode backfires on another.

| Failure mode | Use this form |
| --- | --- |
| Knows the rule, skips it under pressure | Prohibition plus a short self-check list of the tempting workarounds |
| Output has the wrong shape (bloated, buried result) | A positive recipe or contract: state what the output should contain, in order |
| Omits a required element | A required structural slot in the template the agent fills in |
| Behavior should be conditional | A conditional keyed to an observable predicate ("when the diff is empty, ...") |

State the foundational rationale behind a non-obvious rule so the agent can apply it correctly in cases the rule does not spell out. Discovering the agent's real baseline failure empirically is a separate downstream evaluation stage — write guidance for the failure you can already name, not an imagined one.

## Degrees of freedom

Match how prescriptive the instruction is to how fragile the task is.

- **High freedom (prose):** open-ended judgment tasks with many valid paths.
- **Low freedom (exact steps or a script):** fragile, order-sensitive, or destructive operations. Say "run this, do not modify" and give the command.

## Examples and defaults

- One excellent, complete example beats several mediocre ones. Do not dilute the same pattern across many languages.
- Offer a default with an escape hatch, not a menu of equivalent options.
- Write reusable guidance, not a narrative of how a problem was solved once.

## Terminology

- Use one term per concept throughout the skill; do not alternate synonyms.
- Avoid time-sensitive statements. If old guidance must stay, fold it into a short "old patterns" note rather than dating the main instructions.

## Organizing references

- Keep references **one level deep** from `SKILL.md`. Agents may partially read files reached through another reference, so do not chain `SKILL.md` to a file that points to yet another file for essential content.
- Use a flowchart only for a non-obvious decision; use prose or a list for linear or reference material.

## Discovery and scripts

- Cover the words an agent would search for: error strings, symptoms, tool names, and synonyms.
- Scripts should solve the problem, not punt it back to the agent with vague failures. Avoid unexplained constants; document why a value is what it is.
- Make execution intent explicit: say whether the agent should run a script or read it as reference.
