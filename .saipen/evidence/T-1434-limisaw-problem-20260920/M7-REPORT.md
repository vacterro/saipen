# T-1434 / SRC-088 — Milestone 7 evidence: real LIMISAW end-to-end recovery

Date: 2026-09-21. Phase BUILD. Continuation of T-1434 (SRC-088).

Mission: LIMISAW reaches authoritative conformance PASS through CANONICAL
SAIPEN operations only, history and product bytes preserved, SRC-011 product
work left untouched.

## Fresh baseline before M7 (measured, not inherited)

`validate --gate core` (protocol-home engine, observe binding via M6):
`Validation FAILED: 22 problem(s), 21 warning(s)` --
21 closure-evidence (T-008, T-009, T-015, T-19..T-36) + 1 closure-provenance
(EX-000001..3 stale against the moved engine generation).

## M7.1 closure evidence -- per-ticket executed verification

Each of the 21 DONE tickets received its OWN executed contract, clustered by
contract type but never one generic command: the named harness exe for
behavioral contracts (`tests\bin\limits.exe`, `carry_forward`, `child_job`,
`settings_ux`, `refresh_coalesce`, `zcode_budget`, `ini_reload`,
`save_partial`, `codex_session`, `antigravity_journal`, `slider_commit`) and an
exact source/doc marker check for code-level contracts (negative `SetVolume(int)`
call-site check for T-008, `sb.Capacity` doubling loop T-029, `W2-007` artifact
digest T-030, `Bounded newest-first candidates` T-028, `DesktopHit` cache T-035,
`void Apply(ProbeResult snapshot)` T-034, `using (var fmt = new StringFormat`
T-036, `LoadErrors` T-010, `LowSound`/`NotifyLow` T-022, exe `0.0.8` stamp
T-009, exe untracked + clean tree T-015, knowledge-doc route T-023).

Receipts RV-000001..RV-000028 (append-only; each binds its Work, tree, ruleset
and contract). Verdicts: 20 x PASS_WITH_CARRIED_DEBT, 1 honest interim FAIL --
T-23 first ran a checker whose literal/case was wrong (`never run git checkout`
lowercase, no /S), recorded FAIL RV-000013/RV-000027, then the corrected
contract (`findstr /S /C:"git checkout -- LIMISAW.exe" build-and-test.md`)
recorded PASS RV-000028. The FAIL receipts remain as history; the newest PASS
is what cures. All 21 closure-evidence FAILs disappeared from the validator.

## M7.2 external resolution generation move (designed rollback proof)

The original contracts were re-executed against the NEW engine generation:
`test_t1411_stale_complete_resolution.py` (T-73),
`test_t1412_conformance_truth.py ValidateSurfaceTests` (T-66),
`test_t1412_conformance_truth.py StatusSurfaceTests` (T-67) -- all still PASS.
Canonical re-resolution wrote NEW immutable receipts EX-000004/5/6
(old EX-000001..3 preserved; DONE rows untouched; identical
authority/implementation/reason tuples). `ALREADY_APPLIED` on a repeat proves
idempotency. Validator: closure-provenance PASS.

## M7.3 strict cycle

`imp-vacterro-limisaw-20260918-4` is terminal (`cycle_status: superseded`,
two seats `unavailable` with `retire_reason: EMPTY_DRAFT`, three seats
`superseded` onto opencode-06 with preserved hashes);
`improve verify <cycle>` -> `IMPROVE_VERIFY_PASS`; sweep-ticket-link PASS.
All transitions were canonical operations; no manual manifest/report edits.
One protocol defect surfaced and was repaired inside SRC-088: `improve verify`
compared a SEALED cycle's report fingerprint against the moved install; the
bound proof now applies installed truth to ACTIVE evidence only, with test
`test_12_sealed_cycle_is_not_compared_to_a_moved_install` (M4 suite 12/12).

## M7.4 source state

SRC-007 tombstone: retired 2026-09-20T20:49:03Z, reason recorded,
`archive/retired/SRC-007.md` preserved (sha256 4e3acc1203e9d729...), no
current source failures (`source receipts` class gone).

## M7.5 product requirements

SRC-011 remains ACTIVE (linked_work T-52); R001..R004 VERIFIED;
R005..R015 UNKNOWN/unresolved. Next legitimate LIMISAW product target stays
SRC-011:R005.

## M7.6 final acceptance (canonical front door)

- structural gate PASS; authoritative receipt CURRENT_PASS
  (`receipt-6b026968bd87_core_PASS.json`, sha256 d8d1db080cdda19a...);
- `saipen validate --gate core` -> `VALID` (front door re-read
  `conformance_status` = CURRENT_PASS);
- human status line and machine `conformance_status` agree (PASS);
- `saipen next` -> `ok`, action `saipen continue`, reason `maintain`; no
  CONFORMANCE_UNHEALTHY block;
- current conformance errors: 0 (21 warnings, 0 problems);
- history preserved: RV-000001..28, EX-000001..6, all prior receipts intact;
  LIMISAW product source unchanged (`git status --porcelain` empty,
  HEAD dce172c1e7a3f03e865122c2e74df9bb7da71cd4 unchanged).

## Product-side note (PRE_EXISTING, NOT T-1434)

`pwsh build.ps1 -Tests` (LIMISAW's own suite, run as cross-cutting evidence for
M7.1) reports 4 failing harness checks pre-existing to T-1434 and unrelated to
its operations, with LIMISAW HEAD unchanged:
- `standalone` README-header check: invalidated by T-69's authorized README
  polish -> FIXTURE/ORACLE drift (LIMISAW-side);
- `core_refresh_ownership` source guard ("no raw WinForms Refresh from the
  worker"): drifted against later product edits -> FIXTURE/ORACLE drift;
- `settings_consistency` low-threshold re-arm check -> suspected
  environment/state, LIMISAW-side;
- `gdi_paint`: failed once inside the suite, PASSES standalone (11 checks,
  0 failures) -> ENVIRONMENTAL.
These affect LIMISAW's product test suite, not the SAIPEN conformance gates;
they are classified for a bounded LIMISAW-side owner (T-72 ship / next
audit wave) and were NOT repaired here (no unrelated product implementation).

## Exact next action

M8 (SRC-088): cross-shape regression + determinism -- synthetic shapes for all
recovered primitives, the M5 remediation gate, an extra real read-only project
if safely available, and a double broad-family run on ONE unchanged tree with
HEAD/tree/ruleset captured before run 1.
