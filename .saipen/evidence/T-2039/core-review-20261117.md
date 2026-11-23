# T-2039 — Core review disposition for saitest/TEST-12

Ticket verify: "Independently reproduce or reject hypothesis, record Core
disposition, apply no package patch during intake."

Package: `saitest/TEST-12` — "adversary and adversarial verification sweep at
66ef622a". `package_identity=sha256:a28ec28020e02fab71a67de7660e8d2623b39c43df42c934b1b4364d6477d940`,
`source_head=66ef622a43ab59512735ac78ce10d1250e26f9df`,
`source_tree_fingerprint=git-delta-v1:ad029851d6daceeff2ec767c44677a1c3a1e66fc4c125cd809e52e8cb749c485`.

Independent re-measurement identity: HEAD `dc39709c0c17a3272126c01a626ffcaa4176140b`,
tree `git-delta-v1:f3dab073ebbfbd9021d22a0e63c2cbba72094bb6ff587c16e670aa98bd38e1d7`,
measured 2026-11-17.

## Scenario 1 — rebind repair lifecycle: NOT REPRODUCIBLE at this identity

Package claim: `python -m unittest tools/test_rebind_repair_lifecycle.py`
→ 12/12 PASS.

Measured: `tools/test_rebind_repair_lifecycle.py` does not exist in HEAD, does
not exist in the worktree, and `git log --all` never carried it in a commit —
the only commit that contains the path is the stash commit `06fa9f073`
("index on main: 66ef622a"). Two byte-identical copies exist outside HEAD:

- `stash@{2}` ("On main: t2040-wip"), sha256
  `167616918fbdbe80d2e3c4d16e93681cc7cfe73f4b8d83d2a4c3dc410744763c`;
- `.saipen/evidence/T-2040/same-final-oracle-20261109T201201613243Z/snapshot/tools/test_rebind_repair_lifecycle.py`,
  same sha256.

Both copies contain the literal `ded-deadbeef` 11 times, and the current
declared family already reds on exactly that byte
(`test_style_contract_chokepoint.StaticChokepointTests.test_evidence_scripts_hardcode_no_marker`,
cached records under `.saipen/cache/core-unit/`). The copy belongs to T-2040's
parked work (reconciliation owner: T-2054); restoring it is outside this review
intake and would be a source change, not a review.

Verdict: the 12/12 claim cannot be re-derived from committed source. This is a
package-evidence gap, not a reproduced product defect, and no patch is applied
(the verify forbids package patches during intake).

## Scenario 2 — bootstrap / install identity: REPRODUCED

`python -m unittest tools/test_host_bootstrap.py tools/test_install_identity_doctor.py tools/test_t1854_runtime_home.py`

Result: `Ran 55 tests in 19.117s` — `OK (skipped=1)`. Matches the package's
55/55 PASS.

## Scenario 3 — core validator: CONTRADICTED, but by an owned condition

`python tools/validate.py` → `Validation FAILED: 31 problem(s), 39 warning(s)`.

All 31 problems are the single class "runtime manifest names a file git does not
track" — the 31 untracked `tools/` files of the pending 8.1.1 delivery blob
(`tools/saipen_engine/gc.py`, `persistent_goal.py`, `outcome_truth.py`,
`discovery_providers.py`, `source_reindex.py`, `tools/test_t2040_*.py`, …). No
problem is attributable to TEST-12's scenarios. The red is the release-surface
condition owned by T-2058/T-1449 (Gate A EX-000053 and the staging batch), not a
defect this package found or missed.

The package's "0 problems" held only at its own claimed source identity and is
not reproducible here for a separately-owned reason.

## Durable disposition record

E-20727 (07.11.26 14:13) already records the canonical disposition: "disposition
saitest/TEST-12 reviewed after Core review T-2039 terminal". The OUTBOX entry
that operation wrote was later lost from the worktree projection: the current
`saitest/kitchen/OUTBOX.md` carries TEST-1..TEST-11 and TEST-14..TEST-19 but no
TEST-12 or TEST-13, and `saipen sub dispose saitest TEST-12 --dry-run` answers
`PACKAGE_INCOMPLETE` ("no READY package to dispose"). The LOG event remains the
canonical record; the projection loss is noted, not repaired from this ticket.

## Core disposition

