# AG3 runtime availability and bounded historical attribution

Status: local repair T-1712 is owned by `saipen-cli`; verification is in progress.
The originally blocked consumer now reads DONE / task none with CURRENT_PASS
receipt `receipt-988a6f99ca0b`. The installed manifest module remains pre-fix;
the successful intervening route/principal is not established. The original
BLOCKED snapshot is historical, not a current global stop. No deployment or
publication is authorized.

## Confirmed failure boundary

The pre-fix current CLI reproduces this chain with injected Windows error 5:

`main -> _continue -> reconcile_protocol_state -> _ensure_audit_contract ->
audit_manifest.ensure:700 -> audit_manifest.write:795 ->
paths.safe_atomic_write_bytes:401 -> prove_owned_dir_chain:244 -> Path.lstat`.

The writer proves every ancestor because this caller does not supply an
`ownership_root`. That proof is retained. The helper converted an `OSError`
into a plain `ValueError`; the lifecycle caller caught only `OSError`. The
exception therefore escaped normal CLI JSON handling. A required no-follow
metadata probe, rather than project content enumeration, encountered the boundary.
`preflight.json` preserves the current reproduction and unchanged canonical bytes.
The operator's 07:26 and 08:14 source snapshots are reported identical; their
original carriers were not independently supplied here.

## Identity and permission evidence

The reported AG3 identity is `SAIAG_9fabb0d5`, confirmed as an enabled local
account, SID `S-1-5-21-6247072-3065140091-1424061869-1019`, direct group `Users`.
The exact account-manager grant binds it to
`V:\___VAC\__K\__CODE\_TAMPERMONKEY\_SUNO_DOWNLOADER`.
That root and its `.saipen` have an existing Modify grant for this SID.
The inspected ancestors lack an allow entry for this account or `Users`.
The operator reports WinError 5 at `V:\___VAC\__K`.

These diagnostics ran as `vac34`, SID ending `-1002`, medium integrity. They do
not prove the affected AG3 token, restricted SID set, impersonation state or
traverse privilege. No AG3 credentials or impersonation were used. All four
affected canonical file hashes are unchanged in `read-only-diagnostics.json`;
that read-only diagnostic performed zero ACL mutations or affected-project writes.
The installed manifest module is byte-identical to the pre-fix source
(`33973fa8219482db208cd1cc33367609c9bd0e51152131657aad838d51a1771b`).
Installed `paths.py` and `reconcile.py` differ from the current checkout. Neither
their version string nor this source fix proves that AG3 runs repaired bytes.

| Candidate cause | Admissible conclusion |
| --- | --- |
| Missing project or ancestor | Not established by `Test-Path False`; operator diagnostics confirm these nodes exist |
| Inaccessible ancestor | Reported WinError 5 at `__K`, consistent with recorded ACLs and reproduced metadata boundary; actual AG3 token probe unavailable |
| Inaccessible child | Distinct hard refusal covered by fault injection, not asserted as the observed host cause |
| Invalid canonical binding | Exact account grant and project lineage are present; access denial must not be relabeled as missing memory or lineage conflict |
| Missing dependency | Manifest module exists in source and installed runtime; no evidence this incident is a missing-module failure |
| Canonical corruption | No current evidence: affected STATE is PLAN / task none; missing manifest after denied enrollment does not prove corrupt authority |
| Intentional isolation versus host grant defect | Insufficient policy/token evidence to choose; existing denial remains intact |

## Attribution matrix

Git author names, canonical Work owners and model identities are different facts.
No row below attributes a defect to the previous Gemini protocolist. The independent
Gemini forensic assignment and current AG3 executor are outside that allegation.

