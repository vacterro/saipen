# SAIPEN defect report — the ship source-coverage gate deadlocks a repository with no autonomous exit

Reporter: buffy, working in `V:\___VAC\__K\__CODE\_PY\_SAIPENVIEW`
Protocol: 8.0.1
Date: 2026-09-18
Class: release-gate deadlock / correctness vs. liveness / refusal without an autonomous route
Severity: P1

## Why this report exists

`saipen push` refused to publish a fully verified release because of an
unrelated ticket that is parked, and the protocol offers no operation an agent
may legally perform to clear it. The user-visible consequence is that a
repository can reach a permanent, unbreakable shipping deadlock that only a
human operator can lift by hand-writing an authority grant — which contradicts
the premise that a session works autonomously until it truly needs a human.

The blocker is not a bug in the reporting project. It is a missing liveness
property in the ship gate. This report records it so it can be repaired
autonomously in the protocol rather than worked around by fabricating authority
in every affected project.

## Executive summary

1. `release_gate()` (`tools/saipen_engine/intake.py:2134`) refuses `saipen
   ship` if **any** BOARD ticket carrying a `source_receipts` link has
   non-terminal coverage — regardless of whether that ticket is the one being
   released.
2. A ticket parked in `## BLOCKED` never reaches `ticket done`, and the only
   mechanism that seeds a request's own coverage clause
   (`ensure_request_clause`, `operations.py` via `discharge_request_clauses`)
   runs **inside** the finish path. A blocked ticket therefore keeps
   `actionable == 0` forever.
3. `coverage_complete()` requires `actionable > 0` (`intake.py:1807`). Zero
   actionable clauses can never be complete, so the gate stays red
   permanently.
4. The only terminal escape is retirement, whose sole reason code is
   `MISROUTED_PROJECT_BINDING` — a claim that the work was minted into the
   wrong project. When the parked work is a *genuine* external-owner defect,
   that claim is false and must not be asserted. Retirement also requires a
   separate ACTIVE operator receipt whose stored bytes carry an
   operator-authority capsule; an agent that types those bytes itself is
   fabricating the authority the gate exists to require.
5. Net effect: a single blocked, correctly-routed, empty-coverage ticket
   freezes **all** publication in the repository, and the frozen session has no
   legal move. The refusal (`RELEASE_FAILED` / `stage: SOURCE_COVERAGE`) also
   carries no `canonical_next_command`, so it is a refusal without a route —
   the class `admission.py::_BRAKE_ROUTES` closes for protocol-state refusals.

## Deterministic reproduction

Observed live in `_SAIPENVIEW` on 2026-09-18, protocol 8.0.1.

Preconditions:

- A DOING release ticket in `phase: SHIP` with a complete release scope and a
  green `validate --gate core` / `--gate ship`.
- One BOARD ticket (`T-850`) in `## BLOCKED` whose `source_receipts` names
  `SRC-007`; `SRC-007` is an ACTIVE `user_instruction` receipt with an empty
  coverage ledger (`requirements: {}`).

Command and result:

```
saipen push --json
{"ok":false,"code":"RELEASE_FAILED","stage":"SOURCE_COVERAGE",
 "detail":"active source receipt blocks ship: {'ok': False, 'code':
 'SOURCE_UNRESOLVED', 'receipt': 'SRC-007', 'work': 'T-850', 'coverage':
 {'receipt': 'SRC-007', 'requirements': 0, 'actionable': 0, 'terminal': 0,
 'dispositions': {}, 'unresolved': []}}"}
```

No `canonical_next_command`, no `next`, no `next_action`. The refusal names the
blocked work but no move that could clear it.

Direct gate probes confirm the mechanism and rule out the release ticket as the
cause:

```
intake.release_gate(root, "T-874")
 -> {'ok': False, 'code': 'SOURCE_UNRESOLVED', 'receipt': 'SRC-007', 'work': 'T-850', ...}
intake.work_closure_gate(root, "T-850")
 -> {'ok': False, 'code': 'SOURCE_UNRESOLVED', 'receipt': 'SRC-007', ... 0/0 ...}
intake.work_closure_gate(root, "T-874")
 -> {'ok': True, 'code': 'SOURCE_COVERAGE_COMPLETE', 'receipts': ['SRC-017']}
```

The release ticket's own source is green. The gate is red solely because of an
unrelated parked ticket.

## Root cause (three composing defects)

1. **Gate scope is repository-wide, not release-scoped.**
   `release_gate()` iterates every `_board_source_links(root)` entry and returns
   on the first non-terminal link. A release is blocked by work it does not
   touch and cannot modify.

2. **The clause-seeding mechanism is unreachable from the trap.** `SRC-007`
   carries zero requirements. `ensure_request_clause` — the operation that gives
   a request its one self-clause — is only invoked from `finish_ticket` /
   `_only_request_clauses_await` (the `ticket done` path) and from the
   `INCOMPLETE_TICKET` route. `release_gate` never seeds it. A ticket that is
   parked (BLOCKED) never runs `finish_ticket`, so its receipt is permanently
   zero-clause and permanently incomplete.

