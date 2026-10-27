# T-1817 / SRC-276 R008 — final diagnosis, owner-separated, evidence-backed

Date: 2026-10-22. This is the delivery artifact R008 asks for: every source
finding F-01..F-12 retained with its defense, confidence and remaining unknown,
split by the owner that can actually close it, and reconciled against the
current measured state instead of the historical snapshot.

Read-only compilation. The observed target
`V:/___VAC/__K/__CODE/_PY/_SMART_VAC_MEDIA_COMPRESSOR` was not written to.

## 1. What the record actually establishes

The observed session did not fake authority, did not hand-edit the sealed LOG,
did not fabricate sidecars, did not publish, and did not declare the goal
complete. Its goal verifier correctly returned `passed:false` /
`blocked_external` with four blocked tickets. What it did do is stop on a real
`CURRENT_FAIL` and then route badly: it minted a second tracking record over a
subject that already had an owner, overstated the completeness of its checks,
presented absence-from-Git as historical non-existence, and moved
engine-owned work into a "needs you" list.

That distinction is the whole point of the source. The validator was right to
complain; the recovery and orchestration contracts around it were unfinished.

## 2. Current measured state differs from the historical snapshot

| historical claim | current measurement |
|---|---|
| SRC-003 closed archive is incomplete; validator reports `source_receipt_closed_archive_invalid`; `intake.status` → `SOURCE_CORRUPTION` | **not current.** All five sidecars present; `_closed_archive_bundle` proves meta `CLOSED`/`ARCHIVED`, digest equals tombstone `7b142fba…`, 4 of 4 clauses `VERIFIED`, 0 unresolved; `intake.status` answers `CLOSED`, `DISTRIBUTABLE`. Evidence: `.saipen/evidence/T-1817-current-audit/external-r001-current.json`, every pinned carrier hashed before and after, `observed_files_unchanged: true`. |
| T-62 is a duplicate that stole T-57's subject and was never reconciled | **reconciled by the target's own LOG.** E-693 recorded the E-371 accepted debt; E-694 recorded `BUILD -> VERIFY: "SRC-003 routed to T-57"`; T-62 finished E-699 and T-57 finished E-709 with a verify PASS over the closed archive. Both closed through a real SHIP chain, so no fictional DONE exists on either. Evidence: `.saipen/evidence/T-1817-finding-route/R002-LINEAGE.md`. |
| no fresh `CURRENT_PASS` exists | the newest core receipt in the target is a PASS at HEAD `9ebe344e`, which is still that tree's HEAD. It now reads `STALE_PASS` (`source-binding-stale`) because the external tree moved after the receipt. A fresh foreign validator receipt is outside this project's write authority and is **not claimed**. |

The last row is the honest boundary: the archive defect is provably gone, but a
fresh foreign receipt is not something this handoff can produce.

## 3. Finding register (all twelve retained)

`owner` is the class from `saipen_engine/finding_ownership.py`. `defense` is the
protection the source itself recorded and that this diagnosis preserves.

| F | sev | owner | confidence | defense preserved | remaining unknown |
|---|---|---|---|---|---|
| F-01 routing/scope drift | P1 | ENGINE_INTERNAL | HIGH for route deviation; MEDIUM for a normative ban | engine accepted the start as `model_supplied`, `user_explicit:false`, `goal_pivot:false`; no forged user authority | whether a narrower local-diagnostic policy would have permitted it |
| F-02 duplicate ownership | P1 | ENGINE_INTERNAL | HIGH overlap; MEDIUM-HIGH dedup defect | T-62 carried a distinct E-371 half, so it was not purely redundant | none — adjudicated by E-693/E-694/E-699/E-709 |
| F-03 closed-archive recovery | P1 | ENGINE_INTERNAL | HIGH defect then; LOW for "never existed" | fail-closed refusal was correct; copying bytes would have been wrong | historical cause of the missing sidecars |
| F-04 E-371 provenance | P1 | OPERATOR_DECISION | HIGH for the missing marker; UNKNOWN origin | refusing to forge the token was correct; sealed LOG not edited | historical writer of E-371 |
| F-05 accepted-debt authority gap | P1 | ENGINE_INTERNAL | MEDIUM-HIGH design risk; no exploit proven | this session never exercised the path | whether an unshown host admission layer existed |
| F-06 unsupported exhaustive claim | P2 | UNAVAILABLE_EXTERNAL | HIGH | the practical conclusion "no verified path created valid sidecars" was true | none |
| F-07 temporary false heal claim | P2 | ENGINE_INTERNAL | HIGH that the claim occurred; HIGH that it was corrected | corrected in-session; final answer did not claim the heal | none |
| F-08 language/structure/HUSH drift | P1 | UNAVAILABLE_EXTERNAL | HIGH output drift; HIGH `enforcement: none` | host admission was explicitly not mechanically enforcing | any overriding instruction outside the capture |
| F-09 partial observation | P2 | UNAVAILABLE_EXTERNAL | HIGH pattern; LOW missed task | an independent verifier still saw `actionable: 0, blocked: 4` | none |
| F-10 negative-evidence overclaim | P2 | UNAVAILABLE_EXTERNAL | HIGH overreach; UNKNOWN origin | current absence in the checked repo was true | actual historical origin |
| F-11 human-handoff misclassification | P1 | ENGINE_INTERNAL | MEDIUM-HIGH | no AskUserQuestion, no simulated consent; engine did stop | whether `blocked_external` was host taxonomy or canonical class |
| F-12 UI TODO vs goal | P3 | UNAVAILABLE_EXTERNAL | MEDIUM UX; HIGH no false goal PASS | goal stayed `passed:false` and paused | none |