| Defect / classification | Introducing commit or earliest occurrence | Verified historical owner | First available failure | Should prior verification catch it? | Repair owner | Preventive regression | Current status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Manifest ancestor denial escapes lifecycle; pre-existing implementation defect | `dbbfad94688515d604b54e2c97dc92aa5fa7eab1`, 2026-08-27 23:33:14 +03, introduced the helper's OS-error to ValueError conversion; manifest call path first tracked in `8f91d779cc4d65f6e1db952eee58db7fb3b14a78`, 2026-09-15 13:36:08 +03 | T-1171 committed BOARD: `codex`; T-1328: `codex` owns registration/verification, explicitly not original implementation; Git author VAC34 | Current operator AG3 report; exact committed manifest/helper subjects reproduce in `history.json` | Error containment contract warranted a permission fault control; recorded 350/33 green tests do not establish that coverage | SAIPEN / T-1712 / `saipen-cli` | Same oracle red before and green after; ancestor WinError/path retained; hard parseable JSON; zero canonical writes | Owned local patch applied; focused controls pass; complete gate pending |
| Denied manifest inspection treated as absent/malformed, with force able to replace it; pre-existing implementation defect | Earliest tracked manifest `8f91d779`; current failure still present before this patch | Original implementation author unknown; T-1328 registration owner `codex` only | `red-final.json`: denied stat/read and STATE inspection controls | The original 33-case manifest suite contains no PermissionError/OSError/denied control; it tested malformed bytes and missing paths instead | SAIPEN / T-1712 | Existing unreadable child and manifest stay hard unavailable, including `force`; original bytes unchanged | Corrected in local lifecycle boundaries |
| Required enrollment failure could be a soft success after reconciliation; pre-existing implementation defect | `_ensure_audit_contract` first tracked in `b2343541e3ebe939bc583408a173c54aeb57939b`, 2026-09-15 15:25:20 +03 | Git author VAC34; carrying commit covers T-1334/1335/1336 with canonical `codex` owners; exact hook implementation attribution not proved | Current denied-write control, plus neighboring tests that expected successful continuation after denial | Neighboring expectations explicitly allowed the old behavior; current operator contract requires hard refusal and no partial canonical repair | SAIPEN / T-1712 | Required manifest write fails before repair commit; active phase/claim unchanged; access-denied neighbors require refusal | Preflight and required write moved before canonical repair; five neighboring expectations updated with stronger denial assertions |
| INIT late write leaves partial memory; separately confirmed pre-existing defect, not the observed AG3 cause | Earliest tracked `init_project.py`: `c138bfd8aa89ec82728587dd7c9ae43e9a69b7c3`, 2026-09-28 23:34:31 +03; a registration commit, not proven original authorship | Git author VAC34; original executor not established | Current injected STATE write denial leaves IDENTITY.md in pre-fix subject | A materialization rollback control should catch it; no claim that older verification exercised this fault | SAIPEN / T-1712 | Late INIT denial leaves no canonical files and emits no INIT_COMPLETED | Complete directory staged before publication; focused control passes |
| Permission denial formerly reported as invalid binding; diagnostic gap with a preserved security refusal | Current pre-fix `_valid_saipen_dir`/binding path and existing T-1647 tests; exact introducing attribution unresolved | No verified model attribution | Existing restricted-principal controls and current pre-admission fault injection | Older tests required PROJECT_BINDING_INVALID; the new source now requires OS denial to remain distinguishable | SAIPEN / T-1712 | Binding denial yields before_admission runtime-unavailable; true missing binding and lineage mismatch retain separate behavior | Structured resolver failure added; binding neighbors pass |
| AG3 root grant with denied ancestor metadata; intentional denial or external host configuration defect not yet distinguished | Read-only ACL/grant snapshot; no proven grant-changing commit or actor | Account/policy owner unknown; current operator owns any privileged repair authorization | Operator WinError 5 and matching account/root diagnostics | A live same-token ancestor/root probe would reveal it; ordinary source tests cannot prove another token's grant | Host account-manager / isolation-policy operator | Read-only same-token no-follow probes; preserve unrelated directories and denied grants | Historical BLOCKED; newer consumer DONE / CURRENT_PASS. Intervening route/principal unknown; no repair or deployment by this Work |
| Previous Gemini executor introduced these regressions; insufficient evidence | E-14232 records the 2026-10-10 provider-limit succession; no verified start commit/model-bound change set or last verified predecessor supplied | Previous executor is identified by operator clarification only; `saipen-cli` and VAC34 do not identify a model | No model-bound introducing delta found in the bounded inspected surfaces | A green predecessor would require exact subject, verifier and executor provenance; a date or provider name is insufficient | SAIPEN historical evidence / T-1713 | Bind future execution receipts to exact subjects and unchanged fault controls, without inventing past attribution | Attribution remains unproved; no historical logs rewritten or DONE tickets reopened |

The manifest's fault-bearing ensure/write lines still blame to `8f91d779`.
The last tracked whole-file change, `c7e25f92`, concerns evidence declarations;
executing that exact committed module with the historical helper reproduces the
same exception as the earliest manifest. This proves persistence of the defect,
not that a particular recent executor introduced it. The historical replay uses
exact committed modules with the current standard library and an explicit current
protocol directory; it is not a claim to have booted a complete old installation.