- Defect hypothesis: **NOT_REPRODUCED** — no product defect found in the
  scenarios that can be measured at `dc39709c`.
- Package evidentiary quality: **PARTIAL / STALE** — 1 of 3 scenarios
  reproducible, 1 unreproducible (target absent from source), 1 contradicted by
  a separately-owned release-surface red.
- Package patch: none. No tree change is made by this intake.
- Archive verdict: the reviewed hypothesis may be archived **with the
  qualification above**. That is an administrative acknowledgement of a
  completed zero-defect review, not a protected operator decision.

## Why the ticket cannot be closed in this generation

The BOARD row is `## BLOCKED` with head class `WAIT_USER_DECISION` ("awaiting
operator confirmation to archive"). Measured against the installed 8.1.0
engine, four canonical routes refuse with zero writes:

| route | measured answer |
| --- | --- |
| `saipen ticket unblock T-2039 "<decision>"` | `WAIT_USER_DECISION` — "unblocking requires verified operator authority or authentic proof" |
| `saipen claim T-2039 --dry-run` | `TICKET_NOT_WORKABLE` — "explicit priority override does not override authorization" |
| `saipen ticket done T-2039 --closure-mode finding_invalidated --invalidated-by E-20727 --dry-run` | `ILLEGAL_TICKET_LIFECYCLE` — "finish accepts only a ## DOING [/] ticket" |
| `saipen checkpoint DEC T-2039 "…" --dry-run` | `STALE_WORK_CONTEXT` — no active work context to bind |

`unblock` is the only verb that removes a `blocker` field, and its operator gate
accepts only a sealed `operator_origin` or the documented proof tokens. No sealed
origin exists in this project: every active host ingress record carries
`witness: model_supplied` (including this turn's `ing-4d400448026a05e2`), and
`.saipen/cache/ingress/` holds no `operator_origin`.

Conclusion: the review work the verify demands is complete and recorded here; the
remaining act is the administrative archive confirmation. The operator can settle
it in one of three ways:

1. deliver a sealed operator ingress for T-2039 (the engine then accepts
   `saipen ticket unblock T-2039 "<decision>"`), or
2. authorize the 8.1.1 generation that carries the current unblock/closure
   rules (T-2058 Gate A) and any generation-level review-closure route, or
3. record an explicit T-2039 archive decision in a receipt whose capsule grants
   it.

Until one of those exists, marking T-2039 DONE would mark blocked work DONE,
which the standing constraints forbid.

## The exact operator act (one message, no commands)

The installed generation's gate was re-read after this review
(`scheduled-source/tools/saipen_engine/operations.py`, unblock plan): it calls
`operator_task.witness(payload, root=root)` and admits either
`witness == "operator_carrier"` or an authenticated `operator_origin`. Both are
produced only by the host prompt boundary sealing the operator's own bytes, so
the whole remaining human act is one plain message typed in this ZAICODE
session:

```
T-2039 arhiivikinnitus: saitest/TEST-12 ülevaatus on lõpetatud, tootedefekti ei leitud; arhiveeri ilma täiendava kinnituseta.
```

Rules for that message, all load-bearing:

- Do not prefix it with any SAIPEN shortcut token (`cc`, `gg`, `sss`, …); the
  router would resolve it as a command before the engine sees a decision.
- It must be the whole message: the hook seals the message bytes, and the
  unblock payload must be those same bytes.
- The transport is degraded right now. `saipen host doctor` reports
  `authority.running: false`, `unanswered: "absent"`, so recent ingress records
  (including `ing-4d400448026a05e2`) are `witness: model_supplied` and the turn
  proceeds unsealed. If the message still arrives unsealed, the operator's own
  explicit repair is the one `tools/authority_service.py` attributes to them:
  `authority_service.py start --force`. Nothing on the agent side can or should
  perform it: a service the agent starts would be sealing the agent's own bytes.

Once that sealed message exists, closure is mechanical and stays in this
generation: `ticket unblock` → `claim` → transition `DOING` → re-run the two
reproducible scenarios → transition `SHIP` → ticket-bound `checkpoint DEC` with
the premise-invalidated finding → `ticket done --closure-mode
finding_invalidated --invalidated-by <that E-###>`. No patch, no publication
receipt, and no fabrication is involved at any step.
