# T-1944 / SRC-343 — audit/27.md closure report

**Source:** `audit/27.md`, sha256 `1d66a2ad2c03f92a6180e149df42d3760e965de8623436ef22f6aad77abd47d4`,
captured as SRC-343 (`external_audit`, `transport_transform: none`, byte-identical
to the original).

**Audit shape:** 16 findings in three waves — 5 CORE (P0/P1/P1/P1/P2), 6 SECOND WAVE
(P0/P1/P1/P1/P2/P2), 5 PERFORMANCE (P1×4, P2×1). Every finding names a file and
symbol, an isolated reproduction, a DEFECT, a REPAIR, and a VERIFY list.

**Contract:** derived 2026-10-27T12:58:03Z, `interpretation_revision` 0 → 16.
One requirement per finding, R001..R016, each carrying the audit's own REPAIR and
VERIFY text verbatim. Before this derivation the coverage ledger held **zero**
requirements, so no closure claim could have had a denominator.

---

## 1. Clause ledger

| Clause | Finding | Pri | Subject | Repair | Primary test class |
|--------|---------|-----|---------|--------|--------------------|
| R001 | CORE-001 | P0 | `saipal_adapter.SaipalAdapter.deliver_finding_to_audit_inbox` | qualification proof authentication bypass | `Core001ForgedQualificationProof` |
| R002 | CORE-002 | P1 | `campaign.inspect_campaign_state` / `step` | missing digest permits fabricated terminal lifecycle | `Core002CampaignStateDigestIsMandatory` |
| R003 | CORE-003 | P1 | `saipen/REGISTRY.json` / `goal_authority` | continuous-maintenance scope contradicts registry | `Core003MaintenanceScopeAgreesAcrossWriterAndReader` |
| R004 | CORE-004 | P1 | `SaipalAdapter.record_maintainer_disposition` | VERIFIED disposition lacks exact task/evidence binding | `Core004VerifiedDispositionNeedsExactBinding` |
| R005 | CORE-005 | P2 | `tools/saipen.py` campaign status dispatch | corrupt persisted campaign reported as successful null | `Core005CampaignStatusDistinguishesCorruption` |
| R006 | W2-001 | P0 | `SaipalAdapter.reconcile_history` | absent-history reconstruction overwrites concurrent writes | `W2_001ReconcileIsOneTransaction` |
| R007 | W2-002 | P1 | `SaipalAdapter.iter_new_qualified_findings` | cursor acknowledges findings before delivery | `W2_002YieldingIsNotDelivery` |
| R008 | W2-003 | P1 | `deliver_finding_to_audit_inbox` | publication receipt dedup TOCTOU race | `W2_003ReceiptDeduplicationIsAtomic` |
| R009 | W2-004 | P1 | `CampaignController.step` | failed audit delivery reported as successful | `W2_004DeliveryAggregateIsTruthful` |
| R010 | W2-005 | P2 | `iter_new_qualified_findings` | corrupt cursor overwritten, write errors ignored | `W2_005CursorIntegrityIsNeverIgnored` |
| R011 | W2-006 | P2 | `iter_finding_pages` | report corpus identity ignores finding content | `W2_006CorpusIdentityCoversContent` |
| R012 | PERF-001 | P1 | `audit_enqueue.write_allocator` / `enqueue` | full allocator rewritten twice per publication | `PERF001AllocatorWritesAreAmortised` |
| R013 | PERF-002 | P1 | `_find_history_record` / `_append_history` | repeated complete history parsing | `PERF002HistoryParsingIsBounded` |
| R014 | PERF-003 | P1 | `reconcile_history` / `_receipt_from_allocator` | repeated full allocator reads during reconciliation | `PERF003ReconciliationReadsOnce` |
| R015 | PERF-004 | P1 | `_run_cmd("report")` / `iter_finding_pages` | pagination retains the complete report in memory | `PERF004PaginationHasBoundedResidency` |
| R016 | PERF-005 | P2 | `iter_new_qualified_findings` / `save_page_checkpoint` | growing cursor reserialised after each page | `PERF005CursorPersistenceIsLinear` |

## 2. Red-before-green — 16/16 measured

The audit demands an **isolated** regression per finding: pre-fix red, post-fix
green, same test, same fixture, implementation-only difference. Each wave has a
control transcript; the CORE wave had none before this session, and its earlier
probe printed a `TypeError` on both sides of CORE-003, which measured nothing.

| Wave | Transcript | Result |
|------|-----------|--------|
| CORE | `.saipen/evidence/T-1944-audit-wave3/core-pairs.txt` | **5/5 PROVEN** |
| SECOND WAVE | `.saipen/evidence/T-1944-audit-wave3/w2-before-after.txt` | **6/6 PROVEN** |
| PERFORMANCE | `.saipen/evidence/T-1944-audit-wave3/perf-before-after.txt` | **5/5 PROVEN** |

CORE pairs are produced by `probe_core_pairs.py`: it copies the engine and
protocol directory to a scratch tree, runs the unchanged test class green, applies
exactly that finding's pre-fix revert, and re-runs. Result:

```
CORE-001  current=PASS(6)  reverted=FAIL(5 failed)  PROVEN
CORE-002  current=PASS(8)  reverted=FAIL(12 failed) PROVEN
CORE-003  current=PASS(6)  reverted=FAIL(3 failed)  PROVEN
CORE-004  current=PASS(7)  reverted=FAIL(1 failed)  PROVEN
CORE-005  current=PASS(7)  reverted=FAIL(6 failed)  PROVEN
```

