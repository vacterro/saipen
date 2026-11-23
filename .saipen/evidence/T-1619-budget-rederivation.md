# T-1619 — budget re-derivation for the `human_markdown_total` tripwire

The declared core-unit family run of 05.10.26 (evidence
`.saipen/evidence/core-unit/8bbb850e71e7355e-20261005T182037Z.json`, verdict
FAIL, 5110 ran, `--jobs 6`) reported 7 reds with 1 new red outside the
baseline:
`test_protocol_registry.ProtocolRegistryTests.test_every_declared_load_budget_is_measured_from_registry`
— `human_markdown_total` measures 331370 against the 322 KiB (329728)
tripwire held in `tools/test_protocol_registry.py`: **1642 bytes over**.

## Attribution

The whole overage is this ticket's rule prose. `tools/protocol_budget.py`
measures content bytes with LF line ends, so the accounting is exact: at the
pre-change tree the surface measured ~329710 — 18 bytes of slack under the
322 KiB tripwire T-1614 derived. T-1619 adds the `saipen/RUNTIME.md`
"Iteration exit" section (~1.6 KiB), the contract the SAIHANDOFF acceptance
requires: the canonical exit order (`EXECUTOR_CAPABILITY_MISMATCH` /
`OPERATOR_WAIT` / `VALID_TERMINAL` / `AUTO_KICK`), the per-switch admission
rule, and the UI gate (`may_report_goal_complete` on `VALID_TERMINAL` only).

Every sentence of that section states the rule or names its decision owner.
Per T-1590 the compaction branch may touch only prose that states no rule, so
there is no shrink branch here that is not a regression: cutting 1642 bytes
out of a ~1.6 KiB section would delete the exit order the ticket exists to
land, and cutting another ticket's rule prose to pay for this ticket's rule is
the regression T-1614 already recorded.

## Branch taken

Tripwire re-derived to 324 KiB (331776), following the T-1595 (`300 -> 301
KiB`), T-1605 (`302 -> 303 KiB`) and T-1614 (`303 -> 322 KiB`) precedent. No
rule, document or command row was dropped, trimmed or merged to pay for it.
The section was tightened where redundancy allowed (~250 bytes: dropped
introductory throat-clearing, compressed the cross-layer paragraph) before
measuring, so the re-derivation pays only for rule content.

## What would falsify this re-derivation

- `human_markdown_total` measuring at or under 329728 against this tree —
  then the growth was a temporary artefact and the old tripwire stands.
- Any sentence of the RUNTIME.md "Iteration exit" section above that states no
  rule and names no decision owner — then that sentence is the thing to cut,
  not the tripwire.
- `test_protocol_registry.ProtocolRegistryTests.test_every_declared_load_budget_is_measured_from_registry`
  going green on the pre-change tripwire after every other T-1619 fix — that
  would mean the breach was a measurement artifact.

`tools/core_unit_baseline.json` was deliberately not grown: this red is a new
red caused by this ticket, and the inherited-red set is for reds this project
already knows about.