`history-supplement.json` additionally proves that the pre-fix manifest and INIT
module are byte-identical to tracked HEAD `025bf596`. HEAD is a tracked predecessor,
not an asserted last verified predecessor. The registration commit maps INIT to
T-1553/T-1556; their sealed canonical claims name `saipen-cli` (E-10632/E-10656),
which does not identify a model. The earlier manifest test source is preserved:
33 tests, without PermissionError/OSError/ACL fault literals. All sealed log
hashes remained unchanged during this historical readback.

The bounded history covers manifest, path helper, reconciliation, runtime,
bootstrap, binding/state and admission owners. Current LOG and sealed actor
labels do not supply a model-bound previous-Gemini window. Comparison of that
executor against a last verified predecessor therefore remains unavailable.

## Access repair contract and resumption

No host ACL change is part of this implementation. For the reported exact node
`V:\___VAC\__K`, a no-follow metadata probe needs `FILE_READ_ATTRIBUTES` (`RA`,
0x80) for the actual executing SID. If the isolation-policy owner authorizes it
and a same-token probe confirms the denial, the narrow candidate is one explicit
non-inheriting allow entry for SID ending `-1019` with `RA` on that exact object.
It does not include List Directory, Read content, Modify, Full Control, inheritance,
ownership change or recursion. Other ancestors require separate same-token proof;
do not grant rights to all ancestors merely because their ACLs look similar.
`X` traversal is a separate question and needs an actual token/privilege check.
The target-root Modify grant already exists and is not broadened.

If policy deliberately prohibits that metadata access, preserve the denial and
use an operator-approved existing project binding or an authorized broker that
can perform the required checks while retaining the canonical project identity.
No duplicate project/recovery root is created. No original AUDAPACK authority is
changed. The affected operation is not retried with identical prerequisites.

For a future operation that actually requires the denied resource, resume through
the existing binding and canonical validation only after its prerequisite changes.
Do not broaden ACLs merely because an ancestor looks restrictive when the current
operation does not need it. No current ACL request is inferred from that snapshot.

The earlier PLAN / task none / agent saipen readback in `incident.json` is preserved.
At 07:08Z the consumer reads DONE / task none. Existing canonical events record
manifest materialization at 06:01, T-1 completion at 06:12, then HUNT/CLEAN/DONE
through E-18 at 06:36. Read-only classification of its latest actual receipt gives
CURRENT_PASS (`receipt-988a6f99ca0b`, 06:36:59Z). Four canonical hashes remained
unchanged during each observation. This is stronger than the producer's PASS
sentence; no validator was re-executed and no foreign Work was mutated.

The named runtime's manifest hash is still the pre-fix `33973fa8...`, while the
local repaired module is `00306d1c...`. No current AG3 token or authenticated
intervening access/broker route is available, so the consumer's progress does not
prove universal ancestor access or deployment of this fix. Preserve newer DONE /
CURRENT_PASS authority and the historical incident separately. No active foreign
claim needs release. The main goal remains active with independent eligible Work.

## Regression evidence and limitations

`red-final.json` and `green-final.json` execute the same 21-case verifier,
SHA-256 `c929597071d40fc30eec9b01344b9adf3ac1b9b969c57e1ac5fa49d5702a1958`.
The pre-fix subject is red (7 failures, 11 errors); the fixed subject passes all
21 cases. `owned-application.json` records exact before/after hashes of the six
runtime/CLI files and two test files. The root rerun also passes 21 cases; pinned
Ruff 0.16.0 over tools/tests and whitespace pass. Neighbor results are preserved
separately: 40 manifest, 86 binding, 23 bootstrap, 78 isolated-runtime and 70 INIT
tests pass (297 neighbors). The supplemental current VERIFY-phase control passes
and preserves the exact phase, claim and canonical bytes on refusal. Fresh
VERIFY-cycle red/green executions are anchored at E-14365/E-14366. The first
native gate actually failed and is retained in `native-core.json`; supported
executed re-verification RV-000020 and the owned empty Git intent registration
corrected its two local metadata findings. All foreign index entries remained
identical. `native-core-final.json` passes with zero problems and nine warnings.
Full verification and local closure remain pending until the current complete
family and independent review finish. No test bytes were staged or committed by
the intent registration, and no runtime publication is implied by local Git tracking.

Fault-injection tests do not impersonate AG3 or alter host ACLs. Existing Windows
isolation neighbors use their own disposable temporary fixtures and restricted
tokens; their setup/cleanup is not a repair to AG3 grants, ancestors or the
installed host runtime. No production ACL or account-isolation policy was changed.

