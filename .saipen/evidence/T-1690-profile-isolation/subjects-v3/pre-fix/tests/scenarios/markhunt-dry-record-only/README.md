Test: user runs `saipen markhunt` on a project with real issues present.
Per `phases/markhunt.md`, the agent MUST record every finding as a
`[MARKHUNT]`-tagged ticket under `## BLOCKED` (never `## TODO`) and MUST
NOT fix, cap, or delete anything itself -- unlike `HUNT`, which caps at 5
tickets and free-deletes obvious junk. This is a behavioral test (agent
discipline under an audit-only phase), not a structural one -- no
`.saipen/` fixture to validate against; the assertion is that MARKHUNT
stays dry and uncapped where HUNT would act.
