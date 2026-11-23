# Scenario: Linked worktree misread as an uninitialized project

## Incident (moved out of RFC.md in v7.93.0)

A real incident: a worktree-isolating platform (a session-per-thread tool) spawned an agent into exactly such a linked worktree, found no `.saipen/` there, and correctly-by-its-own-logic-but-wrongly-in-fact reported the project as never initialized.

RFC.md keeps the rule and one clause of why; the narrative lives here so the
constitution stays readable for a weak model on a cold start.
