# Structural gates measured on 2026-11-17 (crew identity, host authority)

Measured while auditing why the autonomous circuit cannot progress without an
operator act. HEAD `dc39709c0c17a3272126c01a626ffcaa4176140b`.

## 1. The crew source identity excludes `.saipen`

`tools/freshness.py::compute_source_identity` returns, for this root:

```
source_head              dc39709c0c17a3272126c01a626ffcaa4176140b
source_tree_fingerprint  git-delta-v1:0f69fe84ecb98bfc84e2c33be0bb35ef7310de8bbd75c223f7d6b77232be14d2
discovery_model          git-delta-v1
```

This is exactly the identity the live crew plan carries for SC-2, so the plan
reads a current tree.

`_git_delta_listing` passes the `.saipen` boundary to both Git calls as an
exclusion (T-1900, SRC-318; the boundary is `_is_saipen_path`, so
`.saipenicious.py` and `.saipen-src/` remain ordinary source). The listing
therefore covers tracked and untracked project paths **outside** `.saipen`
only — including the foreign pre-staged paths of T-1816/T-1817.

**Measured, correcting an earlier hypothesis:** writing this file under
`.saipen/evidence/` did not move the identity — it stays `0f69fe84…` before
and after. `.saipen` writes (evidence, LOG/STATE, kitchen packages, crew
receipts) do not re-stale a crew binding. Only a write outside `.saipen`
does.

## 2. The live crew plan

```
saipen crew --json
  code            CREW_ACTION
  first_unsatisfied  SC-2
  requires_human  false
  next            RUN_ROLE (saihunt)
  execute_in_current_agent  true
  liveness        CREW_STALLED, stall_repeats 3,
                  "do not poll" — the same actionable state returned
                  again with no qualifying state change
```

SC-2 asks for "current source-bound independent role evidence bound to THIS
crew epoch" at `0f69fe84…`: a complete strict OUTBOX package plus a committed
`crew_run` receipt binding the epoch.

Because `.saipen` writes are identity-neutral, this is reachable: write the
role package first, then record the run while the identity is still
`0f69fe84…`. Nothing those writes do can invalidate the binding.

## 3. Host authority transport from an agent process

```
python scheduled-source/tools/authority_service.py status --json
  code      BROKER_UNREACHABLE
  detail    "no host-authority broker answered; the prompt boundary starts it
             automatically when the asking process is the host application's
             own hook"
  policy    mode degraded, source operator (C:\Users\vac34\.saipen\authority.json)
  endpoint  \\.\pipe\saipen-authority-336850628174a20c242c9247
```

`C:\Users\vac34\.saipen\authority.json` contains only
`{"mode": "degraded", "set_by": "operator"}` — it names no host. The
`host_images` list in the status output (`claude.exe`, `claude-code`, …) is
the installed service's default host resolution, not an operator setting.

Therefore: no agent-run command can start the broker or seal an origin. Only a
message typed by the operator at a ZAICODE prompt can, because that is the
host's own hook invocation. If the prompt still arrives unsealed, the
operator's own repair surface is `tools/authority_service.py start --force` —
an agent must not run it (it would seal the agent's own bytes).

## 4. What this leaves for the autonomous side

- The crew RUN_ROLE path is feasible without a human and is the one live
  execution route; it is being worked.
- Review intake closure, T-2062's dependency release, and release-named
  closure still need either a sealed operator ingress or the Gate A install
  (EX-000053).
