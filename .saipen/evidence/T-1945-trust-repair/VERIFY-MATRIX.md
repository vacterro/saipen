# T-1945 VERIFY matrix — SRC-344 trust repair

Measured 2026-10-27 on the working tree at phase VERIFY, last_event E-18959.
Categories are reported separately. A green entry in one category is not
evidence for another, and nothing here is claimed beyond what was measured.

## UNIT — PASS

Canonical focused gate (tools/verification_policy.json = focused):

    python -c "import sys; sys.path.insert(0,'tools'); from saipen_engine.core_unit import main; raise SystemExit(main(['focused','T-1945','--project-root','.','--pattern','test_t1945_analysis_progress.py','--pattern','test_t1945_campaign_driver.py','--pattern','test_t1945_incremental_discovery.py','--pattern','test_t1945_host_trust.py','--timeout','300']))"
    -> {"ok": true, "verdict": "PASS", "ran": 44,
        "record": ".saipen/evidence/focused-unit/2f39f2b17a09e411-20261027T143230409880Z.json"}

That invocation returned `reused: true` because the source bytes were
unchanged: it re-verified the recorded result rather than re-executing the
suite. To exclude a stale record, the four modules were re-run directly in a
separate interpreter (`verify-independent-gate.log`):

    PYTHONPATH=tools python -m unittest test_t1945_host_trust \
        test_t1945_analysis_progress test_t1945_campaign_driver \
        test_t1945_incremental_discovery
    -> Ran 44 tests in 0.256s, OK

Per module:

| module | tests | repair |
|---|---|---|
| test_t1945_host_trust.py | 18 | AUT-001 (brokered identity gate, persisted-status split, typed numeric refusals) |
| test_t1945_analysis_progress.py | 8 | AUT-007 (ANALYSIS_PROGRESS stays schedulable; findings branch preserved) |
| test_t1945_campaign_driver.py | 9 | AUT-006 (bounded CampaignController.run + CLI caller) |
| test_t1945_incremental_discovery.py | 9 | AUT-005 (discover() consumes the paged transport) |

Red-before-green pairs for all four repairs are in this directory
(`aut00{1,5,6,7}-pair.txt`), each recorded against a scratch tree with only the
repair reverted.

## CONTRACT — PASS

The trust seams and campaign gate contracts are exercised without weakening
them. Suites that assert the *contract* rather than the mechanics:

| suite | tests |
|---|---|
| test_t1931_saipal_boundary.py | 22 |
| test_t1932_campaign_authority.py | 23 |
| test_host_authority_broker.py | 38 |

Two `test_t1931_saipal_boundary.py` discovery tests were re-anchored during this
ticket because `discover()` no longer reads through `_run_cmd("report")`. They
now serve a real report spool; their assertions (NO_NEW_EVIDENCE on an empty
corpus, ANALYSIS_BLOCKED with marker bytes preserved on an unreadable
watermark) are unchanged, not relaxed.

Identity is verified by the broker, not by receipt shape: `_broker_verified_receipt`
delegates to `host_authority_client.verify_record` and returns False on any
exception, including when no broker exists. `test_t1945_host_trust.py`
deliberately does not patch that function.

## INTEGRATION — PASS

Campaign mechanics end to end through the controller:

| suite | tests |
|---|---|
| test_campaign_matrix.py | 35 |
| test_campaign_production_gates.py | 18 |
| test_campaign_continuation_assessment.py | 7 |
| test_t1931_campaign_lifecycle.py | 27 |

Live CLI smoke (real process, not mocked):

    python tools/saipen.py campaign run --steps 0 --json
    -> {"ok": false, "code": "INVALID_STEP_BOUND",
        "detail": "max_steps must be a positive integer, got 0", "route": "campaign"}
    exit status 1

Combined blast-radius run of all eleven suites (`verify-regression-suite.log`):

    Ran 214 tests in 33.076s, OK

## INSTALLED_HOST — NOT_RUN

No live host acceptance was obtained or can be obtained from this seat.

- The shipped `zaicode` adapter declares `declared_strength: "ADVISORY"` and
  `response_hook: null` in `extensions/adapters/registry.json`. With no response
  hook it produces no host acceptance receipt at all.
- The broker exposes no operation that mints one. Its full op surface
  (`host_authority_broker.py::handle` plus `WRITE_OPS`/`READ_OPS`) is
  `ping, status, shutdown, verify-origin, verify-source-origin,
  prepare-origin-goal, verify-origin-goal, verify-origin-campaign,
  prepare-origin-debt, verify-origin-debt, evaluate, verify, verify-record,
  authorize, admission, invalidate, issue-origin, register-origin-worker,
  revoke-origin`. `verify-record` only checks an existing record's HMAC; none
  of the rest attest that a host accepted a dispatched turn.

A PASS in `test_t1945_host_trust.py` shows the *validator* refuses unverified
receipts. It does not show an installed host issued a real one. Claiming it
would be exactly the mocked-broker DONE that this ticket forbids.

## LIVE_END_TO_END — NOT_RUN

The chain host turn -> dispatch -> campaign generation -> SAIPAL slice ->
publication requires the installed native host described above. It is not
available, so no end-to-end turn was measured.

Additionally, the live native campaign grant for T-1943 remains uncommitted by
the operator, so the campaign cannot be driven against the real issuer.

## SOAK — NOT_RUN

No multi-hour or multi-cycle runtime was measured. The `run()` driver is bounded
by design and was tested at N=1..3 in `test_t1945_campaign_driver.py`. That is
unit evidence about the bound, not soak evidence, and no wall-clock duration is
claimed anywhere in this ticket.

## Pre-existing reds (observed, out of scope, not repaired)

1. `engine-state-contract -- properties continuous_maintenance` drift.
2. `test_audit_dogfood.py::ProducerNeutrality` — 85 offenders in untracked
   bridge modules.
3. `EX-000022` closure-provenance drift.
4. ~300 foreign pre-staged paths blocking T-1815/T-1816/T-1817/T-1856/T-1857
   and all publication.
5. Repo-wide ruff: 259 findings, including 11 in untouched `supervisor.py`.
   The four new test modules were linted to zero; `host_dispatch.py` additions
   introduce no new finding.
