# AUDAPACK — Cross-project contamination incident report (SAITULS QV-A+B)

Recorded 2026-09-13 by the repair session (buffy). Canonical SAIPEN LOG
journaling of this entry is BLOCKED by two pre-existing sealed-ledger defects
that the repair directive forbids rewriting: duplicate/out-of-order E-1347 and
the malformed event line at LOG.md:1159. STATE.md carries the summary; this
file carries the full evidence.

## Incident

On 2026-09-12 (15:37–15:45 +03:00) an Antigravity agent session was launched
with the AUDAPACK workspace (`V:\___VAC\__K\__CODE\_PY\_AUDAPACK`) as its
project root while carrying a SAITULS task ("Queue Viewer realtime arbitration
and send admission safety"). It wrote into AUDAPACK:

1. `.saipen/STATE.md` — overwritten with `task: SAITULS-QV-A+B`,
   `agent: antigravity`, `phase: VERIFY`, `last_event: 1349` (a misattribution:
   E-1349 is AUDAPACK's own buffy T-188 checkpoint at 13:40Z).
2. `scripts/saipatch/**` — six files, a "Target A / Target B" Queue Viewer
   refactor (PresentationArbiter, AdmissionGuard, QueueViewerCore).
3. `tests/test_queue_viewer.py`, `tests/test_saipatch_queue_core.py`.
4. `pytest.ini` — gained `pythonpath = .` to make `scripts.saipatch` imports
   resolvable from the repo root.

## Target A — contamination boundary (final classification)

| Path | Class | Basis |
|---|---|---|
| `.saipen/STATE.md` | FOREIGN_SAITULS (working tree) | Foreign task/agent; illegal SHIP→VERIFY transition bypassed engine; prior truth (HEAD, last_event 895) and mid-stream AUDAPACK truth (E-1349/E-1350) both AUDAPACK-owned |
| `.saipen/BOARD.md` | LEGITIMATE_AUDAPACK | Diff vs HEAD = T-188 claim + T-191/T-190 closures; all AUDAPACK history |
| `.saipen/LOG.md` | LEGITIMATE_AUDAPACK | 458 appended AUDAPACK event lines E-896..E-1350; no SAITULS-QV content |
| `.saipen/IDENTITY.md` | LEGITIMATE_AUDAPACK | lineage-79944d6c... unchanged |
| `scripts/saipatch/**` (6 files) | FOREIGN_SAITULS / ownership unproven | Module docstrings self-identify SAITULS; not present in authoritative SAITULS tree or _TEMP_SAITULS_RECOVERY/_SNAPSHOT |
| `tests/test_queue_viewer.py`, `tests/test_saipatch_queue_core.py` | FOREIGN_SAITULS | Import scripts.saipatch exclusively; SAITULS's own copies differ |
| `pytest.ini` `pythonpath = .` | FOREIGN (supporting change) | Added 2026-09-12 15:44:32, same window; reverted |
| BOARD/LOG SAITULS mentions (E-575, E-642, T-125, config.py, instances.py...) | LEGITIMATE_AUDAPACK | Long-standing AUDAPACK audit/instance-attribution history predating the incident |

## Target B — root cause (proven)

Evidence: Antigravity session transcript
`C:\Users\vac34\.gemini\antigravity\brain\8c3e1c1e-ee90-4f76-a792-89233730afc8\.system_generated\logs\transcript.jsonl`

- Step 0 (2026-09-12T12:37:15Z): USER_EXPLICIT input is the SAITULS
  Queue Viewer directive.
- Step 1–2: planner lists `V:\___VAC\__K\__CODE\_PY\_AUDAPACK` as "Project
  root" — the WRONG workspace for a SAITULS task.
- Step 3–4: reads `_AUDAPACK\.saipen\STATE.md` as "SAIPEN state".
- 15:39–15:45: writes saipatch files, QV tests, pytest.ini change, then
  STATE.md (15:44:55) — all inside AUDAPACK.

Causal path: the operator's SAITULS task was handed to an agent session whose
workspace/cwd was the AUDAPACK checkout; the session resolved "the project" by
cwd and wrote its SAIPEN state and task code relative to that cwd. No
project-identity check (AUDAPACK lineage-79944d6c… vs SAITULS
lineage-ded945ae…) guarded the state write, and the write bypassed the SAIPEN
engine entirely (SHIP→VERIFY is an illegal transition the engine refuses).

Root cause location: EXTERNAL to this repository — the agent session's
workspace selection / project-identity handling. Not repairable in AUDAPACK
without inventing a patch for another system, so it is recorded as the standing
blocker in STATE.md. Target E (local regression boundary) is therefore NOT
applied per the directive ("do not add speculative guards unrelated to the
proven cause").

## Target C — restored truth

- STATE.md restored to AUDAPACK semantics: `phase: DONE`, `task: none`,
  `agent: buffy`, canonical `WAIT: blocked -- ...` next_action, `last_event:
  1350` (the true ledger tail), `execution_intent: converge`.
- SAIPEN engine (`_SAIPEN/tools/saipen.py status`) now validates STATE clean;
  remaining refusals are ONLY the two pre-existing ledger defects:
  duplicate/out-of-order E-1347 and the malformed line at LOG.md:1159 —
  sealed history, deliberately not rewritten.
- T-188 remains open; no fabricated closure; SRC-044 + audit/10.md untouched
  and live.

## Target D — removal

- `scripts/saipatch/` (6 files), `tests/test_queue_viewer.py`,
  `tests/test_saipatch_queue_core.py` removed after byte preservation.
- Preservation: `V:\___VAC\__K\__CODE\_TEMP_SAITULS_QV_AB_PRESERVED_20260912`
  (SHA256SUMS.txt + README with full SHA-256 provenance).
- pytest.ini `pythonpath` line reverted via git checkout.
- Zero residual references (grep over audapack/tests/scripts/pytest.ini).

## Target F — gates (all green post-cleanup)

- `pytest tests/test_source_inventory.py tests/test_packing_git_inventory.py
  tests/test_packing.py tests/test_hidden_subprocess.py` → 114 passed, 1 skipped
- `pytest -q` full → 1639 passed, 5 skipped (prior 1659 − 20 foreign QV tests)
- `ruff check audapack tests scripts` → clean
- `compileall -q audapack scripts` → clean
- `node --test tests/widget/*.test.js` → 493 pass, 0 fail
- `.saipen/kitchen/regression_t158.py` → 4/4 PASS

Manual Windows smoke (SAIPEN PACK ×2, PACK ALL batch, zero console flash,
no foreign state creation) requires the operator's desktop session and remains
the standing acceptance step.
