# SRC-203 current-engine adjudication

The 19 September LIMISAW handoff describes three shared engine defects. The
current source implements all three repairs; this Work independently verifies
that behavior and records the supported recovery. It changes no engine code.

## R001: canonical validation and receipt truth

`tools/saipen.py:_validate` first checks canonical document structure, invokes
the validator belonging to the running installation, and reads the resulting
receipt through `conformance_decision`. Only a current PASS yields `VALID`.
The eight StatusSurfaceTests/ValidateSurfaceTests controls in
`tools/test_t1412_conformance_truth.py` cover stale/current FAIL, receipt-write
failure, moved-source PASS, structural refusal, JSON/human agreement, and the
absence of a second verdict route. The inherited executed result is recorded
in `conformance-tests.txt`, bound to unchanged source hashes in `subject.json`.

The live source gate also rejected stale T-1695 closure with CURRENT_FAIL and
named `saipen work reverify T-1695`. The engine executed the unchanged original
red/green oracle and four public CLI controls, producing RV-000008 with
`PASS_WITH_CARRIED_DEBT`. No historical closure or evidence was rewritten.

## R002: status labels authoritative truth

The human printer reads `conformance_status.status`; `conformance_history`
appears only as `Validator history hint` with an explicit historical label.
The same eight-control suite covers the complete status matrix and disagreement
with legacy LOG PASS. A historical receipt is evidence of its original tree,
not current acceptance or proof that an installed consumer has converged.

## R003: draft provenance recovery

The canonical command is
`saipen improve rebind <cycle> <seat> <project>`. It requires an ACTIVE cycle,
a DRAFT report, and no bound error other than install-derived identity drift.
It validates the proposed report through the same bound bar used for append,
writes through the journal, and leaves the RUN body unchanged. Complete,
swept, and archived evidence is preserved. `improve retire` and
`improve reconcile` provide separately defined finite lifecycle exits.

The sacrificial fixture in `triage.py` first demonstrates stale draft append
refusal with unchanged bytes, then invokes the public launcher and receives
`REBIND_COMMITTED`. The complete restored report equals the original bytes;
append and completion then succeed. `rebind-cli.json` and
`rebind-control.json` retain the real outputs.

Fresh `verify-*` and `review-*` runs repeat the eight conformance controls
and public rebind recovery, additionally proving that a completed report is
refused without changing its bytes. The original unprefixed artifacts remain
intact. `verify-live-validation.json` records the real CURRENT_PASS receipt.

## Installed transport is a separate generation

The initial diagnostic used the installed skill launcher under
`C:/Users/vac34/.agents/skills/saipen/`. It reported AUDIT_BINDING_CORRUPT,
whereas the source launcher under this repository reports all five named
pending files and no binding error. The installed directory is a real copy,
not a junction: its `audit_inbox.py` has SHA256
`aada9fb01baa4a6ee6b36af67d3c6cc4becd6e2712c3ca201b04a41408532d3f`,
while the source has
`7421355627f2b55b109e0df4644a5b49580f2f21173e6bf33d3544dc37968e06`.
The corresponding `saipen.py` hashes also differ. No binding repair was made;
the observations must not be conflated into a current-source corruption claim.
Installed consumers remain a distribution question governed by the existing
publication policy. This Work verifies the source transport and performs no
rollout.

## Downstream boundary

A read on 10 October observes LIMISAW at HEAD
`64f15a1d50b5f9d98d151c8d82c4435c62bc5ebf`, SCOUT T-113. The cited cycle
`imp-vacterro-limisaw-20260918-4` now has `cycle_status: superseded`, retired
empty draft seats, and preserved hashes with replacement opencode-06 for its
stale completed seats. The handoff's assertion that it remains ACTIVE is
historical. This Work has not repaired that project or changed its files;
its stale STYLE binding also prevents claiming current downstream conformance.

## Scope and verification

The deliverable is this adjudication and its bounded verification evidence
under `.saipen/evidence/T-1700-limisaw-handoff/`. Engine and foreign project
bytes, publication policy, and the inherited Git index remain outside the
delta. Source clauses become terminal only with current executed verification;
Work closure and journaled inbox consumption remain separate mechanical gates.

The first review boundary helper deliberately compared the raw Git index and
failed when its hash changed. That diagnostic is retained in
`review-boundary-differences.json`; source hashes and all four foreign Core
files plus eight foreign cycle files remained equal. The inherited staged
binary diff is independently equal to the historical snapshot after CRLF
transport normalization, SHA256
`8103c569fa19a7a2daf96e968de7d2375f51a875261a6e08ad385720d05cd1a2`.
`index-adjudication.json` records the current exact index-entry digest as well.
No index restore or staging was performed; raw metadata equality is not claimed.
