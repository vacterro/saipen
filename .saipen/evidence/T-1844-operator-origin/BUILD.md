# T-1844 unfinished operator-origin repair

The full child acceptance remains on BOARD; T-1819 retains the whole original
SRC-278 mission, actual Freebuff/Luna integration, T-1479 recovery and A-Q UI
acceptance. Neither Work is complete. Current phase is BUILD.

## Concrete current delta

The real-carrier regression is `tools/test_t1844_operator_origin.py`:
eight tests, nine assertion failures on the original implementation; all eight
currently pass. It tests the real SAIPEN digest/file names, matching model-owned
cache envelopes, a forged proof/unkeyed seal, ordinary local work, mismatch
refusal and preservation of an unverified proof for retry. No host was involved.
`red-control.log` and `current-negative.log` preserve observations. The test was
subsequently formatted and strengthened with the unconsumed-envelope check;
the FINAL native executed pair must restore the saved preimages against the
same final oracle, rather than cite the earlier transcript as a final pair.

`operator_task.authority_for_provenance` now needs an independently supplied
project and a broker-verified exact-event proof before granting privileged
effects. Raw matching carriers are classified model_supplied with integrity
metadata; ordinary capture/local_work remain true. Raw historical labels alone
no longer authenticate origin. Source-derived authority passes root/receipt.
Entry, goal and operation callers now pass root explicitly. In particular,
goal_entry uses project_root before its later local root variable is assigned.

The client has `verify_operator_origin`: typed `operator-origin` proof, exact
digest/project, optional delivering session and Source receipt, production
endpoint only, authenticated service, typed matching response. It deliberately
has no model-selected runtime override. The requested broker op is
`verify-origin` and its successful reply kind must be
`operator-origin-verdict`. THIS BROKER OP IS NOT IMPLEMENTED YET. Existing
brokers reject it, so no genuine positive path is claimed or silently invented.

Ingress transport preserves an operator_origin dictionary but does not trust
it. A present proof which cannot be verified is not consumed. The cache file is
not an authority. The remaining genuine delivery/binding protocol is still owed.

`handoff.authority_error` now uses authority_for_receipt rather than trusting an
old operator_carrier label. Original inherited bytes of ten production files
are in prefix/ and before.json; no original staging was changed. Preserve that
inheritance and restrict later diffs to this Work.

## Actual checks and limitations

- New negative suite: 8 PASS after containment. This is not ticket acceptance.
- Existing Freebuff suite: 19 tests, 2 FAIL and 1 explicit live-host SKIP.
  A/F still expect a plain file/digest to prove identity. Do not delete these
  positive assertions or relabel them as real UI success; replace their input
  fixtures only when the genuine proof path exists. Other broader consumers
  and goal/source/entry/response/handoff tests have not all been verified.
- Whole-source contracts: refusal registry 4 PASS, printed-command reachability
  11 PASS, subprocess UTF-8 contract 6 PASS. Scoped Ruff is green after fixing
  line lengths and the early goal_entry root reference. Whitespace was checked.
- No full unit family, final native regression pair, VERIFY, REVIEW, SHIP,
  pending cohort, publication, install or genuine Freebuff positive is claimed.

## Existing authority to reuse

host_authority_broker.Broker.identify proves a registered host's own shipped
hook from OS process facts; model shell descendants are a distinct rejected
shape. Its in-memory Authority key and Ledger._provenance/verify already own
keyed record authenticity. host_authority_client._exchange authenticates the
actual service endpoint; do not create another signer, daemon, env bypass or
same-user private-key file. Generic admission capabilities bind a session and
policy, NOT an exact human message; verify_record alone is insufficient as an
operator-intent verifier.

## Required next implementation

1. Implement broker-owned issue/verification and consumption/reference state
   for exact native human events, using the existing authenticated writer and
   ephemeral signer. Retain native event identity, content digest, project and
   lineage, session, task/goal scope, permitted action, issuer/generation and
   expiry/revocation. Self-asserted authenticated flags must grant nothing.
2. Authenticate the delivering model/tool scope independently of its own env
   strings. A readable signed proof plus a model-chosen matching session is
   not enough. Use the real host's trusted tool-spawn path to register an
   OS-observed worker PID/birth/session/project relationship if needed; nested
   callers must be descendants of that real registered worker. Never register
   the shared host/orchestrator PID as an arbitrary model session.
3. Make first delivery and Source/goal-operation binding idempotent and safe
   under errors/crash. A writable consumed flag is not one-use proof. Bind a
   verified origin to the actual canonical Source/operation so copying it into
   a second Source, another task, another goal epoch or another project cannot
   mint privilege. Preserve legitimate historical attribution and valid scoped
   continuation without promoting old model_supplied receipts. Expired,
   revoked, lost-issuer or unbound proof stays unverified. Do not use a generic
   admitted-session token as exact request authority.
4. Wire genuine native issuance before privileged projection, and migrate all
   real consumers. Remaining direct witness-label checks include
   decision_request.validate_authority_escalation (currently no production
   callers found), handoff/board legacy shapes, response_surface's response
   authority and retirement history validation. Response authority currently
   calls the helper without root, so its genuine positive path is still owed.
   Inspect intent/action binding rather than indiscriminately restoring every
   old privilege bit from any authenticated message.
5. Add positive issuer/consumer/scope/replay/expiry/revocation/loss controls
   with honest isolated authority fixtures, then migrate related existing
   fixtures without weakening assertions. Test the Source/entry/goal pipeline
   and mismatch/ordinary-local behavior. Unknown safety dependencies require
   the appropriate full-family check once the final engine batch is ready.
6. Produce the concrete Freebuff handoff from the inspected installed source
   (see parent SCOUT.md and its verified ASAR extracts). Keep real host A/O/P
   and original T-1479 admission/GUI acceptance as the parent's actual live
   gates, not mock-only successes. Do not install or patch Freebuff here.

Useful verified vendor locators from this turn: the installed orchestrator's
message route at lines 251295-251304 calls engine.postMessage; Engine.postMessage
at 235599 calls admitMessage, which builds user input (235622) with opts.origin.
messageThread at 235602 is a separate origin-bearing path; distinguish it from
human UI delivery before proposing a hook. The package's generic CLI wrapper
is not the Desktop's input boundary. The Freebuff Electron source already
keeps launch secrets out of env and sends them by stdin; preserve that boundary.

Continue implementation. Do not leave the goal blocked on a vendor change while
the owned SAIPEN issuer/consumer work above remains implementable.