3. **The only legal terminal disposition is gated behind human authority and a
   false premise.** `RETIREMENT_REASONS` contains only
   `MISROUTED_PROJECT_BINDING`, whose definition requires that the ingress
   resolved the wrong project root. `audit_manifest.py`'s `OPTIONAL_DIRS` /
   `NON_EXPORTABLE` defect is a real protocol defect belonging to the SAIPEN
   repository, not a misroute of `_SAIPENVIEW`'s execution history, so the
   reason does not apply. Retirement also demands an ACTIVE separate operator
   receipt carrying the exact grant capsule; an agent cannot author it without
   fabricating operator authority.

## Why this is worse than a normal WAIT

A `WAIT:` is a legitimate human boundary and is expected to name exactly what
is missing. This deadlock is different in three ways:

- It is **invisible until ship**. Recovery, validation, review and every read
  path are green; only the terminal publish is refused.
- It is **repo-wide**. Any single parked source-linked ticket freezes every
  future release, in every project that accumulates blocked audits.
- It has **no route**. The refusal carries no `canonical_next_command`, so a
  session that trusts the router has nothing to execute next; the only moves
  are the two forbidden ones (fabricate a misroute retirement, or resolve an
  external repo from here).

Empirically this blocks a legitimate, fully verified `0.1.33` release of
SAIPENVIEW whose only crime is that a different ticket (`T-850`) is parked on
an external defect.

## What would make it autonomous

Candidates, in the order I would try them:

1. **Scope the gate to the release.** `release_gate()` should fail a ship only
   for coverage that this release actually depends on (the release ticket and
   the work its reviewed scope implements), not for every `source_receipts`
   link on the board. Unrelated parked work must not freeze publication.
2. **Seed the request clause at the gate, not only at finish.** Any place that
   evaluates `coverage_complete` on a `user_instruction` receipt should be able
   to materialise its self-clause, so "zero clauses" stops meaning "permanently
   incomplete".
3. **Separate `BLOCKED_EXTERNAL` from local non-terminal coverage.** `SOURCES.md`
   already names `BLOCKED_EXTERNAL` at Work lifecycle level. A receipt whose
   clause is blocked on an external owner should not be able to hold unrelated
   publication hostage; the release gate should exclude it while still
   refusing to let *that* work close.
4. **Give the refusal a route.** The `SOURCE_COVERAGE` branch should carry a
   `canonical_next_command` (the reachable inspect/block/retire-name move), so
   the refusal class matches `_BRAKE_ROUTES`' contract for every other
   protocol-state refusal.
5. **Do not require fabricated authority to leave a trap.** Where a genuinely
   correct but externally-owned ticket blocks shipping, provide a legal
   non-deceptive disposition (e.g. `EXTERNAL_OWNER` / `NOT_THIS_PROJECT` with
   proof) that records the truth instead of forcing a false
   `MISROUTED_PROJECT_BINDING`.

Candidate 1 or 3 alone removes the deadlock for the reporting project. Candidate
5 removes the incentive to fabricate that exists today.

## Impact on the reporting session

- `_SAIPENVIEW` was left at `phase: SHIP`, ticket `T-874`, with a complete,
  verified, recorded release scope (`v0.1.33`) that cannot be published.
- All gates green: `release_gate --dev` PASS, `validate --gate core` PASS,
  `--gate ship` PASS, compileall PASS, targeted 51 + wave 42 tests PASS.
- The only sanctioned exits are (a) assert a misroute that did not happen, or
  (b) hold the release until a human hand-writes an authority grant. Both are
  failures of autonomy, which is the point of this report.

## Related

- `FUTURE GATE — AUDIT CONTRACT OPTIONAL ROOTS EXPORT RUNTIME STATE; PROJECT-LOCAL
  SCOPING IS ERASED BY REGENERATION_20260916.md` — the underlying `T-850` /
  `SRC-007` defect this report is downstream of.
- `SAI-DEFECT-20260918-routeless-finish-source-gate.md` (this inbox) — the
  sibling refusal-without-route in the `ticket done` path.
- `SOURCES.md` § "Contract, coverage, and reread gates" — states "SHIP cannot
  pass while linked active source coverage is red", which is the rule being
  applied with repository-wide scope.
- `_BRAKE_ROUTES` (`tools/saipen_engine/admission.py`) — the route contract this
  refusal does not honour.

## Evidence

- `saipen push --json` refusal, quoted verbatim above.
- `intake.release_gate` / `intake.work_closure_gate` probes, quoted verbatim.
- `tools/saipen_engine/intake.py:1807` `coverage_complete` (requires
  `actionable > 0`); `intake.py:2134` `release_gate`; `intake.py:1686`
  `ensure_request_clause`; `intake.py:1854` `discharge_request_clauses`.
- `tools/saipen_engine/operations.py:2890-2936` finish-path clause discharge.
- `tools/saipen_engine/retirement.py:109` `RETIREMENT_REASONS`.
- `tools/saipen_engine/audit_manifest.py:131` `OPTIONAL_DIRS`, `:140`
  `NON_EXPORTABLE` — the external defect `T-850` is parked on.
