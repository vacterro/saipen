# T-1959 / SRC-348 closure report

Agent-drift audit reconciliation, executed 2026-10-29.
CANONICAL SAIPEN HEAD: `66ef622a43ab59512735ac78ce10d1250e26f9df`.
Source: `audit/SAIHANDOFF_AGENT_DRIFT_20261029_2328.md`, sha256
`b907ad13b95eba7436dd367fb898f667e9f17ce2241cbacb3fc35624179f8b8c`, 9486 bytes.

## STATUS

COMPLETE for what the evidence permits, and PARTIAL exactly where the audit
said it must be. All nine actionable clauses carry a terminal disposition with
clause-specific evidence. Seven confirmed findings (F-01..F-07) were re-measured
against HEAD and are already remediated; the two findings the audit itself marks
UNPROVEN (F-08, F-09) are out of this repository and were left unproven rather
than converted into defects.

Full historical verification is **not** claimed. The audit's `MANDATORY
LIMITATION` says the capture declares 5096 messages and 18168 parts but contains
only messages 1-384 and ends mid-tool-output, and that the original 70777-byte
handoff appears only as a preview. That limitation was measured, not assumed
(see R008 below), and its `STOP CONDITION` -- "Missing complete evidence =>
PARTIAL, never fabricated forensic completeness" -- is the outcome recorded here.

## RESULT

### Finding matrix against HEAD 66ef622a

| Finding | Audit class | Measured on HEAD | Basis |
|---|---|---|---|
| F-01 initial route | HIGH confirmed | IMPLEMENTED + REGRESSED | BOOT routes new actionable input to START with START FIRST; the start transport carries file, hex and receipt forms. 9 tests. |
| F-02 self-certified coverage | CRITICAL confirmed | IMPLEMENTED + REGRESSED | Six refusal guards in disposition handling; two reproduced live this session. 34 tests. |
| F-03 workflow bypass | CRITICAL confirmed | IMPLEMENTED + REGRESSED | Read-only permitted under a blocked gate, mutation refused; CLI replay cannot renew bounded authority; broker refuses a replayed capability. 57 tests. |
| F-04 false domain completeness | CRITICAL confirmed | IMPLEMENTED + REGRESSED | Shard merge proves every occurrence exactly once; generic aggregate proof refused for live-acceptance clauses; per-clause derivation. 29 + 34 tests. |
| F-05 derived requirement provenance | HIGH confirmed | IMPLEMENTED | Three witness classes; only a carrier witness projects operator authority. 30 tests. |
| F-06 response contract | MEDIUM confirmed | IMPLEMENTED + REGRESSED | Read-only renderer/checker decides actual reply text; language bound to the session. 85 tests. |
| F-07 authenticated bridge | HIGH host limitation | FAIL-CLOSED | No proven candidate answers unavailable; an unregistered explicit host is never green; installed guard byte-identical to HEAD. 25 tests. |
| F-08 runtime projection | MEDIUM **UNPROVEN** | OUT OF REPOSITORY | The named counters are host snapshot fields; none exist in this engine. Audit marks it unproven; left unproven. |
| F-09 Qt teardown | LOW/MED **UNPROVEN** | OUT OF REPOSITORY | No Qt dependency here; the only PyQt/PySide mentions are applicability detection strings. Left unproven. |

Total AUTHENTICATED suite evidence in this ticket: **269** test executions
green across the eight focused records cited below, 0 red, all on one
fingerprint (`80573d5680492f06…`) that was verified equal to the live tree at
disposition time.

One earlier batch is deliberately NOT counted: an 84-test run
(`049e2290e0fcbdeb-20261029T231114439833Z.json`) whose individual tests were
all green but whose record verdict was FAIL, because a concurrently editing
session moved the tree and the whole-tree fingerprint no longer matched. Its
tests re-ran inside the authenticated 9 + 75 records above, so nothing is lost;
but a FAIL record is not evidence and is not counted as any. Saying "309" by
adding that batch to the 269 would have inflated authenticated evidence with an
unauthenticated run, which is precisely the defect class this audit is about.

### Clause dispositions (SRC-348 revision 9)

| Clause | Disposition | What proves it |
|---|---|---|
| R001 | VERIFIED | BOOT start-first route; start transport accepts file/hex/receipt and refuses when attachment transport is unavailable. `test_entry_answer_agrees.py`, 9 PASS. |
| R002 | VERIFIED | Terminal disposition needs evidence; implemented/verified needs verification; absent/unrelated/too-weak/partial evidence each refuse. `test_source_contract_derivation.py` + `test_cold_agent_truth.py`, 34 PASS. |
| R003 | VERIFIED | Read-only under block, mutation refused, RECONCILE_REAUTH_REQUIRED on bad authority/project/gate version, CLI replay cannot renew the budget, broker refuses replayed capability as blocking. `test_automation_block.py` + `test_capability_boundary.py` + `test_t1858_valve_guidance.py`, 57 PASS. |
| R004 | VERIFIED | Shard merge proves every discovered occurrence exactly once and persists the partition proof; records bound to a tree fingerprint and verification identity; generic aggregate proof refused. `test_t1472_core_unit_shards.py` + `test_t1837_ci_family_parity.py`, 29 PASS. |
| R005 | VERIFIED | Operator carrier / transport obligation / model supplied are distinct; only carrier projects operator authority; unwitnessed becomes model supplied without being a refusal. `test_operator_task_witness.py` + `test_ingress_authority.py`, 30 PASS. |
| R006 | VERIFIED | Read-only renderer/checker validates the actual reply; language bound via the running style contract; a format retry re-enters a pure validator with no tool dispatch. 85 PASS across two records. |
| R007 | VERIFIED | Authenticated host adapter test exists and stays fail-closed with no proven candidate or an unregistered explicit host. `test_host_bootstrap.py`, 25 PASS. Installed hook byte-identical to the committed blob. |
| R008 | VERIFIED | Declared 5096/18168/70777 compared against 384 messages in 9486 bytes; no 70777-byte file in the project tree, the host app-data tree or the host blob store. Full historical verification not claimed; absence never read as proof. |
| R009 | VERIFIED | Non-goal honoured: no reopened ticket, no push, no forged/replayed/bypassed credential, nonintrusive commands only. |

### Authenticated focused records

```
80573d5680492f06-20261029T231213077740Z.json   9   R001
80573d5680492f06-20261029T231405663501Z.json  34   R002
80573d5680492f06-20261029T231610291842Z.json  57   R003
80573d5680492f06-20261029T231810312380Z.json  29   R004
80573d5680492f06-20261029T232023474270Z.json  30   R005
80573d5680492f06-20261029T232223012982Z.json  66   R006 a
80573d5680492f06-20261029T232420223418Z.json  19   R006 b
80573d5680492f06-20261029T232658155652Z.json  25   R007
```

## VALIDATION

- Contract revision 9, 9 clauses derived from the audit body.
- Coverage: `actionable 9, terminal 9, dispositions {VERIFIED: 9}, unresolved []`.
- Every `VERIFIED` clause cites an authenticated focused receipt whose proven
  oracles include the test named in its verification text. The engine's own
  gate refused the first attempts (`EVIDENCE_UNAUTHENTICATED`) and a
  whole-tree fingerprint mismatch, so no clause closed on raw unittest output.
- Authenticated test executions: 269, across eight PASS records, 0 red.
- The audit inbox holds `audit/SAIHANDOFF_AGENT_DRIFT_20261029_2328.md` as
  SRC-348 bound to T-1959 with a matching sha256.

## BLOCKERS

None for this ticket's own scope.

Two standing hazards, neither caused by this work and neither touched:

1. A bare `saipen ship` resolves its release ticket from committed release
   evidence for the version and lands on an orphan T-1679 v8.1.0 continuation
   whose recorded scope names `tools/saipen_engine/lifecycle_authority.py` at a
   digest that no longer matches live bytes (live file is byte-identical to
   HEAD). That is a pre-existing project condition, not a defect introduced
   here, and it is not repaired by editing another session's file.
2. The working tree is being written by at least one other live session
   (tools files changed at 01:04 and 01:08 local during this ticket), which is
   why the whole-tree fingerprint check forced short, immediately-consumed runs.

## NEXT EXACT ACTION

Close T-1959 through the lifecycle (BUILD -> VERIFY -> REVIEW -> SHIP -> DONE)
citing this report, then close SRC-348.
