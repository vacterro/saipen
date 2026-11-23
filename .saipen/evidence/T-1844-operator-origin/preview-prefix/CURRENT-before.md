# T-1844 current implementation checkpoint

Current protocol authority remains `.saipen/STATE.md`, BOARD and LOG. This file
is implementation/evidence context, not a phase transition or completion claim.
It supersedes the implementation-status paragraphs in the earlier BUILD.md;
that earlier file retains the original source/vendor investigation.

## Continuation on 21 October: Source/event identity

This continuation preserves the entire original `cc all` objective and T-1819's
SRC-278 mission. It remains BUILD. Before relying on the mission, the canonical
`source show SRC-278` read verified the active exact body, SHA256
`978ae2709d51a6fa5037263039565cf0b89f9fa9251109d590609421853745bf`,
and its unchanged historical `model_supplied` provenance. No actual Freebuff
acceptance or T-1479 recovery is claimed.

The seven production files in this continuation are `intake.py`, `entry.py`,
`operations.py`, `retirement.py`, `response_surface.py`, `decision_request.py`
and `source_append.py`. Exact pre-turn bytes are under `turn-prefix/tools/`;
other saved files there were preserved but remain unchanged. Original CRLF/LF
styles are preserved. The graph MCP remains unavailable; exact source reads
and caller searches were used, without negative graph-completeness claims.

- Source dedupe now compares operator-event identity as well as exact bytes.
  The comparison grants no authority: independent broker verification still
  owns trust. Model/native and separate native events keep distinct Sources;
  retries locate their own event, and older provenance is never rewritten.
- Integrity checks precede event filtering. Indexed Sources cannot be adopted
  as crash orphans. Body-only interruptions reuse the orphan, while persisted
  orphan metadata retains its exact original event and receipt time. Corrupt
  orphan metadata fails closed. Closed predecessors remain historical and a
  repeated request retains its supersedes relation.
- START projects its exact captured Source after transport consumption through
  `user_request(source_receipt=...)`; that argument must resolve an active,
  integrity-checked Source with exactly the rendered body. No re-witnessing,
  second model-labelled Source or body substitution is accepted.
- The direct user-request and Source-append callers now pass their independent
  project root when verifying native ingress.
- An authorize-goal retry scans exact matching active Sources and checks the
  existing live binding; an older model Source cannot hide the later original
  bound event. The old model Source is retained unchanged.
- Automatic false-authority retirement requires affirmative historical
  non-operator provenance. Expiry/revocation/issuer loss is not proof that a
  historical genuine projection was model-authored. The archive validator
  uses the same conservative historical classification. This grants no
  current privilege from a witness label.
- Response/decision queries use existing-only receipt verification and cannot
  create an unused event's Source binding. Other authority callers still need
  completion of the read-only/preview audit; do not extrapolate this coverage.

`test_t1844_source_event.py` has 17 tests. The unchanged final oracle ran against
exact pre-turn and current subjects with identical copied dependencies,
configuration and native Python 3.11.9: pre-turn 14 assertion failures, no test
errors; current 17 PASS. `source-event-pair.json` records all subject hashes,
oracle identity and transcripts. This is a diagnostic pair for this delta,
not the final canonical executed-regression receipt for the entire ticket.

The direct kernel run passed 34 tests. A 170-test Source suite passed before the
final orphan/append changes, so it must be remeasured on the final generation.
The broad START run executed 75 tests and reported 20 failures, including 13
alphabet subcases and raw-hash operator-authority expectations; the earlier
ingress run reported 1 failure across 13 tests. These are unresolved fixture/
consumer evidence, not PASS and not proof that the broad suite is repaired.
No positive assertions were weakened. Owned Ruff passed on the frozen source.
The native ten-module focused run terminated FAIL:
`f6abfaafe4df0bc1-20261021T082055349866Z.json`, 319.234 seconds. Its first five
modules completed 103 tests with no assertion failures; the remaining total
budget expired in refusal-registry discovery, leaving the selection incomplete.
The broker's 38 tests passed but took 169.829 seconds, versus 31.484 in the
earlier generation's run. No budget was raised. The subsequent four-pattern
check is incremental evidence for this delta, never a replacement PASS for the
failed broader selection or the ticket's final acceptance.

That four-pattern check is now terminal PASS: native record
`f6abfaafe4df0bc1-20261021T082425618222Z.json`, 229 tests in 135.329 seconds,
no reuse, no record problem. It includes the 170 Source tests, unchanged eight
carrier-forgery controls, 34 broker/kernel tests and 17 Source/event controls.
An independent `record_problem` check with the launcher-matching runtime and
PATH returned null on the current source. Final owned Ruff also passed.
No test process remains live. The original broader selection and core failures
above remain unresolved; this record supports only its actual four patterns.

Canonical core conformance is also CURRENT_FAIL, receipt
`receipt-be432098461c`: five problems, 21 warnings. Four problems are the
ticket's untracked new runtime/test files (including this continuation's new
test); the other is EX-000016's stale installed-engine dependency after engine
changes. These remain real publication/closure obligations. No staging, oracle
waiver, dependency relabelling or unrelated restoration was used to hide them.

## Implemented

- `operator_origin.py` uses the existing broker's keyed Ledger and native
  identity verifier for issue/register/verify/revoke. It creates no signer or
  service. Proofs bind exact content, project/lineage, native host PID/birth,
  session, task/goal/budget scope, action, nonce, expiry and issuer generation.
