# T-1704: isolated checkpoint/audit parity repair

The mission is not complete. A concrete repair for the T-1703 audit-route
contradiction is implemented and tested in an isolated source copy, packaged
as `repair.patch`, and checked for applicability to the live working tree.
It has not been applied to the live project. The current legacy goal still
has no persistent grant, and its actual continuation still refuses with
`RECONCILE_REAUTH_REQUIRED`. Repeating the user's approval is not the missing
piece: the host must transport genuine operator provenance through the existing
ingress mechanism. The agent did not manufacture that provenance.

## Root cause and mechanism reused

The router's `state.binding_brake` gives a genuine safety-valve WAIT priority
over active Work and ordinary audit ingestion. The native validator called
`audit_route.route_violation` without canonical state or counter evidence;
that predicate accepted only the audit action or literal active-ticket PHASE
continuation. Consequently the legal T-1703 REVIEW boundary at 0 waves and
20 verified tickets was CURRENT_FAIL. The captured counterexample is retained
as `tests/fixtures/t1703-valve-audit.json` in the draft and patch.

The repair extends the existing binding-brake/audit-route owners. A new shared
`goal_valve_wait_is_proven` predicate requires goal intent, strict nonnegative
integer counts, a tripped existing cap, exact canonical WAIT wording, and
equality with counters reconstructed from canonical history. An arbitrary
WAIT, fabricated STATE cap, absent history, mismatched action, scope-selection
WAIT, numeric string or Boolean does not earn the exception. Genuine user,
destructive, external and BLOCKED brakes retain their priority.

Native validation supplies its existing canonical HistorySnapshot to this
decision. Persistent checkpoint routing and `reauthorize_valve` use the same
counter proof. The existing reset operation also checks active ownership and
journals a structured safety-review record with original authority source,
phase/task, base event and old/new counters. Its existing frozen snapshot,
grant proof, writer lock, journal and compare-and-swap preconditions remain
the commit mechanism. No checkpoint becomes a new operator grant.

SRC-112/T-1494 remains the sole persistent authorization system. No quartet
value, enum or grant proof was changed, no maintainer/path exception was added,
and no old receipt was upgraded. Active-ticket-first and subsequent audit
priority remain in the existing router; no audit is consumed by this repair.

## Exact source changes

These seven paths are modified/added only in
`V:\_TEMP_\saipen-t1704-draft-43c_1k2f\subject` and the portable patch:

| Path | Change |
| --- | --- |
| `tools/saipen_engine/state.py` | Shared canonical valve/counter proof. |
| `tools/saipen_engine/audit_route.py` | Consume the existing binding brake and require counter proof for valve WAIT. |
| `tools/saipen_engine/router.py` | Prove earned counters before persistent checkpoint admission. |
| `tools/saipen_engine/operations.py` | Checkpoint counter/ownership guard and durable review metadata. |
| `tools/validate.py` | Supply frozen canonical state/history to audit-route validation. |
| `tools/test_t1704_goal_checkpoint_priority.py` | 24 focused regression tests. |
| `tests/fixtures/t1703-valve-audit.json` | Captured live T-1703 counterexample and controls. |

`package.json` records exact before/after SHA-256 values. `repair.patch` SHA-256:
`17a3c7e467021aea3c73546b073180dfc2135828cc903c5ed87921ecc83dbca9`.
`git apply --check --whitespace=error <repair.patch>` exited 0, empty output.
This check did not apply the patch, stage changes or alter Git history.

## Red/green verification

Exact executable for these runs:
`C:\Users\vac34\AppData\Local\Programs\Python\Python311\python.EXE`.
The working directory was the isolated subject above. `verify_pair.py` restored
the five original implementation files for RED, kept the test and fixture
bytes frozen, and restored the proposed implementation in a `finally` block
before GREEN. No production file in the live root was swapped.

RED command:

```text
python -B -m unittest tools.test_t1704_goal_checkpoint_priority
```

RED: 24 tests, 12 failures, exit 1, 7.147219 seconds. Complete test ids and
streams are in `red-frozen.json` and `red-frozen.stderr.txt`. Subject content
fingerprint before/after:
`6b76af2a39d8a11eed511c88d917a20b84d66ec10a056178abbc0d2c480b8bc1`.
The failures include the captured REVIEW valve, native bounded and persistent
audit cases, genuine higher-priority brakes, and an unearned checkpoint cap.

GREEN command:

```text
python -B -m unittest tools.test_t1704_goal_checkpoint_priority tools.test_t1494_continuation_authority tools.test_t1293_valve_resume_audit_route tools.test_audit_route tools.test_reconcile_valve tools.test_command_routing tools.test_t1619_iteration_boundary
```

GREEN: 184 tests, 0 failures, exit 0, 73.173331 seconds. The unittest stream
reports 72.890 seconds. `green-frozen.json` and `green-frozen.stderr.txt` hold
the complete results. Subject fingerprint before/after:
`4e198213e476980f0ad386106336a3aff44cace5f196bfa9d6bfca18dc9cc24a`.
The identical oracle hashes are in `pair.json`; no assertion was changed
between this final RED and GREEN pair. Earlier exploratory runs, an import
harness error and the corrected synthetic REVIEW fixture are retained under
their original labels, not substituted for these frozen results.

Ruff checked all five proposed implementation files and the new test file:
exit 0, `All checks passed!`; exact argv is in `lint-final.json`.

The 24 new tests cover canonical bounded valve waits at 20 tickets/3 waves,
overrun accounting, fake or missing counter evidence, genuine higher-priority
brakes, scope-selection refusal, unchanged audit projection, active continuation,
native validator agreement, persistent 20-ticket/3-wave continuation, phase
preservation, bounded refusal, checkpoint replay/count reconstruction, and a
native owned T-1703 REVIEW fixture. Existing SRC-112 and iteration tests are
included in the 184-test result; this is a focused family, not full acceptance.

