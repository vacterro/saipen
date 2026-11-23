# T-2025 — re-derivation of the `ordinary_phase` route budget

`tools/protocol_budget.py` (the route admission gate, T-1670 / SRC-191) measured
`ordinary_phase` at **42791** bytes against the declared 40 KiB (40960) budget:
**1831 bytes over**. Measured 2026-11-04 with
`protocol_budget.load_profiles(Path("saipen"))` (content bytes, LF line ends).

## Attribution

The whole overage is the rule-stating block the DONE T-2019 added to
`saipen/phases/verify.md`:

| document | bytes | what it states |
|----------|------:|----------------|
| `saipen/phases/verify.md` | +1848 | the `SUITE-PREFLIGHT-01` section (`### Long declared suites`): affected-subset selection before a long declared suite, failing-script-only rerun after a red, `--fail-fast` partial-FAIL semantics, the `process_s`/`overhead_s` duration split and its flush rule, and the advisory (never a gate) speed ticket |

The route is `CORE.md` (32117) closed with the largest active phase
(`@active_phase_max`, now `verify.md` 10674). Pre-change route:
42791 - 1848 = 40943, i.e. 17 bytes of slack under the old cap. Every other
phase route carries large slack (next largest: `CORE.md` + `ship.md` = 37807),
so the overage is this one document, not a stale route shape.

Every sentence in the block states a rule or names its owner
(`<!-- RULE-OWNER: SUITE-PREFLIGHT-01 -->`). Per T-1590 the compaction branch
may touch only prose that states no rule, so there is no shrink of this block
that is not a regression: removing any of it removes the only protocol-level
statement of the preflight rule. T-1842 compacted the older `verify.md` prose;
this block is new rule content, not slack.

## Branch taken

Tripwire re-derived to **42 KiB (43008)**, the next whole KiB that holds the
measured route, following the T-1595, T-1596, T-1614, T-1619 and T-1624
precedent. 217 bytes of slack remain. No rule, document or command row was
dropped, trimmed or merged to pay for it. The load graph and every other
declared budget in `saipen/REGISTRY.json` are unchanged.

## What would falsify this re-derivation

- `ordinary_phase` measuring at or under 40960 against this tree;
- a sentence in the SUITE-PREFLIGHT-01 block that states no rule and names no
  owner;
- any other declared profile in `saipen/REGISTRY.json` measuring over its
  budget.
