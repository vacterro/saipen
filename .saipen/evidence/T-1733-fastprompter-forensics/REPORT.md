# Forensic Report: FastPrompter closure provenance (SRC-231 / T-1733)

Read-only forensics on `V:/___VAC/__K/__CODE/_PY/_FastPrompter`. No FastPrompter
source, LOG, STATE or BOARD byte was written by this mission.

## Disposition: VALID (stale/mixed snapshot) with one bounded follow-up

The audited project state was a stale snapshot. The canonical ledger is
internally consistent; the one durable finding is the absence of a
source-drift warning for historically-DONE Work, referred to a narrow
follow-up ticket.

## 1. Canonical head determination

- Live head: `src/fastprompter/main.py` sha256[:16] = `7edec16857fdb645`
  (1126128 bytes), **worktree-modified** (`git status` ` M`), git HEAD `4d6a59d`.
- Live STATE: `phase: REVIEW`, `task: T-1459`, `last_event: 4520`,
  `updated 2026-10-13T02:28:05Z`, `saipen_version: 8`.
- Live LOG ends at `E-4521` (T-1459 transition to BUILD), 469 lines.

The audit's quoted "current recorded STATE" (`phase: DONE`, `task: none`,
`last_event: 4395`) and "current main.py sha256 113307a15ec960bf" **do not
match the live tree**. They match an earlier snapshot. The project moved on
(T-1451..T-1460, T-1459 REVIEW) after the audit bytes were captured.

## 2. Provenance matrix

| Item | Source/authority | Parent | Ticket | Recorded phase | Source binding | Current validity | Quarantine/canonical | Establishes completion |
|---|---|---|---|---|---|---|---|---|
| `E-4395` | LOG/SAIOPS | E-4394 | T-1450 | VERIFY (checkpoint RUN) | none (no fingerprint) | canonical, still present | canonical | No — verify checkpoint only |
| `E-4404` | LOG/SAIOPS | E-4403 | **T-1402** | transition to REVIEW | none | canonical | canonical | No — different ticket, REVIEW not finish |
| `board-terminal.json` | recovery projection | — | lists T-1450 | terminal | `board_sha256_16` (BOARD, not source) | written 2026-10-13 05:32 | recovery record | BOARD-only; no LOG finish, no source binding |
| postfix snapshot `23d1bbfe75c54f5a` | `.saipen/evidence/t1450/main_postfix_snapshot.py` | — | T-1450 | recorded post-fix | self-hash | file present | evidence | Work-level only |
| audit "current" `113307a15ec960bf` | audit text only | — | — | — | unresolved | **no byte source found** | — | No |

## 3. E-4395 versus E-4404

`E-4395` (09.10.26 14:22, parent E-4394) is T-1450's VERIFY checkpoint
("6237 passed, 26 skipped, 2 failed, both pre-existing"). `E-4404`
(10.10.26 02:04, parent E-4403) is **T-1402's** transition to REVIEW — not a
T-1450 event and not any finish. The audit's recollection that "E-4404 was the
successful T-1450 completion event after a reconciliation" is **rejected**: the
event belongs to a different ticket and a non-terminal phase.

## 4. BOARD/LOG/STATE consistency verdict

T-1450 appears in the canonical LOG **once** (E-4395). No `SHIP` or
`finish` line for T-1450 exists, and the event chain is contiguous
(E-4394→E-4395→E-4396), so nothing was renumbered or deleted. BOARD shows
`- [x] T-1450`. The `[x]` is explained by the **BOARD-only terminal recovery
projection** recorded in `.saipen/recovery/board-terminal.json`
(`{"schema":1,"board_sha256_16":...,"done":[... "T-1450" ...]}`, written
2026-10-13 05:32). That is the documented behaviour of `saipen ticket` board
terminal projection: a canonical DONE whose LOG finish line was never written is
carried as a board terminal, not as a fabricated LOG event. Verdict:
**consistent** — BOARD DONE over a LOG that ends at a checkpoint is the expected
signature of a board-only terminal, not corruption.

## 5. Source-fingerprint and verification binding

The T-1450 evidence records red-control anchors: pre-fix subject
`be4f065613de20c4`, post-fix snapshot `23d1bbfe75c54f5a`, reconstructor
`52ca3485f5601b10`. Those are Work-level self-hashes. **No** record ties the
closure to the production tree's committed bytes, and none of the recorded
hashes equals the current live `7edec168...`. Verification binding is
**Work-local, not source-bound**.

## 6. Confirmed defect or rejected hypothesis

- Audit hypothesis "the current production implementation contains previously
  repaired defects": **rejected for the live tree.** The T-1450 repair markers
  are present and *more* numerous live (`_pre_quit_logical_finalize` ×5,
  `_logical_finalized` ×10) than in the recorded postfix snapshot (×3/×9) and
  equal-or-greater than every committed blob checked.
- Audit hash `113307a15ec960bf` matches no live file, no simple line-ending
  transform of the live file, and no blob in `git log` for the path (20 most
  recent commits enumerated; none equals it): the audited byte source is
  **unidentified**, i.e. a stale or repackaged snapshot.
- This is the DECISION GATE's first branch: **stale/mixed project snapshot →
  report packaging/source provenance, do not change SAIPEN internals.**

## 7. Safe recovery proposal

None required for the FastPrompter ledger — it is consistent and live. No
mutation, no renumbering, no history compaction.

## 8. Bounded follow-up (source-drift warning)

Durable observation, narrow scope: a historically-DONE Work whose verified
source bytes are not bound to the closure gives no warning when the source later
drifts (`T-1450` DONE while live `main.py` differs from every recorded hash).
SAIPEN already ships the manual remedy (`saipen work reverify` replays a DONE
Work against the CURRENT tree). Missing is the *automatic* drift signal on
closure-bearing rows whose binding is absent or stale. Filed as narrow
follow-up Work **T-1734** with focused-test acceptance criteria; not implemented
here, to respect the non-goal "do not expand into a protocol architecture
redesign".

## 9. Evidence references

- FastPrompter `.saipen/STATE.md`, `BOARD.md` (T-1450 `[x]`), `LOG.md`
  (E-4390..E-4405 at lines 338–353; E-4395 line 343; E-4404 line 352).
- `.saipen/evidence/t1450/README.md`, `main_prefix_subject.py`,
  `main_postfix_snapshot.py`, `reconstruct_prefix_subject.py`.
- `.saipen/recovery/board-terminal.json` (mtime 2026-10-13 05:32).
- Git: `4d6a59d` head; `git log -- src/fastprompter/main.py`; per-commit blob
  hashes enumerated; `src/fastprompter/main.py` worktree-modified.

## 10. Exact owner of the subsequent corrective task

The source-drift warning (item 8) is a SAIPEN-side concern and belongs to this
repository's protocol maintainer (CMD-ROUTING-01 / OPS); the FastPrompter
ledger itself needs no owner because no mutation is due.

## 11. Final disposition

VALID — the audited discrepancies are a stale/mixed snapshot plus a
mis-remembered event id, not a ledger inconsistency. One bounded follow-up
recorded (source-drift warning). No FastPrompter mutation; no SAIPEN-internal
change made.
