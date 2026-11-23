# T-1624 — budget re-derivation for the `human_markdown_total` tripwire

`tools/test_protocol_registry.py::test_every_declared_load_budget_is_measured_from_registry`
measured `human_markdown_total` at **334663** bytes against the 324 KiB
(331776) tripwire: **2887 bytes over**. Measured 2026-10-06 with
`protocol_budget.load_profiles(Path("saipen"))` (content bytes, LF line ends).

## Attribution

The whole overage is this ticket's rule prose. T-1623 left the surface at the
cap on purpose and said so (`T-1623-budget-rederivation.md`: "the next change
that grows the human markdown surface will have to re-derive this cap with its
own evidence file"). T-1624 adds:

| document | bytes | what it states |
|----------|------:|----------------|
| `saipen/RUNTIME.md` | +2488 | the HOST-INTEGRATION-01 section: the taxonomy and its one decision rule, the capability contract and the nine-state model, `host doctor|repair|mode`, the three installer rules for a prompt-blocking hook (stage/self-test/activate, installed runtime, `HOOK_BOOTSTRAP` and the retired stand-in), and the hook-only start of the authority service |
| `saipen/COMMANDS.md` | +330 | the `host doctor|repair|mode` row, `DEGRADED` in the admission state list, `launch <host>` in place of `launch opencode` |
| `saipen/EXECUTION.md` | +208 | the admission paragraph: only an ADMITTED session is MECHANICAL, a gap degrades by default, a conflict blocks in every mode |

Pre-change surface: 334663 - 3026 = 331637, i.e. 139 bytes of slack under the
old cap.

Every sentence added states a rule or names its owner; the section had no
protocol-level statement before this ticket (the rule lived only in module
docstrings and the adapter note). The RUNTIME section was tightened once
before measuring (2648 -> 2488 bytes: merged two sentences, moved the three
hook rules into one list). Per T-1590 the compaction branch may touch only
prose that states no rule, so no further shrink exists that is not a
regression.

## Branch taken

Tripwire re-derived to **327 KiB (334848)**, the next whole KiB that holds the
measured surface, following the T-1595, T-1605, T-1614 and T-1619 precedent.
185 bytes of slack remain. No rule, document or command row was dropped,
trimmed or merged to pay for it. The declared load profiles did not move:
`cold` 26007 / 27648, `command_resolution` 53580 / 54272.

## What would falsify this re-derivation

- `human_markdown_total` measuring at or under 331776 against this tree;
- a sentence in the three additions above that states no rule and names no
  owner;
- any declared profile in `saipen/REGISTRY.json` measuring over its budget.
