---
description: Tag every step in a plan as [deep] or [exec] and insert STOP markers at tier boundaries so you can switch models or delegate exec work to a subagent.
---

Apply the `personal-plan-model-tiers` skill to $ARGUMENTS.

If no argument is given, use the most recent plan visible in the conversation or the most recent `.scratch/plan-*.md` in the workspace.