## 4. What SAIPEN delivered, and the proof for each

**F-01 routing.** `tools/saipen_engine/finding_route.py` resolves a blocked
finding to existing owner Work with codes `ROUTED_TO_OWNER` / `DONE_ONLY` /
`NO_OWNER` / `AMBIGUOUS`, and `route_command` emits `saipen ticket claim`,
never `saipen start`. Live answers: this project's SRC-276 →
`ROUTED_TO_OWNER T-1817`; the target's SRC-003 → `DONE_ONLY` (T-47/48/49/50 all
DONE), so a continuation is never invited to reopen it. Proof: executed
FAIL→PASS pair `regression-execution-900f8403443d44809137d674543f3d9d` over
10 controls.

**F-02 dedup.** An open ticket already carrying the rule is the owner; two live
claimants are `AMBIGUOUS` rather than a guess; a DONE claimant never reopens.
Same executed pair.

**F-03 strict prover.** The refusal family proves a missing or weakened carrier
is refused with zero writes, and the real target now proves. Proof: focused
record `419e78ff4007af4a-20261022T115941199589Z`, plus the read-only
observation named in section 2.

**F-05 / F-07 closure and authority.** Delivered under T-1851 with a fresh
executed pair E-17252, extended by T-1817 R004 so closure outcomes are typed
instead of inferred from `recovered: true`. Proof:
`regression-execution-fac522e9eb6249cdb39c09dc45ff0147` and
`regression-execution-ea725e0844324b1ca994cb7e439b400f`.

**F-11 typed ownership.** `tools/saipen_engine/finding_ownership.py` classifies
each finding `ENGINE_INTERNAL` / `OPERATOR_DECISION` / `UNAVAILABLE_EXTERNAL`,
with `UNKNOWN` when the family is unrecognized, and `conformance.py` publishes
that partition on the `ENGINEERING_REQUIRED` diagnostic only when the findings
set is complete. Operator action renders only for a witnessed decision naming
the subject; an engine-owned finding never becomes a consumer `saipen start`.
Proof: executed pair `regression-execution-5498482b60b54d4c9af38ccf19b4449e`
and focused gate `abb782c3d23fccb9-20261022T124647846713Z` (95 tests).
Compatibility preserved: ownership is a derived projection outside
`RULE_TABLE`, so `ruleset_fingerprint()` and every `finding_key` stay
byte-identical — asserted by `test_ownership_does_not_change_finding_identity`.

## 5. Operator decision still outstanding

**F-04 / E-371.** The event is a SAIOPS-created structural mutation with no
`[op: …]` marker, and no trusted operation/journal carrier was found. A checked
reconstruction is therefore unavailable, and a Decision B grant must not be
inferred from token syntax. The decision is narrow: approve the scoped accepted
debt for E-371, or accept that the provenance gap stays open. Nothing in this
shift minted that grant, and no text here should be read as one.

## 6. Host-owned, not claimed

**F-06, F-08, F-09, F-10, F-12** live on the ZAICODE answer/observation/UI
surface. The separated handoff with per-finding acceptance criteria is
`.saipen/evidence/T-1817-zaicode-host-handoff.md`. Measured capability fact:
the adapter registry declares `zaicode` as `ADVISORY` / `ADVISORY` /
`response_hook: null`, matching the captured `enforcement.language: none`.
SAIPEN's own response surfaces (`response style`, `response digest`,
`response render`, `response check`) exist and are provable; they need the host
to call them at the reply boundary.

## 7. Preserved fail-closed behavior (not drift)

- Refusing to forge the E-371 authority token was correct.
- Refusing to hand-write archive sidecars was correct.
- No publish, and FUTURE_GATE stayed closed.
- The goal verdict stayed `passed:false` despite a fully-checked host TODO
  list.

## 8. What this document is not

No claim here rests on a proxy signal, an inferred operator decision, or an
assumed absence. It does not claim a ZAICODE edit exists, does not claim the
historical origin of the missing sidecars, does not claim the host's
enforcement beyond the captured session, and does not reopen FUTURE_GATE or
grant a goal pivot.
