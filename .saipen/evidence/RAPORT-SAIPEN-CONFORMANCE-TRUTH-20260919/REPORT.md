# SAIPEN conformance truth: computed but neither rendered nor gated

- reporter: opencode in `V:\___VAC\__K\__CODE\_PY\_LIMISAW` (SAIPEN 8.0.1)
- date: 2026-09-19
- origin findings: `imp-vacterro-limisaw-20260918-4/opencode-04/saipen_improve_SAIPEN.md#RUN-1/IMP-001` (validate) and `#RUN-1/IMP-002` (status); independently reproduced by `opencode-02` in the same cycle
- reporter tickets: T-66 and T-67 on `V:\___VAC\__K\__CODE\_PY\_LIMISAW\.saipen\BOARD.md`
- packet: `SAI-DEFECT-20260919-conformance-truth-not-rendered-not-gated`

## What is wrong

`saipen status` already computes the ONE authoritative conformance fact and puts
it in its JSON payload:

```
payload["conformance_status"] = conformance_status(project_root, gate="core")   # saipen.py:1440
```

It is derived from the canonical validator receipt, and the source comment
(`saipen.py:1433-1436`) calls it "the load-bearing truth that gates
terminal/crew closure", distinguishing it from `payload["conformance"]`
(`saipen.py:1429`), the legacy history-derived hint parsed from the newest LOG
RUN line naming a validator.

Two operator surfaces ignore the authoritative field:

1. **The human render.** `_status`'s printer (`saipen.py:5498-5499`) prints only
   `payload["conformance"]`. It has no branch for `payload["conformance_status"]`,
   so a FAIL tree renders `Conformance: PASS`.
2. **The pre-crew gate.** `saipen validate` (`saipen.py:560-618`) decides
   `VALID`/`VALIDATION_FAILED` purely on `fast_check.validate_texts` over
   STATE/BOARD/LOG. It never reads the receipt, so it answers VALID on a tree
   whose receipt verdict is FAIL. The router names this command as the
   remediation for unhealthy conformance (`router.py` CONFORMANCE_UNHEALTHY /
   CONFORMANCE_UNKNOWN: "run 'saipen validate' before crew work").

Net: one command's human line and one command's verdict both certify a tree that
the SAME command's JSON, in the same instant, labels FAIL.

## Reproduction (measured, not inferred)

On the reporter's tree, HEAD `dce172c`, receipt bound to source `3fa2010`:

```
$ saipen validate --json
{"ok": true, "code": "VALID", "error_count": 0, "errors": [],
 "detail": "canonical STATE/BOARD/LOG pass the fast gate"}

$ saipen status
...
Conformance: PASS (09.09.26 00:19)          <- legacy hint, printed as truth

$ saipen status --json
"conformance": "PASS (09.09.26 00:19)",
"conformance_status": {
  "status": "STALE_FAIL", "gate": "core",
  "reason": "conformance receipt is bound to a different source identity than the current checkpoint",
  "receipt": {"verdict": "FAIL", "exit_code": 1,
              "source_head": "3fa2010460e255a7b2eced3d0f8b3b97fb07408a", ...}
}
```

Same tree, same instant: the human line says PASS, the JSON says STALE_FAIL, and
the gate says VALID.

## Root cause chain

1. `saipen.py:1440` computes `conformance_status` from the receipt — the
   authoritative value.
2. `saipen.py:1429` sets `conformance` from the legacy LOG-prose projection
   (`_project_conformance`, `saipen.py:230-264`).
3. `saipen.py:5498-5499` (`_status` human render) prints only `conformance`;
   `conformance_status` never reaches the operator.
4. `saipen.py:560-618` (`_validate`) imports only `fast_check.validate_texts`
   and never consults the receipt-derived status; the documented pre-crew gate
   passes a FAIL-receipt tree.
5. `conformance.py:1158-1294` classifies CURRENT_FAIL/STALE_FAIL from the
   receipt — a superset of the fast gate that `saipen validate` never runs.

## Impact

- An operator reading only the human `saipen status` line is told PASS on a tree
  the same command reports FAIL — a stale receipt is silently trusted.
- `saipen validate`, the command the router hands a blocked operator, certifies
  an unhealthy conformance state, so crew work proceeds on an unproven source
  identity.
- Cross-project: any project whose receipt is stale/failed but whose canonical
  text is clean hits both surfaces. Only the shared engine can fix it, so the
  reporting project files this packet instead of patching an unrelated install
  (`IMPROVE.md` § 4: nothing is written under `saipen_home`).

## Repair candidates (engine side)

1. In `_status`'s human render, print the receipt-derived truth:
   `conformance_status.status` plus a short reason when present, and demote the
   legacy `conformance` hint to a clearly labelled secondary line (or drop it).
   The authoritative field must never be shadowed by the hint.
2. In `_validate`, consult the same receipt-derived status — or run the same
   gate the receipt is minted from — so the fast gate cannot answer VALID on a
   FAIL-receipt tree; alternatively rename it so it does not present as the
   conformance gate.
3. Have both surfaces share ONE projection function so a future field cannot be
   rendered by one and ignored by the other.

## Reasoning gates for the reporting tickets (T-66, T-67)

- `recurrence:` cross-project. The divergence is in the shared engine, not the
  project: every repository with a stale or failed receipt and clean canonical
  text shows the same one-question-two-answers split. The reporter has seen the
  same "surface presents one verdict while the engine holds another" shape in
  sibling defects (`SAI-DEFECT-20260918-routeless-finish-source-gate`,
  `SAI-DEFECT-20260918-ingress-shell-operator-as-request`).
- `weak_model:` a weak but compliant model cannot avoid this. `saipen validate`
  is the exact command the router names, and it returns VALID with exit 0; an
  operator who reads the human `Conformance:` line sees PASS. Both signals say
  healthy while the load-bearing field says FAIL. The strong fix is mechanical:
  render and gate the field the engine already computes.

## Related

- `SAI-DEFECT-20260918-routeless-finish-source-gate`, `SAI-DEFECT-20260918-diagnostic-verbs-refused-idle`,
  `SAI-DEFECT-20260919-improve-draft-fingerprint-deadend`, `SAI-DEFECT-20260919-improve-complete-stale-seat-unclosable`
  (this root) — same family: a surface presents one verdict while the engine
  holds another, with no route to reconcile them.
