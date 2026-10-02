# T-1434 / SRC-088 — LIMISAW problem: SCOUT measurements and plan

Date: 2026-09-20. Session astra. SAIPEN HEAD 46400306 + dirty tree.
Mission: eliminate conformance states whose validator demands a remediation the
canonical CLI cannot perform (8 milestones in SRC-088).

## External acceptance fixture, current state (measured)

Command (carriers cleared so a foreign root can bind):

```text
$env:SAIPEN_PROJECT_ROOT=''; $env:SAIPEN_PROJECT_LINEAGE='';
$env:SAIPEN_AGENT=''; $env:SAIPEN_HOST_SESSION=''
python tools\validate.py --gate core        # cwd = V:\___VAC\__K\__CODE\_PY\_LIMISAW
-> rc=1; Validation FAILED: 25 problem(s), 22 warning(s)
```

Capture: `V:\_TEMP_\limisaw-before.txt`.

Grouped root causes (exact validator lines):

- A. `closure-evidence` x21 — T-008, T-009, T-015, T-19..T-36: "## DONE but
  carries no current-cycle verification evidence (classifier: no current-cycle
  VERIFY boundary; reverify: no current-tree PASS re-verification receipt)".
  Remediation text says "re-verify with real evidence" but no CLI exists.
- B. `source receipts` x2 — SRC-007 `SOURCE_CORRUPTION` active digest mismatch
  plus its credential gate. Only MISROUTED-class recovery exists.
- C. `improve report` x1 — four cycles `imp-vacterro-limisaw-20260918-1/3/4`:
  reports carrying BOARD headings (red control 22), stale
  protocol_fingerprint, stale source_head; cycle lifecycle has no
  cycle-level terminalization that clears this while reports stay immutable.
- D. `core sweep [sweep-ticket-link]` x1 — six SWEEP entries (T-53..T-55,
  T-66..T-68) produced tickets "without recurrence: and weak_model:"; no
  canonical writer exists for those linkage fields.
- Not validator-visible but named by SRC-088: T-73 (and T-66/T-67) BLOCKED_EXTERNAL
  because the defect was implemented upstream; closure provenance only
  represents local patch ownership.

Observation for Milestone 6 (cross-repo provenance): even this READ-ONLY
measurement of LIMISAW required clearing all four session carriers, because the
same ambient-lineage pin refuses an explicit foreign root (paths.py:648-655).
Cross-project observation and closure therefore share one root assumption
class: `fix == local patch`, `authority == current repository`.

## Engine surface today (facts to build on)

- `tools/saipen_engine/debt.py:1186` `reverify_work(root, work, agent, ...)`,
  `:1401` `current_tree_reverify(root, work)`, RV-NNNNNN receipt allocation at
  `:1138`. Engine logic exists; no public CLI verb (`saipen` usage line has no
  `work`/reverify entry), so validator remediation names an unreachable move.
- Improve lifecycle: `abort` refuses once dispositions exist; `retire` handles a
  single seat; no cycle-level reconcile (previous aborts: T-1411, T-1414-era).
- Source intake supports MISROUTED recovery classes only; no tombstone/retire
  reason set (STALE_CREDENTIAL / EMPTY_STALE_SOURCE / SUPERSEDED_SOURCE /
  ORPHANED_RECEIPT / MISROUTED_PROJECT_BINDING).
- Closure provenance source grammar: `release:<id>`, `T-###`, `SRC-###`
  (`saipen_engine/closure.py:58`); no EXTERNAL_IMPLEMENTATION_LOCAL_VERIFICATION
  variant.

## Plan (one bounded Work at a time, per SRC-088 order)

1. M1 canonical work reverify CLI: expose `reverify_work` as a first-class
   canonical operation (preferred spelling `saipen work reverify <T-###>`),
   with immutable RV receipt binding, idempotence on same tree+contract,
   validator remediation text pointing at the real verb, router routing toward
   it, 10 regression families from SRC-088.
2. M2 external implementation resolution + `EXTERNAL_IMPLEMENTATION_LOCAL_VERIFICATION`
   closure provenance; re-evaluate T-73, then T-66/T-67 individually.
3. M3 conservative source retirement/tombstones with machine-readable reasons.
4. M4 strict improve cycle finite exit: seat semantics (T-1411 preserved) +
   cycle-level reconcile; solve sweep-ticket linkage by writer or derivation.
5. M5 validator remediation self-consistency regression (every emitted
   remediation resolves to a registered command or typed EXTERNAL_ACTION).
6. M6 provenance-model audit for `fix == local patch` assumptions.
7. M7 LIMISAW end-to-end recovery using only the new canonical commands.
8. M8 cross-project regression fixtures + double full-suite run.

## Exact next action

Enter BUILD for Milestone 1: implement the `work reverify` command surface
(CLI + parser/registry/effects + validator remediation + router), with the
SRC-088 regression matrix as its acceptance. LIMISAW stays the external
fixture; no LIMISAW product source is touched.