No declared full core-unit discovery was run for this draft. The historical
T-1703 6027/0/0 record E-14215 remains historical and cannot make the current
native result PASS. The requested legacy conversion, corrupt/missing journal,
concurrent writer, revocation, physical host restart and complete 22-category
acceptance matrix have not been newly demonstrated by this draft. No overall
PASS, REVIEW PASS, SHIP or DONE is claimed.

## Live native validation and preserved position

The live root remains
`V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`, branch `main`, HEAD
`025bf596c683464788ab698248e8a3c5eb44dfec`, with its pre-existing dirty tree.
T-1704 is the independent TODO correction linked to model-supplied SRC-206;
T-1703 remains DOING, owner and execution agent `saipen-cli`.

Canonical evidence checkpoint E-14221 committed through operation
`checkpoint-fb99aab251a944a0b2e2343095e12fa7`, exit 0. It appended evidence and
refreshed the same claim through SAIOPS. `position-final.json` proves the
preserved task T-1703, phase REVIEW, transition_from VERIFY, blocker none,
execution_intent goal, counters 0/20 and exact original valve WAIT. No persistent
quartet is present. Counter history and all original Work evidence remain.

The exact live native command was:

```text
python V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\tools\saipen.py validate --json
```

It exited 1 after E-14221: **CURRENT_FAIL**, structural gate pass,
one problem and nine inherited warnings. Receipt `receipt-fd5891e15952`,
timestamp `2026-10-10T08:48:07.357475Z`, finding key `76b48f23558dce11`,
detail hash `4a030409eccb2929`. The problem remains the bounded valve/audit
conflict, currently naming `audit/SAIPEN_20261010_1123.md`.
Install fingerprint:
`install-v1:5fab9f634a8fdd6eada7f89f3345c32880b8c6f9eab338b7b8f6213468a80ce3`.
Native source fingerprint:
`git-delta-v1:34be14d4d2f352d22c86df7593c41f33da7bbb5f22e5996cecc55b45a1e37476`.
The complete structured result, warnings and exact argv are in `native-final.json`.
Native passes inside disposable test projects do not relabel this live FAIL.

The source copy was initially verified against live content fingerprint
`8ee00e71000df4229d62cd7b82b8dca2ff54d6a3e7eb6021495994bcec5e967a`.
During the paired run the live full-content fingerprint changed to
`314699cb53e099686709efa1c2d33f1dbcd632a9c684b4d9e25283d207d94705`.
`source-differences.json` records a newly arrived
`audit/SAIPEN_20261010_1136.md` plus only the seven intended subject differences
at that observation. The three live canonical SHA values stayed identical
through RED/GREEN; `live_root_modified: true` correctly reports the source
drift, not an admitted patch. A later live observation during finalization is
retained in `position-final.json`. These are different fingerprint algorithms
and observation times; they must not be conflated into a claim of tree identity.
Pending audit files were not edited, deleted, ingested or reordered by this work.

## Authority, remaining blockers and next action

The installed Codex configuration exposes only a Stop hook, not an operator
turn-ingress witness. Host entry proves the executable transport and project
lineage, not operator provenance. Current native continuation was attempted
and refused `RECONCILE_REAUTH_REQUIRED`, changed_files `[]`, reconciliation
CLEAN. No pending operation recovery supplies the missing grant.

The existing proof model cannot legally upgrade a bounded pivot in place.
`LEGACY-TRANSITION-DESIGN.md` specifies a narrowly scoped canonical transition
under the existing proof/journal owners. It is explicitly a proposal, not a
supported command, committed grant or implementation. Fresh operator ingress,
that transition's implementation and its safety/replay/crash tests remain
required before the live goal can acquire persistence. Its counter reset must
then use the existing checkpoint operation, not hand-edited STATE.

T-1703 independent REVIEW and SHIP/DONE remain pending. Parent T-1702 and all
SRC-205 slices stay open. T-1494 stays DONE; T-1493 remains
SUPERSEDED_PENDING:T-1494 until the existing supersession contract is legally
admissible. No deployment, pilot, account-isolation or publication gate changed.

Exact next executable canonical action for the current agent: **NONE**.
The host-side prerequisite is a genuine carrier for the authorization already
given by the operator; another synthetic `cc`, copied instruction or stronger
retry of SRC-206 is not that carrier. After lawful admission, the owning Work
can apply/recheck this exact patch, implement and verify the legacy transition,
complete the remaining requested gates and restore T-1703's exact REVIEW phase.

The existing response gate also requires the handback to equal its machine
digest. A compact evidence-linked handback failed that equivalence check;
`final-response-check.json` retains the refusal and canonical replacement.
The replacement still says `run 'cc'`, which does not establish the absent host
carrier. The requested authority diagnostics/UX therefore also remain open;
the generic final digest must not be interpreted as successful authorization
or as proof that another model invocation can clear this boundary.

Graph evidence was Tier 2, project `saipen`, generation
`2026-09-01T13:16:39Z`. Structural discovery found no relevant code nodes;
coverage explicitly excludes `tools/`, and protocol/adapter metadata changed.
Those sources were read directly. No completeness claim relies on the graph.

## Evidence files and side effects

This directory contains the exact steering text, preparation and verification
helpers, isolated subject location, raw exploratory and frozen test streams,
pair hashes, lint/applicability records, patch, design and this report.
`finalize.py` records the only new canonical mutation in this turn, E-14221;
native validation separately writes its conformance receipt. The installed
hooks, operator environment, broker/services, canonical intake witness, goal
authority and live production/test files were not changed by these helpers.
The source copy's canonical documents are immutable test input, not a grant
or a cloned maintenance mission.
