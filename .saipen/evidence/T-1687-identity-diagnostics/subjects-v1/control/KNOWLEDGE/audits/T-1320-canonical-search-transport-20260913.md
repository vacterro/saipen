# T-1320 — Canonical bounded search transport (fleet-wide search deadlock)

Date: 2026-09-13
Generation published: `T-1317-opencode-active-generation-20260913.5`
Guard SHA-256 (source == installed == loaded): `922ef4a307db4cd423170f4bd4b5b7595601d8636907ea67ba0177e14c7cb96e`

## 1. RIPGREP ROOT CAUSE — `OPEN_CODE_TOOL_FAILURE`

`ripgrep execution failed` exists **only inside the OpenCode binary**; `grep -rn -i ripgrep saipen/ tools/` finds nothing.
It is that program's ripgrep FileSystem service catch-all: every failure inside the scoped effect that is not already a
`Ripgrep.Error` is mapped to one generic string, so the real defect is **swallowed** and the operator sees only the
generic message.

Measured on this host:

- `rg` was **absent from the persistent PATH** (`reg query HKCU\Environment` carries no manicode entry).
- OpenCode's own bin held **only the ripgrep archive with no `rg.exe` beside it** — the stranded state the service
  leaves when extraction throws before its cleanup.
- `@ff-labs` (alternative native finder) is **not installed**, so `grep`/`glob`/`find` all go through the ripgrep layer.
- `opencode debug skill` lists `saipen` successfully with rg absent → skill **discovery** is fine; the fault is the
  agent's host search tool.

Failure owner: **OpenCode**, not SAIPEN. SAIPEN must not pretend it can repair another program's internals; it must
stop making mandatory work depend on either the host search layer **or** generic shell admission.

## 2. THE DEADLOCK, AND WHY IT WAS A DEADLOCK

Operator evidence (PROBLIP): native `Grep` failed with the generic string; the worker reached for the deterministic
shell fallback (`grep -n "CommitSnapshot|..."`); the guard **correctly** refused it (`PROTOCOL_STATE_INVALID`) because
the protocol state was invalid. Native search broken **and** shell fallback blocked — and the only surface the guard
still admits as canonical (`saipen`) had no search verb at all.

## 3. THE TRANSPORT

- Executable owner: `tools/saipen_engine/search.py` (pure `pathlib`/`re`/`os`; **no subprocess of any kind**).
- Reachable surface: **`saipen search`**, added to `SAIPEN_CLI_VERBS` (`tools/saipen_engine/admission.py`), so the
  guard classifies it as a canonical operation and admits it **even while protocol state is invalid**.
- Normative owner: `saipen/BOOT.md` step 14 (kernel contract). `saipen/SKILL.md` references it; `saipen/COMMANDS.md`
  and `saipen/REGISTRY.json` declare it.

**Hex-encoded free text is deliberate, not a workaround.** The guard's canonical argument alphabet excludes shell
metacharacters by design (`_SAIPEN_ARG_CHARS`, `_SHELL_SYNTAX_CHARS`), and a real query like
`CommitSnapshot|FlushSyncUnderGate` is mostly shell metacharacters. Hex also makes the query shell-agnostic: PowerShell,
cmd and bash cannot reinterpret `542d303031` as a pipe, quote or variable. No guard weakening was needed.

## 4. FAST PATH / FALLBACK CONTRACT

| host result | action |
|---|---|
| native search healthy | use it (unchanged fast path) |
| native **zero matches** | a normal empty result — **no** fallback retry |
| native transport/exec error | `saipen search` (bounded, read-only, no shell) |
| invalid regex / bad path | precise caller error, never silently reinterpreted |

## 5. RESULT BOUNDING

`max_files` 4000, `max_matches` 200, `max_result_bytes` 64 KiB, `max_file_bytes` 1 MB, `max_per_file` 20, fixed
excerpt width. Limits hit → `status: TRUNCATED` with explicit `truncation_reasons` and counters; results are never
presented as exhaustive. `SKIP_DIRS` keeps the walk cheap and deterministic. `UNAVAILABLE` is the honest terminal
state for a bound root that is gone; `PATH_OUTSIDE_ROOT` refuses any scope escaping the bound root.

## 6. RECOVERY-STATE SEARCH (the property the deadlock lacked)

Proven on a real malformed bound project with ripgrep removed from PATH and from OpenCode's bin:

```
[powershell] rc=0 match=True   engine: FALLBACK  status: OK  native: UNKNOWN   src/engine.py:1 …
[cmd]        rc=0 match=True   engine: FALLBACK  status: OK  native: UNKNOWN   src/engine.py:1 …
[bash]       rc=0 match=True   engine: FALLBACK  status: OK  native: UNKNOWN   src/engine.py:1 …
[status]     rc=1 (truthful malformed refusal) but cold_route PRESENT
[recover]    rc=0: code: REPAIRED   → phase: BUILD
```

Probe: `.saipen/kitchen/search_transport_probe.py`.

## 7. LIVE OPENCODE PROOF (fresh process, real model, real guard)

`SAIPEN_LIVE_OPENCODE=1 PYTHONPATH=tools python -m unittest tools.test_opencode_live_session -v` → **9 tests OK in
65.6 s**. The new control (`test_9`) drives the transport through the model in the post-recovery session:

```
command : saipen search --hex 542d303031 --max-matches 3
status  : completed            (no SAIPEN_GUARD_REFUSAL, no "ripgrep execution failed")
output  : engine: FALLBACK  status: TRUNCATED  native: UNKNOWN
          matches: 3 (4 file(s) scanned of 4 considered)  TRUNCATED: max_matches
          .saipen/BOARD.md:2: - [/] T-001 [P1] fix | verify: test
          .saipen/LOG.md:3: …
          .saipen/STATE.md:3: task: T-001
```

The same run also proves generation identity (`source == installed == loaded == 922ef4a3…`, BUILD_ID `.5`) and keeps
T-1318's recovery AC-05 green (`test_7`).

## 8. SESSION DEGRADATION MEMORY

`saipen search --native-failed` records `DEGRADED` for the session (a marker keyed on the bound root, in the **system
temp dir** — vendor/runtime detail never enters canonical STATE) and the result carries `native_search:
AVAILABLE|DEGRADED|UNKNOWN`. One proven-broken transport must not become fifty identical failing tool calls.

## 9. FOCUSED TEST EVIDENCE

| suite | result |
|---|---|
| `tools.test_search_transport` (new) | **26 PASS** |
| `tools.test_boot_locator` | 10 PASS |
| `tools.test_reconcile_valve` (with `PYTHONPATH=tools`) | 32 PASS |
| `tools.test_guard_events` | 23 PASS |
| `tools.test_guard_admission` | 12 PASS |
| `tools.test_guard_hostile_matrix` | 41 PASS |
| `tools.test_adaptive_runtime` | 29 PASS |
| `tools.test_opencode_host_smoke` (generation gate) | 7 PASS |
| `tools.test_opencode_live_session` (live) | 9 PASS |
| `tools.test_command_routing` | 61 PASS / **1 pre-existing FAIL** (`gg` goal-pivot: `T-11 has no [T-###] allocation event` — historical fixture debt, unrelated to this patch) |
| Ruff (touched files) | clean |
| compileall (touched files) | clean |

## 10. DOC / STATE CHANGES

- `saipen/REGISTRY.json` — `search` added to the closed command surface.
- `saipen/COMMANDS.md` — `saipen search <pattern>` row.
- `saipen/BOOT.md` — search-transport contract (zero matches ≠ failure; never fall back to `grep`/`bash`).
- `saipen/SKILL.md` — cold-start reference to the transport.
- `_cold_route` now survives a **malformed** checkpoint: the locator still names the route (two anchored regexes over a
  bounded head of the raw STATE text), because a malformed project is exactly when recovery must be found without the
  host search layer.

## 11. RESIDUAL RISKS

- The host transport is still broken and still swallows its own root cause; SAIPEN's fallback removes the deadlock but
  cannot make `Grep`/`Glob` work. `SEARCH_NATIVE` therefore reads `DEGRADED`/`UNKNOWN` until the host provisions rg.
- Already-open OpenCode windows keep generation `.4` resident until restarted; the generation gate reports exactly that.
- `tools.test_command_routing::test_gg_new_goal_is_create_pivot_not_resume` remains a pre-existing failure and was left
  untouched (out of scope: unrelated historical fixture debt).
- Fallback search is deliberately **not** an ignore-rule engine: it skips a fixed directory set, so a query can match
  generated/vendored files that a configure-aware ripgrep would exclude. Callers bound the query with `--scope`/`--include`.
