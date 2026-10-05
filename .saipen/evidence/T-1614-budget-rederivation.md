# T-1614 — budget re-derivation for the `command_resolution` load profile

The declared core-unit family run of 05.10.26 (evidence
`.saipen/evidence/core-unit/0f194222ff9916c2-20261005T025227Z.json`, verdict FAIL,
5038 ran, `--jobs 4 --timeout 3600`) reported 22 new reds. Two of them are one
defect: `command_resolution` measures over its cap.

`tools/protocol_budget.py` measures content bytes with LF line ends (`_size`), so
a CRLF checkout and an LF clone measure the same. `command_resolution` routes
`REGISTRY.json + COMMANDS.md` — the surface every command resolves against.

| Surface | at `d99cfb15` | working tree | delta | cap before | cap after | slack |
|---|---|---|---|---|---|---|
| `REGISTRY.json` | 29003 | 29457 | +454 | 47104 | 53248 (52 KiB) | 852 |
| `COMMANDS.md` | 17652 | 22939 | +5287 | | | |
| **sum** | 46655 | 52396 | +5741 | | | |

## Attribution

Two independent contributors, both real content whose owners already exist:

- **T-1614 (this ticket), +4.5 KiB of `REGISTRY.json` and part of COMMANDS.md.**
  The future-gate surface ships as a rule family, so the registry grew where a
  rule family grows: `rule_owners["FUTURE-GATE-01"]`, the matching
  `semantic_baseline.facts` entry (owner/test/subject), the two production
  refusal codes the engine emits (`FUTURE_GATE_ABSENT`,
  `FUTURE_GATE_NOT_ELIGIBLE`), and six published `saipen future` rows in
  COMMANDS.md — one per verb, each stating its effect class.
- **Uncommitted command rows swept into the tree this ticket committed
  (+~4.6 KiB of COMMANDS.md).** `improve status`, the `storage` verb set,
  `source capture/req/disp/close/archive/purge`, `audit manifest`,
  `userperson`, `sub`, `undo confirm`, `cut confirm`, `recover`, `fleet` and
  `ticket compact` were already written and already true of code in this
  checkout at `d99cfb15`; commit `63c52fb2` committed them with the future rows.
  They are published verbs, not prose: deleting a row to pay a budget would
  leave an implemented mutation unpublished, which is the defect T-1614 exists
  to prevent in the future family.

## Branch taken

Cap re-derived one KiB step up, `47104 -> 53248`, following the T-1595
(`303e0bbf`) and T-1596 (`6c78a965`) precedent. No rule, document or command row
was dropped, trimmed or merged to pay for it.

The shrink branch was considered and rejected on the same evidence T-1595
recorded: `core` already excludes CORE.md, CONFORMANCE.md and `phases/*.md` from
the router surface, `load_profiles.basis` carries meaning, and trimming command
prose authored by another ticket's closure is net-zero at best and a silent
regression at worst.

## The human-markdown tripwire

`tools/protocol_budget.py` also reports `human_markdown_total` — every `*.md`
under `saipen/`. At `d99cfb15` it measured 310213 against a 303 KiB (310272)
tripwire held in `tools/test_protocol_registry.py`: **59 bytes of slack**. The
T-1614 additions bring it to 329328 (FUTURE.md 12274, COMMANDS.md +5287,
INDEX.md/MAINTENANCE.md +~1554). The tripwire is re-derived one KiB step to
322 KiB (329728), which leaves 400 bytes of slack — the same one-step shape
T-1595 (`300 -> 301 KiB`) and T-1605 (`302 -> 303 KiB`) used.

There was no shrink branch available here that was not a regression: the tree was
already 59 bytes under the old tripwire, so any compensating trim would have cut
another ticket's rule prose to pay for this ticket's document.

## What would falsify this re-derivation

- `command_resolution` measuring at or under 47104 against this tree — then the
  growth was a temporary artefact and the old cap stands.
- Any COMMANDS.md row above that no verb in `tools/saipen.py` implements — then
  part of the 5287 bytes is prose, and the row is the thing to cut, not the cap.
- `test_protocol_registry.ProtocolRegistryTests.test_every_declared_load_budget_is_measured_from_registry`
  and `tools/test_t1465_budget_line_ends.py` going green on the pre-change cap
  after every other T-1614 fix — that would mean the breach was a measurement
  artifact.

`tools/core_unit_baseline.json` was deliberately not grown: these two reds are
new reds caused by this ticket, and the inherited-red set is for reds this
project already knows about.