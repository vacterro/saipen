# Statistical Habits of Modern LLMs

This retrieval map links common agent errors to existing countermeasures. It creates no new rule.

1. **Consultant drift:** filler replaces an actionable answer. Counter: `STYLE.md` and the STATE style contract.
2. **Following the last speaker instead of authority:** recent chat displaces canonical state. Counter: `CORE.md` authority and disk-first rules.
3. **Hedging or guessing:** the agent offers options without choosing, or invents missing facts. Counter: `CORE.md` selection and insufficient-information rules.
4. **Claiming an unperformed read or test:** a plausible PASS replaces evidence. Counter: `CORE.md` session trace and `tools/audit_checks.py` controls.
5. **Inventing plausible details:** paths, versions or shortcuts are fabricated. Counter: the closed command registry and `tools/validate.py` path checks.
6. **Copying an example instead of applying its rule:** example and law diverge. Counter: conformance checks in `tools/validate.py`.
7. **Stopping at the first green:** narrow tests hide relevant failures. Counter: SHIP gates and the declared test family.
8. **Describing work instead of doing it:** an empty session must say so under `CORE.md`'s trace rule. A LOG entry that promises future work violates its event rule; `tools/validate.py` rejects future-tense first clauses, with a red control in `tools/audit_checks.py`. Check these existing counters before claiming a new gap.
9. **Assuming unread material is empty:** a truncated file or queue is treated as complete. Counter: `CORE.md`'s read-to-end rule.