Primary access semantics: [Microsoft file access rights](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights),
[icacls advanced permissions](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls),
and [CPython 3.11.9 Windows stat implementation](https://raw.githubusercontent.com/python/cpython/v3.11.9/Modules/posixmodule.c).
The minimum RA candidate is an inference from those APIs and the observed failing
operation, conditional on the policy and actual-token evidence above.

## Continuation evidence

The continuation rechecked all four verifier files and all six implementation
files against `verify-green.json`; every hash matches. `ACCEPTANCE.md` maps all
33 derived SRC-213 clauses to the inspected evidence. Canonical Source operations
now record 33 VERIFIED dispositions with no unresolved clause; this does not
close T-1712 or bypass the full-family and REVIEW gates.

The first declared-family execution completed at 2026-10-11T06:57:20Z:
6156 ran, seven new red, kernel verdict FAIL, 1472.1 seconds, no leaked sandboxes.
Record `core-unit/77a71a06679d26c4-20261011T065720Z.json` is anchored at E-14368;
its source fingerprint is `77a71a06679d26c4d714b1ffe617e542916bbba84de995acfb03230e74599600`.
The seven errors are the two native OpenCode host checks and five bound-launch
checks. Their errors identify the 479-byte incomplete default `opencode.exe`
shim as incompatible with Windows; no actual native startup occurred there.
The genuine existing 180656008-byte x64 payload executes version 1.18.35.

`opencode-instrument-control.json` runs the unchanged host-smoke module with
that existing payload selected only in the verification child's PATH: 10/10,
exit 0, 91.101 seconds. Hashes of the four checked source/installed/native/shim
files are unchanged. This is instrument recovery, not a machine installation
repair, product-regression pair or substitute for a whole family.
The first run and its seven failures remain preserved without a baseline waiver.
A second complete family began at 2026-10-11T06:57:52Z with the same source and
the corrected child-only PATH selection. It completed at 07:19:00Z: 6156/0 red,
1268 seconds, no leaked sandboxes, E-14371, immutable record
`core-unit/77a71a06679d26c4-20261011T071900Z.json`, SHA-256
31eb7aa7b2f4c25e9b8ca8c3fcc96b53d96e71f88be8e3457cbca09d0a7b8961.
Independent first REVIEW re-executed the unchanged 21-case red/current pair.

At 07:22Z an external Future document landed after that PASS. The next native
gate correctly refused two metadata findings; `review-native-core.json` is
preserved, and the prior family is no longer current-tree closure evidence.
Canonical refresh/refine registered FG-0047 DEFERRED from its own proposal-only
instruction, without implementing it. Executed RV-000021 refreshed T-1695's
historical verification while retaining DONE. Current native core is green:
`native-core-future-generation.json`, zero problems/eight warnings. Work returned
through BUILD to a fresh VERIFY boundary E-14377. The same frozen regression
pair actually re-executed, anchored E-14378/E-14379; its exact records are
`verify-future-generation-red.json` and `verify-future-generation-current.json`.
The third complete family completed at 07:59:20Z: 6156/0 red, 1313.2 seconds,
no leaked sandboxes. E-14380 cites
`core-unit/a73ab9009b6fef33-20261011T075920Z.json`, SHA-256
a2dbf6547f28b75c5477b295211328412b3c4d68e26e0c04e1a9bfb0a4c58fa5;
full source fingerprint a73ab9009b6fef336b5e5197d1cffce4a4e7c82dae241afca5fbe0cb78881759.
Fresh pinned Ruff and whitespace pass. The final REVIEW re-executes the same
red/current pair in `review-future-generation-red.json` and
`review-future-generation-current.json`, with the same identities and outcomes.
No unfinished gate is spent as a PASS; local canonical closure remains pending.

The separate preliminary T-1711 preparation is `T-1711-admission/DESIGN.md` and
`prototype-bindings.json`: eight unchanged controls, five failures on current
code, eight passes in a disposable two-file prototype, then the same five
failures after exact restoration. No prototype was applied to production.
T-1713's requested compact historical matrix is prepared in `ATTRIBUTION.md`,
without a claim, historical rewrite or executor attribution. Both Work rows
remain queued while T-1712 owns VERIFY.

`continuation-readback.json` and `consumer-conformance-observation.json` supersede
the old current-state statement for the affected project. The latter reuses the
canonical read-only receipt classifier and proves CURRENT_PASS against the live
checkpoint; it does not infer a new ACL grant or identify the executing model.
