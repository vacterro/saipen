# T-2089 P0 — the three W2 defects, fixed and proven (2026-11-18)

The hyperlean handoff's P0 asked for exactly three defects in
`_agent_view_payload` (the W2 agent-view route). All three were reproduced
RED on the live tree, fixed in `tools/saipen.py`, and proven GREEN.

## RED → GREEN

Reproducer: `tools/regression_t2089/t2089_p0_repro.py` (kept beside the
existing t2089 oracle; same subject-loading pattern).

| Defect | RED observation | Fix |
|---|---|---|
| P0-A root_ticket_count | group[4] `root_ticket_count=1` while the group held 3 roots; groups 0–3 carried no count at all | count is measured at projection build for EVERY row (`root_ticket_count`, `dependent_count`) before detail collapse |
| P0-B byte budget | 4 kept appends × 1 MB text serialized to 12 000 545 B, `truncated=false` | per-string UTF-8 budgets (`_bounded_text`: 2048 B scalar fields, 240 B wait rows, 512 B causes, per-append 2048 B serialized cap), every cut reported via `byte_budget_exceeded` + digest + `full_value_ref` |
| P0-C input mutation | `conformance["receipt"] = slim_receipt` rewrote the caller's payload (first differing key: conformance_status) | every mutable `keep` value is deep-copied on the way in; all later projection edits touch only the copy |

## Stress and property proof

`tools/regression_t2089/t2089_p0_stress.py` — all green:

- 120 / 2 000 / 10 000 blocker groups, plain and adversarial (5 KB causes,
  9 KB wait strings and appends): serialized agent view never exceeds the
  32 KiB hard budget;
- group counts 1–20 randomized: `blocker_group_count`,
  `blocker_ticket_count`, per-row `root_ticket_count` and
  `dependent_count` match the canonical full projection every time;
- 40-trial mutation sweep: input payload byte-identical after view
  construction; agent view is idempotent over the same input
  (full → agent → full unchanged);
- truncation honesty: 3 small groups → `truncated=false`; 30 groups →
  `truncated=true`.

`_cap_digest` now digests bounded-text marker dicts too (the RED P0-B run
crashed on `TypeError: sequence item 0: expected str instance, dict found`
before this).

## Parity on the live project (read-only)

Full vs agent, same tree, same run:

- exit code parity: 0 = 0;
- authority fields (`ok`, `code`, `recovery_pending`,
  `recovery_conflict`, `pending_ops`, `conflict_ops`, `operator_gates`,
  `phase`, `task`) — no diffs;
- size: full 414 815 B, agent 26 299 B (−94%), latency 8.02 s vs 8.25 s —
  output improvement only, honestly NOT an execution improvement.

Top agent-view keys by size after bounding: `waiting_on_you` 4 847 B,
`blocker_groups` 3 681 B, `source_drift` 2 417 B, `distribution` 1 964 B,
`cold_route` 1 791 B.

## P1 honest conclusion (dependency profiling, no code change made)

cProfile over `_status()` (the 8 s wall):

- `convergence_verdict` → `semantic_receipt_snapshot` →
  `_scan_receipt_namespace`: 4.78 s cumulative; 91 487 `nt.lstat` calls
  under `_receipt_namespace_entries` (20 268 calls over two scans);
- `distribution_report`: 2.08 s (61 `runtime_generation_identity` calls
  underneath — the memoized path already collapses 61 lookups to 10 real
  hashes, the falsified P4 hypothesis stays falsified);
- `closed_contracts.inspect` 0.82 s, `record_memo` 0.85 s, snapshot capture
  0.65 s.

The agent route today computes the FULL projection and only then bounds
the rendering (`saipen.py`: `if view == "agent": _emit(...)` runs after
every gate). A 2 s decision-status therefore requires splitting
decision-critical computation from diagnostic projection (handoff P1-A) —
that is a contract change to which stages a verdict may skip, not a
rendering change, and no such change was made this shift. Measured floor
with everything on: ~8 s. No fake speedup is claimed.

## Regression sweep after the fix

- t2089 agent-view 4/4, lazy entrypoints 4/4, oracle mutation-chain OK;
- t1734 15/15; t1944 22/22; t1836 25/25; continue_chain 6/6;
- t2087 drift anchors 4/5: the one FAIL
  (`E2AdmissionLatency::test_user_messages_admitted_only_as_late_paraphrase`)
  was proven pre-existing by stashing my edits and re-running at HEAD —
  same 1 failed / 4 passed. It is the known E2 ingress-debt owner
  (handoff P5), not a regression from this work.

## Files changed this shift (repo worktree, uncommitted like the rest of T-2089)

- `tools/saipen.py`: `_agent_view_payload` P0-A/B/C fix (~18 lines of the
  539-line worktree diff are this shift's; the rest is prior shifts'
  uncommitted T-2089 work, HEAD's `tools/saipen.py` contains no
  `_agent_view_payload` at all);
- `tools/validate.py`: EXEMPT row for `tools/regression_*/**/*.md`;
- new: `tools/regression_t2089/t2089_p0_repro.py`,
  `tools/regression_t2089/t2089_p0_stress.py`.

## Post-fix validator state (honest baseline)

After the P0 fixes moved the source-tree fingerprint, T-2047's reverify
receipt (RV-000093) was re-minted so the closure proof binds the CURRENT
tree: RV-000094, verdict PASS_WITH_CARRIED_DEBT, executed
(`python -m unittest tools.test_t1430_crew_run_receipt -v`, 5 tests OK).
Repo validator now reads 40 problems / 40 warnings and every one of the 40
FAILs is the publication-debt family `runtime manifest names a file git does
not track` (38 prior-shift untracked tools members + this shift's two new
regression files) — zero closure-evidence, zero coverage-gap, zero
other-class findings. The repair for all 40 is `git commit`, which is the
T-2058 operator publication cycle, not engine work.
