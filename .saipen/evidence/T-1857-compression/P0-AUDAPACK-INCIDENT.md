# P0: genuine operator continuation cannot reach ZAICODE authority

STATUS: BLOCKED. Native continuation has not been restored or proved LIVE.
OWNERS: SAIPEN core authority boundary and ZAICODE native host integration.
Sources: SRC-291 (exact P0 request), SRC-292 (AUDAPACK clarification), SRC-293
(forwarded FastPrompter handoff, retained as context). T-1858 is the existing
incident integration track; T-1859 now explicitly requires genuine LIVE proof.
E-17353 strengthens that acceptance contract; it is not a test PASS.

## Confirmed current failure

The native host's recent-project registry resolves AUDAPACK to
`V:/___VAC/__K/__CODE/_PY/_AUDAPACK`. The canonical read-only preview reproduces
`RECONCILE_REAUTH_REQUIRED` with `0 waves / 28 tickets`. SHA-256 before/after
STATE, BOARD and LOG are identical. P0-AUDAPACK-preview.json and
P0-AUDAPACK-readback.json retain the actual result and byte identities.

The state is BUILD T-336, hard_wait, operator_required, authority_source E-3335.
Twenty-eight is the processed-ticket authority counter, not a count of pending
queue entries. The registered 3-wave/20-ticket predicate already uses >=.
Neither the real overshoot nor a large queue justifies manually changing it.
No AUDAPACK source, intake, state, board, log or counters were edited.

## The missing bridge is a declared capability gap

The ZAICODE adapter has `hook_artifact: null`, no hook install surface and
`operator_ingress_capability.prompt_to_work_binding: NOT_INSTALLED`.
Its admission is advisory; there is no separated native issuer declared for it.
Thus an installer cannot restore a supposedly deleted ZAICODE hook: no such
artifact is shipped by that adapter. T-415's positive test substitutes a
test-only hook and cannot establish deployed native admission.

The product's operator-ingress.ts looks for `.zcode/hooks/saipen-guard.py` and
constructs a `before_tool`/`read` envelope. Native origin issue in the broker
requires the proven host invocation and the native `UserPromptSubmit` event.
The host also needs actual-worker registration through that same proven native
owner; the current launcher only attempts the optional hook before it spawns
the continuation worker. Copying a file into the expected location would not
supply this missing identity/event/worker integration.

The actual authority service is running and current for its own installed
generation. It is not observed down. Its current policy verifies Claude host
images signed by Anthropic, PBC. The actual running ZAICODE.exe is NotSigned.
Trusting generic node.exe, a renamed executable, an environment flag or an
agent-written image hash would bypass the existing caller boundary. None was
added. The native issuer's accepted identity must be established through an
independently trusted installation/host path before real issue/register calls
can pass. Model-provided input cannot supply that proof.

Doctor also reports the installed ZAICODE skill and machine runtime stale
against the changed checkout. That is a separate generation finding. Running
`host repair` against the same advisory contract can refresh declared runtime
artifacts but cannot create the absent native issuer. No unverified generation
was installed into a running host during this campaign.

## Corrections to the forwarded FastPrompter recovery advice

The reported FastPrompter SCOUT T-1506 / 3 waves / 32 tickets / E-5284 is
consistent with the prior read-only observation, not evidence of recovery.
Its original campaign and queue are retained; no FastPrompter product edit was
made here. The forwarded body is preserved unchanged in the Source receipt.

The handoff's promise that an OpenCode launch carrier will reset the budget is
not valid for the current hardened kernel. operator_task.witness records a
matching task hash as `model_supplied` and explicitly says it is not operator
origin. fresh_cc_provenance additionally requires reset_bounded_authority.
OpenCode's registry entry also has prompt_to_work_binding NOT_INSTALLED and
advisory admission. A carrier or that host's name is insufficient. No OpenCode session was
launched and no command was submitted while pretending to be the operator.

## Actual local repairs and evidence limits

* Resume forms derive from one registry policy. `cc`, `continue`, canonical
  continuation and the allowed all forms share the existing pipeline; the
  independent broker proof still decides renewal.
* Missing-input guidance distinguishes native ingress from an agent replay.
  A read-only AUDAPACK preview shows that guidance and preserves all three
  protocol files exactly. No counter reset was manufactured.
* The 28-processed-ticket case refuses untrusted input. Explicit native-origin
  test doubles prove kernel recovery while retaining hard_wait. Twenty-eight
  and 1,000 queued TODO records do not consume a zero processed-ticket budget.
  Those tests do not prove the ZAICODE UI event, signature or deployment.
* Idle output and its authoritative checker share one display owner. Existing
  operator waits remain valid; blocked Work cannot look complete, and an idle
  projection cannot override an active phase. Controlled regression and the
  four real checker/Stop consumers pass locally.
* A diagnostic-only ZAICODE patch remains scratch-tested and unapplied. It
  prioritizes the actual undelivered-ingress reason over a generic valve flag;
  ten projection cases pass after six original failures. It does not install
  a native bridge. See ZAICODE-NATIVE-INGRESS-HANDOFF.md.
* RUNTIME.md now documents diagnosis, declared-hook repair limits, the native
  owner/worker handshake and use of another already-authenticated healthy
  host on the same project when available. It does not promise OpenCode or
  any particular unverified installed host will work.

## Exact recovery boundary

1. Deliver a reviewed native ZAICODE adapter/host integration whose issuer the
   existing broker can independently verify; bind the original user callback,
   project/session and the worker the host actually launches. Establish its
   trusted deployed executable identity without removing caller verification.
2. Install that reviewed generation through the canonical installer; verify
   the loaded build/adapter and worker registration, then observe a real human
   `cc` in the actual AUDAPACK UI. Confirm canonical grant renewal and eligible
   Work resumption. Exercise replay, wrong scope/worker and untrusted callers.
3. Until those prerequisites exist, retain RECONCILE_REAUTH_REQUIRED. A human
   can use another healthy host that already proves native ingress for this
   SAME project, if one exists. No agent CLI command can substitute for its
   genuine native operator event. Never direct another ineffective cc loop.

No LIVE positive is claimed. Source 291's four requirements, T-1858/T-1859
native acceptance and the overall compression campaign remain open.