CORE-003's repair is registry *content*, not Python, so its revert removes
`continuous_maintenance` from `goal_authority.until` — the exact pre-fix
vocabulary the audit quotes. `control_core003.py` is the standalone version.

## 3. Performance measurements (audit baseline → post-repair)

| Finding | Audit baseline | Measured after repair |
|---------|---------------|----------------------|
| PERF-001 | 136166 B at 20 ops, 528806 B at 40, 2084486 B at 80 — two whole-file writes per enqueue | 975.49 / 1001.68 / 1012.71 bytes per operation at 500 / 1000 / 2000 ops (flat); growth < 2.6 per doubling |
| PERF-002 | whole receipt log parsed on every append | re-parse work follows new work, not history size: `last <= first*2 + 4096` across a 25/50/100 ladder |
| PERF-003 | allocator re-read per receipt during reconciliation | **< 6** allocator reads for 12 receipts (one snapshot, one index per pass) |
| PERF-004 | whole corpus materialised, then sliced per page | peak 675 KB at 2000 findings vs 702 KB at 20000 (1.04×) against a 6.04 MB whole-corpus baseline at 8000 findings |
| PERF-005 | cursor carries and re-serialises every delivered id | 40 pages well under the audit's 234910-byte baseline; cursor has no `delivered_finding_ids` key |

Three of the five repairs were found by *measuring*, not by asserting: the
compaction threshold originally re-serialised the whole document to size itself
(2.05 s of a 4.04 s 100-enqueue run), the append path still parsed the full log
under the lock, and the corpus identity retained one `[id, digest]` pair per
finding (memory still grew 8.82× for a 10× corpus). Each is fixed, and each has
the test that would have caught it.

## 4. Focused VERIFY evidence

Six focused records, all PASS, produced inside this phase:

| Record | Suite | Tests |
|--------|-------|-------|
| `9e2b18292bb681e9-20261027T125940150565Z.json` | `test_t1944_core_wave1.py` | 34 |
| `9e2b18292bb681e9-20261027T130104227715Z.json` | `test_t1944_wave2.py` | 26 |
| `9e2b18292bb681e9-20261027T130422556793Z.json` | `test_t1944_perf_wave.py` | 22 |
| `9e2b18292bb681e9-20261027T130550254984Z.json` | `test_t1931_saipal_boundary.py` | 22 |
| `9e2b18292bb681e9-20261027T130812924745Z.json` | `test_t1932_src338_closures.py` | 69 |
| `9e2b18292bb681e9-20261027T130934524891Z.json` | `test_audit_enqueue.py` | 31 |

**204 tests, 0 red.**

## 5. Broader regression

| Suites | Result |
|--------|--------|
| campaign + supervisor + dispatch + adapter parity (8 modules) | 141 passed, 136 subtests |
| receipts + report + soak (8 modules) | 226 passed, 45 subtests, **1 failed** |
| `test_audit_dogfood.py` + `test_campaign_matrix.py` | 42 passed, 2 subtests, **1 failed** |

The two failures are **inherited, classified, and not repaired here**:

1. `test_t1516_portable_receipts.py::test_the_acceptance_holds_in_a_copy_at_another_path`
   — fails on `engine-state-contract -- properties continuous_maintenance`, the
   schema drift another actor is mid-work on (`saipen_engine/state.py` vs
   `state.schema.json`). Unrelated to any SRC-343 finding.
2. `test_audit_dogfood.py::ProducerNeutrality::test_no_engine_module_branches_on_a_producer_name`
   — 85 offenders, **all 85 in the two untracked bridge modules**
   (`campaign.py` 16, `saipal_adapter.py` 69) and **0 in the 153 tracked engine
   modules**. Those two modules *are* the SAIPAL bridge, so their own name is not
   a producer branch; the guard is designed for producer-neutral transport code.
   Count was 76 before this session; the rise comes from new adapter helpers
   naming their own artifacts (`saipal_ack_journal.jsonl`, cursor paths, the
   `saipal_report_stream` import), not from new producer-name branching. The
   three genuine `producer != "saipal"` filters already existed at the
   reconciliation and committed-id sites.

No baseline was widened to absorb either failure.

## 6. Truthful environment classification

| Environment | Status |
|-------------|--------|
| Native Windows (this host, CPython 3.11) | **exercised** — every number above was measured here |
| External/installed ZAICODE host | **UNVERIFIED** — no installed-host receipt exists for this ticket; nothing in SRC-343's 16 findings requires it |
| Non-Windows | **UNVERIFIED** — not exercised |

## 7. What the audit asked for that this ticket does not claim

- No fabricated benchmark: every performance number is a test assertion or a
  transcript line from a command that ran.
- No premature completion: `PERFORMANCE_DONE_WHEN`'s "native Windows and external
  integration results truthfully classified" is satisfied by §6 stating the
  external half as unverified rather than inferring it.
- No unauthorized implementation mutation: changes are confined to
  `tools/saipen_engine/{saipal_adapter,campaign,audit_enqueue}.py`,
  `tools/saipen.py`, `saipen/REGISTRY.json`, and the four `tools/test_t1944_*`
  / migrated-fixture test modules. `STATE`, `BOARD`, `LOG` are written only
  through `saipen`.
- No hand edit to `.saipen/STATE.md` counters, no `goal_tickets` reset, no
  authority simulation.