- Consumers require the independently registered worker ancestry/birth. A
  session env value or readable proof cannot replace that OS binding. Shared
  host registration, PID reuse, session borrowing, action substitution and
  changed native-event redelivery refuse. Native revocation permits assigning
  the worker to a new human event; an active old binding cannot be transplanted.
- Raw task hashes/files/cache envelopes grant capture/local work only. Matching
  file transport can use a separately verified exact native event. Historical
  model-supplied records remain model-supplied even when handed a later proof.
- One event binds one exact canonical Source, or one stable goal operation.
  Source references retain expiry/task/goal/budget checks. Goal continuation
  uses the broker's reserved scope plus the original COMMITTED journal, not
  fresh-delivery privilege. Valid scoped goals survive task churn, delivery
  expiry and native replacement workers; wrong scope, revocation and issuer loss
  fail. Neither a copied Source nor a rewritten journal creates a new grant.
- Source/entry/goal callers pass their independent project. Response authority
  passes project scope; the legacy decision helper no longer trusts a string
  witness. Generic admission remains distinct from exact operator intent.
- Native goal-entry and existing-goal authorization use a nonce-stable operation
  ID. Refused APPLY can retry the same accepted Source/reservation. Preview of
  that retry writes neither project files nor broker binding. `existing_only`
  verification is a narrower query that cannot create an unbound Source grant.

## Evidence

The pre-continuation native focused record was
`6e198c63ef303dc2-20261021T052219775924Z.json`: PASS, 155 tests, 144.766 seconds,
nine selected modules, no record problem, no reuse. It covered its then-frozen
source including Source-bound retry and the nonbinding existing-only query;
it is not current evidence for this continuation's changed source.
The prior record `135f26d6c54f074a-20261021T051519542353Z.json` passed 153 tests
and is retained as evidence of the earlier generation only.

Targeted broker/consumer/doctor tests passed after the retry fix; the additional
existing-only negative control also passed in the current wider execution.
Owned Ruff passed on the frozen final source. The real-process broker Identity
suite is part of that wider selection; the earlier standalone seven identity
tests passed. The Freebuff suite retains its explicitly unavailable live-host
SKIP. Simulated positives use the real isolated broker with explicitly simulated
native identity and process facts, never fabricated Freebuff UI acceptance.

`diagnostic-carrier-pair.json` binds the SAME unchanged eight-test oracle
SHA256 `d51851cf7b403b1e07eb6bc1832b523b936f2ddd9b390e2b2de9cf8075369560`.
The saved production preimages produced nine assertion failures, no test errors;
the current implementation passed all eight. Both used the native 3.11.9 runtime
and the same dependency/configuration snapshot. The first attempted diagnostic
was unavailable because the copied fixture omitted the adapter registry; both
failed transcripts are preserved in diagnostic-instrument-missing-registry/.
After adding that same required registry to BOTH subjects, known-good was green.
This diagnostic is not the required native executed-regression receipt. BOARD
now declares `regression_evidence: executed`; final VERIFY must still run the
canonical unchanged-oracle operation on the completed subject.

The earlier broad legacy-consumer run executed 95 tests: 36 failures, one error,
one live-host skip. It exposed old raw-hash/file trusted-authority fixtures.
The transport/Freebuff portion was migrated and then passed all 36 selected
tests with one explicit live-host skip. The remaining ingress/goal/continuation
fixtures have not been migrated or reverified. Their stronger assertions must
survive; no production env bypass or permissive fallback is acceptable.

## Next owned work

1. The main Source/event dedupe defect and exact-Source START projection are
   repaired in this continuation and covered by the 17-test diagnostic pair.
   Preserve those controls during fixture migration. Further hostile-history
   cases should include model-labelled metadata that already carries a copied
   genuine proof, plus Source/goal callers with several byte-identical records.
2. Complete the read/write and historical-authority caller audit. Initial Source
   binding and current privileged effects differ from historical attribution.
   Retirement's false-authority audit is now conservatively historical, and
   response/decision queries are existing-only. Acceptance, handoff, retirement
   authority and reset planning still require a complete query-versus-binding
   audit. Read-only/preview callers must not create a new Source binding. Use
   typed, conservative evidence rather than trusting a witness label for a grant.
3. Migrate `test_ingress_authority.py`, `test_t1494_continuation_authority.py`,
   `test_t1704_legacy_goal_authority.py` and related handoff/response/source
   fixtures. Preserve positive, negative, crash, cold-process and actual validator
   coverage. The new kernel tests prove live-owner behavior in an isolated
   authority fixture, but do not replace those other contracts.
4. Complete native issuance/spawner caller integration and consumer coverage.
   NATIVE-ORIGIN-CONTRACT.md describes the exact interface for the parent.
   Freebuff still lacks a proven trusted human-event/spawn bridge compatible
   with the registered broker identity policy. No vendor patch/install or real
   UI acceptance has been performed here. Keep T-1819's full original mission.
5. Final native executed regression, applicable full verification, semantic
   review and local closure remain due. T-1844 stays BUILD. Do not block the
   whole goal on the vendor while the owned work above remains runnable.

## Preservation

The original ten production preimages and hashes remain in prefix/ and
before.json. Additional pre-resume files are in resume-prefix/. No Git staging,
commit, publication or unrelated dirty-file restoration was performed. The graph
MCP was unavailable in this host; exact source reads supplied the evidence.
