# T-1973 — the external recovery surface reported a clean sweep over a defect

Measured 2026-10-31. Ticket `regression: required`.

## What the ticket was actually about

T-1973 was filed against a stale proof: EX-000029 had verified T-1653 against
engine generation `sha256:06c1149a…`, while the running engine was
`sha256:6f2cd4c3…`.

Three clauses were failing, and all three were re-measured with the engine's own
predicates before anything was changed:

| clause | measured | verdict |
|---|---|---|
| engine generation moved | `engine_identity()` differs from `installed_identity` | **true** |
| external implementation differs | `snapshot_problem` → `… differs from its carrying commit: Scripts/accounts/SaiAccounts.cs` | **true of the worktree** |
| verifier context/runtime/argv changed | `receipt_plan` → `external verifier context/runtime/argv changed since the receipt` | **true** |

## The fact that changed the decision

The blocker said a fresh proof would be "a receipt that the next edit
invalidates". That was true when it was written and was no longer the whole
picture. Re-measured this turn:

```
C:\ProgramData\SAI\Accounts\bin\sai-accounts.exe
  sha256 39f20e2a0c095f1bfc00998753907e0b6aed517d24631faeac95ce1f5008f6c5
  mtime  2026-10-31T08:25

recorded in .saipen/evidence/T-1840-external-refresh/live-current.json
  sha256 5568338efc4e6ff088d3c6691cd767e42641fbde2c3d35e9433f59625ece0fbd
```

**The external product shipped new code today.** A fresh measurement is
therefore new evidence, not a re-assertion — which is exactly what T-1973's own
verify clause requires ("the SAI Accounts external implementation
T-289@d93b212 is not re-asserted without new evidence from the external
product").

## The route, and the three that were measured and refused

| route | answer | why |
|---|---|---|
| `ticket renew-external T-1653` | refused: `external implementation differs from its carrying commit: Scripts/accounts/SaiAccounts.cs` | `external_renewal.capture()` compares the `__SAITULS` **worktree** to `git show d93b212f`. That sibling carries 53 uncommitted lines (`git diff --numstat` → `53 0`). Another project's authority. |
| `ticket resolve-external T-1653 --revalidate` | `discovered 0, inspected 0, resolved []` | a receipt whose verifier argv moved is not an executable plan, so no candidate is formed. See §"The defect" below. |
| hand-edit the receipt or BOARD row | forbidden | immutable history |
| **`ticket resolve-external T-1653`** (same tuple, no renewal) | **`EXTERNAL_RESOLVED` → EX-000030** | documented re-resolution path |

The chosen route is the one `_plan_resolve_external_ticket` names in its own
comment: *"Same tuple, but the installed generation moved: this is the
RE-RESOLUTION path. A new append-only receipt replaces the pointer; the DONE
row and all history stay intact."* It writes no `external_snapshot`, so the
worktree comparison is not in its path at all.

### Why the uncommitted sibling delta does not weaken the proof

The delta is `EnsureOperatorConsoleDefaults()` — console QuickEdit, window size
and VT level registered under `HKCU\Console`. It is cosmetic and touches
readiness nowhere. Verified rather than assumed:

```
git show d93b212f:Scripts/accounts/SaiAccounts.cs | grep -c 'readiness' → 7
grep -c 'readiness' Scripts/accounts/SaiAccounts.cs                 → 7
```

All seven `saipen-readiness` / `MACHINE_RUNTIME_READY` / `saipen_runtime_ready`
symbols are present in both. The readiness implementation the receipt names is
unchanged.

## What was executed

The sealed readiness contract ran against the new binary:

```
tools/verify_accounts_readiness.py --engine …sai-accounts.exe --account AG3
  --project …_SMART_VAC_CLEANER --private-home C:\Users\vac34\.codex
  → Ran 3 tests   OK
```

Report at `.saipen/evidence/T-1973-renewal/live-renewal.json`:

```
tests_ran 3   failures 0   errors 0   skipped 0
engine_sha256 39f20e2a…   (the new binary)
fixture_removed true
actual_project_canonical_unchanged true
unlisted_home_negative_control true
operator_profile_readable_but_not_a_project true
```

`actual_project_canonical_unchanged: true` is the important line: the verifier
grants and revokes managed-account ACLs only on a disposable temp fixture
(`tempfile.mkdtemp(prefix="saipen-accounts-acceptance-")`, removed in a
`finally`), and asserts the live project's canonical hashes are byte-identical
before and after. The earlier worry that re-running it would mutate a live
account or project was measured and did not hold.

## The defect this ticket then had to fix

Running the recovery surface produced:

```
$ saipen ticket resolve-external T-1653 --revalidate --dry-run --json
{ "ok": true, "discovered": 0, "inspected": 0, "revalidated": 0,
  "resolved": [], "predicted_eligible": [], "still_blocked": [] }
```

At that moment `validate.py` printed `FAIL: closure provenance does not
resolve`. **The recovery surface said there was nothing to repair, and the gate
said there was.** One filter caused it:

```python
if engine_moved and not other_problems:   # ← everything else fell through
```

Section 1 of `revalidate_external_dependencies` iterates DONE Work that cites a
receipt and admitted a candidate only when the *only* problem was an engine
move. A moved external artifact, a changed verifier argv, a corrupted
predecessor — each dropped with no counter, no finding, no mention. A clean
sweep reported over work it had measured as non-green.

This is the campaign's own subject one layer down: a surface answering a
question it never asked.

### The fix

```python
if not engine_moved and other_problems:
    inspected_count += 1
    blocked_findings.append({
        "ticket": work,
        "code": "EXTERNAL_CLOSURE_DRIFTED",
        "detail": "; ".join(other_problems),
        "authority": record.get("external_authority"),
        "implementation": record.get("external_implementation"),
    })
    continue
if engine_moved:
    …
```

The surface may still decline to re-execute. It may no longer report silence.

## The measured pair (one verifier, both halves)

Oracle: `tools/test_t1973_revalidate_accounting.py`, unchanged across both
halves.

```
pre-fix   FAIL   accounted=0 over a non-resolving closure; control green
post-fix  PASS   2 tests, 2 passed
```

The pair was re-proved by reverting only the guard and re-running:

```
revert → FAILED (failures=1)  "0 not greater than 0"
restore → OK                   Ran 2 tests
```

The control test (`test_a_resolving_closure_stays_silent`) guards the opposite
error: a green closure must not become noise. It is green in both halves, which
is the point — the fix adds accounting without inventing findings.

Sibling suites, to prove the fix is contained:

```
test_external_revalidation + test_external_resolution
+ test_t1840_external_renewal + test_t1516_portable_receipts
  75 tests   OK
```

## Result on the live tree

```
external.resolution_problems(root, 'T-1653', ticket)  →  []
validate.py                                            →  Validation complete.
                                                          Agent is conformant.
                                                          (18 warning(s))
```

The gate's single FAIL is gone, and it went with zero problems rather than a
suppressed line.

## Honest limits

- EX-000030 binds the engine generation this tree runs **now**. The next ticket
  that edits `tools/saipen_engine/*.py` moves `engine_identity()` again and this
  closure will go stale again. That is the design (a proof is only green against
  the generation that produced it), and the accounting fix above is what makes
  the next occurrence visible instead of silent. It is not a fix for the
  churn itself; parking that is a separate decision.
- `__SAITULS` still carries its 53 uncommitted lines. Nothing here touched it.
  `renew-external` will keep refusing until that project commits or stashes
  them, and that is correct — the receipt must bind committed bytes.
- Nothing was committed. `publication_state: pending`, as with every closure in
  this campaign.
