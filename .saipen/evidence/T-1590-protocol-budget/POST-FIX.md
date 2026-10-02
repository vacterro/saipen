# T-1590 — protocol markdown budget: POST-FIX

## The defect

`tools/test_protocol_registry.py:202` asserts

    self.assertLessEqual(measured["human_markdown_total"], 300 * 1024)

`human_markdown_total` is `sum(_size(path) for path in base.rglob("*.md"))` at
`tools/protocol_budget.py:182`, where `_size` normalizes CRLF to LF. The cap
lives ONLY in that test assertion — the registry's own `load_profiles.budgets`
carries no total cap, which is why `python tools/protocol_budget.py` printed
`BUDGET PASS` while the family stayed red.

Measured before the fix:

    human_markdown_total = 308260   cap 307200   over by 1060

That single red test is machine-wide: the VERIFY→REVIEW edge and SHIP both
require a cited core-unit run with `new_red == 0`, so every ticket on the board
was blocked behind it.

## Routes, and why the cut could not touch them

| route | before | cap | headroom |
|---|---|---|---|
| cold | 26861 | 26880 | 19 |
| command_resolution | 46074 | 46080 | 6 |
| ordinary_phase | 40871 | 40960 | 89 |
| ordinary_continue | 34423 | 35840 | 1417 |
| ship_improve | 46372 | 56320 | 9948 |
| single_doc | 37699 | 51200 | 13501 |

`cold` and `command_resolution` had under 20 bytes of slack, so any edit to
BOOT/STYLE/EXECUTION/INDEX/COMMANDS/CONTROLS/IMPROVE had to be net-negative on
every route it belonged to. Measured membership shows `saipen/UI.md` (19497 B)
appears in **no** load route at all: it is loaded on UI work, not on cold start,
continue, command resolution, ordinary phase, ship/improve or single-doc.

Cutting there therefore cannot push any route over its cap — it can only lower
the total. That is the whole reason the cut landed in UI.md and not in
OPS.md/IMPROVE.md, which the ticket text had anticipated.

## What was ruled out before cutting

* Trailing-whitespace residue across all 37 docs: **4 bytes**.
* Multi-blank-line runs: **none**. Tabs: **none**.
* Cross-file duplicated prose: **105 bytes**, and every instance is normative
  text repeated deliberately as a restatement at the point of use.
* Deleting an unreferenced document: **none exists**. Every doc is reachable.
* `saipen/CHANGELOG.md`: **does not exist**, so the usual "trim the changelog"
  escape was never available.

## The cut

`saipen/UI.md`, 19497 → 18368 bytes, **-1129** (`git diff --numstat`: 37
inserted, 58 deleted). The total lands at **307129**, under the 307200 cap by
**71 bytes**.

Every cut removes prose that states *why a rule exists*. No rule, verb,
threshold, refusal code or grammar clause was removed, reworded in a way that
changes its force, or relaxed. The seven sites:

1. **Palette provenance preamble** — the "copied exactly / not reconstructed
   from a generic description / no second palette" precedence rule and the
   "this file wins over a remembered vintage skill" precedence rule are both
   retained. The mandate sentence is retained **byte-for-byte**; see the failed
   attempt below for why that is not optional.
2. **§ Intent** — five feel-goals plus the "not nostalgia as a costume" line,
   condensed to two prose lines. All five goals survive.
3. **§ Predictability preamble** — "A computer is a tool. A hammer does not
   decide." and the "once the model is gone they probe the tool" rationale,
   condensed. The bolded failure statement (the user losing their model of
   what the machine will do) is retained.
