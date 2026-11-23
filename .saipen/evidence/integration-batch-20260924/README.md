# Post-soak integration batch — 2026-09-24

Why this exists: while the T-1446 24-hour field soak (PID 24736, started
2026-09-24T03:48:38Z) reads this checkout, main is frozen at 86878249. Twelve
tickets were built and verified in isolated worktrees under
`V:/_SAIPEN_WORK_/`. Nothing here is committed. XP-000001 showed that applied,
uncommitted work can vanish (T-1506), so every candidate is also kept here as
a binary patch taken with `git diff --cached --binary` against 86878249.

## Candidates

| Patch | Ticket | Phase at freeze | What it carries |
|---|---|---|---|
| t1503.patch | T-1503 | VERIFY | Markdown compaction of HABITS/IMPROVE/SAICRITIC, with the three improve-admission markers restored (E-9128) |
| t1492.patch | T-1492 | VERIFY | Warning-free compile, Ruff W605 |
| t1499.patch | T-1499 | VERIFY | Telegram turn-entry argv rendering |
| t1505.patch | T-1505 | VERIFY | Core-unit sandboxes: owner stamp, reclaim, stale sweep |
| t1451.patch | T-1451 | VERIFY | Cohort publication fixture against the release-scope contract |
| t1475.patch | T-1475 | VERIFY | Host hook payload detector; root-file-set names the writer |
| t1278.patch | T-1278 | VERIFY | Closure-commit contradiction guard and history scan |
| t1315.patch | T-1315 | VERIFY | Attribution fixture repair + fail-open fix in `_closure_identity` |
| t1299.patch | T-1299 | VERIFY | Semantic Contract comparator (restored from XP-000001) |
| t1300.patch | T-1300 | VERIFY | `saipen source reconcile` (restored from XP-000001) |
| t1487.patch | T-1487 | VERIFY | `saipen handoff`, actor_source, FOREIGN_LIVE names the handoff |
| t1494.patch | T-1494 | BLOCKED before VERIFY | Goal authority carriers (SRC-112); open item in its own blocker |

Verification-only tickets closed in the same batch, no patch: T-1477
(future_gate doc, untracked in main), T-1443, T-576, T-1303, T-1301.

## Order and the known conflicts

Apply to a clean 86878249 tree in this order with `git apply --3way`:

    t1503 t1492 t1499 t1505 t1451 t1475 t1278 t1315 t1299 t1300 t1487 t1494

- t1487 and t1494 carry their own copy of the T-1503 compaction: apply them
  with `--exclude=saipen/HABITS.md --exclude=saipen/IMPROVE.md
  --exclude=saipen/SAICRITIC.md`.
- t1278 and t1494: `--exclude=tools/validator_fail_sites.json`; regenerate
  the ledger once at the end (`python tools/fail_site_inventory.py --write`),
  then adjudicate the one new site (`[closure-contradiction]`) as
  INTENTIONALLY_NO_MUTATION_CASE with the reason used in t1278.patch. The
  t1475 site keeps its COVERED verdict through regeneration.
- `saipen/REGISTRY.json` `error_codes`: t1278, t1487 and t1494 each add one
  code at the head of the list. Keep all three: AUTHORITY_REQUIRED,
  CLOSURE_CONTRADICTION, HANDOFF_AUTHORITY_REQUIRED.
- `tools/test_source_receipts.py`: t1299 and t1300 both add a class before
  `if __name__`. Keep both (t1300 also brings the `_preserved` helper).

A dry run of exactly this sequence lives at `V:/_SAIPEN_WORK_/integration-dryrun`
(resolver: the session scratch `resolve_dryrun.py`). Result there: fail-site
ledger PASS 335, markdown 302405/307200, ruff clean, 369 focused tests OK.

## After applying on main

1. `python tools/core_unit.py baseline` — shrinks by the ids the batch fixes
   (22 in test_recovered_attribution, 1 in test_public_closure_cli).
2. `python tools/validate.py` and `python tools/audit_checks.py`.
3. Per ticket: `core_unit.py evidence T-###`, REVIEW, SHIP (local commit of
   that ticket's paths), `ticket done`.
