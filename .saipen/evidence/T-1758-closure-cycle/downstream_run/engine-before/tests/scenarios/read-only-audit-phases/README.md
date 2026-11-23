Test: a host with no filesystem-write capability sets `mode: read-only`
(RFC § 1.3), then the user runs `saipen markhunt` (or `saipen prepare` /
`saipen validate`). Per § 1.3, these audit/validate phases are reachable
but only in report-only form: the agent runs the audit / freshness-pack /
conformance check and reports the result in chat, and MUST NOT record it
-- no `## BLOCKED` tickets from MARKHUNT, no `kitchen/` or handoff payload
from PREPARE, no structural repair from VALIDATE (the corruption is
reported, left as-is). This is a behavioral test (agent decision-making
about what a read-only phase may write), not a structural one -- the
assertion is entirely in whether the agent degrades to reporting instead
of writing `.saipen/`.