4. **§ Revision notes** — the four-item bullet list condensed to one sentence;
   the T-1262 rule ("a rule this document's own base CSS violates is not a
   rule, it is a preference") is retained verbatim.
5. **`body { overflow-x }` CSS comment** — retained the two operative facts
   (`overflow-x: hidden` hides the evidence rather than enforcing the law; it
   produced a QA gate that could never fail) and the remedy (prevent by
   layout, or scroll inside the one genuinely wide element). Dropped the
   worked example of the clipped column/button/error.
6. **`button.primary` CSS comment** — retained both thresholds and the reason
   they coexist (20px dense default for secondary, 24px mandatory for the
   primary action). Dropped the history of implementations picking one and
   silently breaking the other.
7. **§ Tables `--selection` bullet** — retained the rule (sunken bevel first,
   colour second) and the prohibition (fix it in the rule, never in the
   palette; inventing a 22nd colour is the drift the closed set exists to
   stop). Dropped the explanation that the user "sees nothing selected and acts
   on the wrong row".

Two smaller condensations rode along in sites 1 and 5 (`thinking it looked
better` for `"the model thought it looked better"`; `share one value` for the
longer clause) — both are inside retained rules and change no force.

### The failed first attempt — UI.md prose is NOT free-form

The first compaction rewrote the mandate sentence's punctuation:

    - **Golden Default is the default palette.** Its values are copied exactly from
    + **Golden Default is the default palette**, copied exactly from Vintage's

That is a three-character change, and it broke the machine. `tools/validate.py:9464`
does a literal substring test:

    if "**Golden Default is the default palette.**" not in _ui_body:
        fail("UI.md lost the Golden Default default mandate -- merely "
             "mentioning the palette does not make it the mandatory default")

so the canonical validator went from PASS to FAIL on the live tree, and because
`t1412`, `work_reverify`, `log_tail_quarantine`, `public_closure_cli`,
`next_action_deadlock`, `remediation_self_consistency` and others all shell out
to `saipen validate`, the declared family went from **1 new red to 24**:

    family d5b32575a93ba2b9-20261001T223503Z  ran 4616  red 24
      FAIL: UI.md lost the Golden Default default mandate

The rule of thumb T-1590's verify clause encodes is real but incomplete. "Only
prose that states no rule" is not a sufficient test of editability in
`saipen/UI.md`: the validator pins *literal normative strings* in that file, so
prose that reads as motivation can be load-bearing contract surface. Before
compacting any protocol document, grep the validator for that filename. The
mandate sentence is restored byte-for-byte in the final state.

**Anyone repeating this work must run `python tools/validate.py --project-root .
--gate core` and diff the problem count, not just the budget number.** A
compaction that satisfies the byte cap and reds the validator is a regression.

## Honest tradeoff

T-1590's verify clause requires that the compaction "touch only prose that
states no rule", and that is what this is. But the removed text is not
*pointless* — it is the rationale that makes several thresholds hard to
revert in a future edit. Iron law 4's "540 rows because a 480 target kept
forcing a scrollbar" was deliberately KEPT for exactly that reason even though
it was eligible. The margin is also thin: 77 bytes. The next protocol edit of
any size puts this test red again, and that ticket should be treated as
recurring maintenance, not a closed defect.

## Red / green control

| check | before | after |
|---|---|---|
| `tools/protocol_budget.py` human_markdown_total | 308260 (FAIL) | 307123 (PASS) |
| `python -m unittest tools.test_protocol_registry` | red on `test_every_declared_load_budget_is_measured_from_registry` | **Ran 16 tests ... OK** |
| `python -m unittest tools.test_t1502_ui_aa_contract tools.test_adapter_parity` | green | **Ran 19 tests ... OK** |
| family run `a68c609b98622c2f-20261001T221618Z` | new_red 1 (this test) | see FINAL VERDICT below |

The red is not asserted from memory: it is the recorded `new_red` entry of the
family run cited above, on a settled tree, with no test relaxed, skipped or
edited to produce it. The green is a fresh standalone run of the same
unmodified test module.

`test_t1502_ui_aa_contract.py` normalizes and reads `saipen/UI.md` directly
(line 20), so it is the control most at risk from this edit; it passes.

## FINAL VERDICT

    .saipen/evidence/core-unit/50ca3b28f33a9251-20261001T225144Z.json
    {"ok": true, "verdict": "PASS", "ran": 4616, "red": 0, "new_red": [],
     "problems": [], "sandboxes_leaked": []}

4616 tests, zero red, zero new red, no leaked sandbox. The same family measured
`new_red: 1` on this exact defect at `a68c609b98622c2f-20261001T221618Z` and
`new_red: 24` on the intermediate broken state at
`d5b32575a93ba2b9-20261001T223503Z`. All three are recorded; none is asserted
from memory.

## Live-tree conformance is still NOT green — separate, pre-existing debt

`python tools/validate.py --project-root . --gate core` reports 2 problems that
have nothing to do with this ticket and predate it (both files written 20:13,
this edit at 22:30):

    FAIL: runtime manifest names a file git does not track:
          tools/test_improve_error_boundary.py
    FAIL: runtime manifest names a file git does not track:
          tools/test_t1587_stale_closure_recovery.py

Both are untracked (`git status` -> `??`) while `saipen/MANIFEST.json` names
them. Both PASS when run (`Ran 4 ... OK`, `Ran 23 ... OK`), so the work is real
and only the commit is missing. They do not affect the family result — the
core-unit sandbox excludes `.git`, so a "git does not track" check cannot fire
there, which is why the 22:16 run saw one red and not twenty-five.

This is live-tree debt belonging to the tickets that produced those files
(T-1587 and the improve error-boundary work). It is cured by committing them or
dropping the manifest entries — a SHIP decision, recorded here rather than
taken unilaterally.
