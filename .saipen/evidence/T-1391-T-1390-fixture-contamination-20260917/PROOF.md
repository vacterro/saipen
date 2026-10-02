# TEST_FIXTURE_CONTAMINATION proof -- T-1391/SRC-060 and T-1390/SRC-059

Recorded 2026-09-17 by the T-1392 cleanup session after a fresh read of the
repository bytes (STATE.md, BOARD.md, LOG.md, intake index, request bodies,
request metadata) and the two fixture test modules named below.

## The two fake user tasks

SRC-060 body (sha256 7da1fa1015f5457bd93ed7a0624ff13050befd03a37e85ad511c0889cb58ab2e,
received 2026-09-17T19:47:43Z, linked_work T-1391):

    add a trailing comment

SRC-059 body (sha256 cb1d490e3e5db4157a79d25e8bd03670a36041e925e0b36ebfc02a5e18eb60d6,
received 2026-09-17T19:47:38Z, linked_work T-1390):

    add a docstring to src/app.py

Both bodies match, byte for byte, strings SAIPEN's own tests type into
`saipen start`:

* `tools/test_session_binding.py:217`
  `[sys.executable, str(SAIPEN), "start", "add a trailing comment", "--json"]`
  (helper `_start`, `cwd=str(project)` where `project` is a temp fixture,
  no `--project-root` argument).
* `tools/test_session_binding.py:96`, `:256`, `:288`
  `[sys.executable, str(SAIPEN), "start", "add a docstring to src/app.py", "--json"]`.
* `tools/test_canonical_write_route.py:148` (the file staged as new in this
  worktree)
  `"add a docstring to src/app.py"` passed to `saipen start` by `_started()`
  (that call does pass `--project-root str(project)`; the escaping calls are
  the `test_session_binding.py` ones).

No other occurrence of either string exists in the repository outside test
fixtures.

## Provenance: no operator carrier

`.saipen/intake/active/SRC-060.meta.json` and `SRC-059.meta.json` both carry

    "request_provenance": {
      "witness": "model_supplied",
      "note": "no operator carrier and no transport obligation: the stored
               bytes are what this session supplied, and nothing compared
               them with what the operator wrote"
    }

with `source_authority.mode = "exact"` over bytes the session itself supplied.
No operator-written message carrying either request exists.

## The canonical chain they stole

LOG.md:

* E-7012 17.09.26 19:47 `user request SRC-059 projected as T-1390 (user_explicit)`
* E-7013 17.09.26 19:47 T-1388 blocked ACTIVE_DEPENDENCY:T-1390
* E-7014 17.09.26 19:47 T-1390 claimed
* E-7015 17.09.26 19:47 `user request SRC-060 projected as T-1391 (user_explicit)`
* E-7016 17.09.26 19:47 T-1390 blocked ACTIVE_DEPENDENCY:T-1391
* E-7017 17.09.26 19:47 T-1391 claimed

BOARD.md:

* T-1391 `[/]` DOING, `source_receipts: SRC-060`, owner claude,
  claim_time 2026-09-17T19:47:46Z, claim_session
  97faf1be58f81845b805d73a5972e2eb (lapsed at retirement time).
* T-1390 `[ ]` TODO, `source_receipts: SRC-059`, blocker
  ACTIVE_DEPENDENCY:T-1391, resume_phase SCOUT.
* T-1388 `[ ]` TODO [P0], blocker ACTIVE_DEPENDENCY:T-1390, resume_phase BUILD.

## Product bytes

`src/app.py` does not exist in this repository (absent from disk and from the
git index), so neither contaminated request was implemented and no product
mutation exists for either. This document binds the contamination proof only;
the fixture-escape root-cause measurement is a separate artifact so this
evidence stays byte-stable after retirement.

## Disposition requested

Retire T-1391/SRC-060 first, then T-1390/SRC-059, reason
`TEST_FIXTURE_CONTAMINATION`, so the parked parents restore automatically:
T-1390 to SCOUT, then T-1388 to BUILD. No DONE, no coverage, no rewriting of
the original request bytes.
