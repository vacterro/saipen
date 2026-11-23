# T-1425 — host binding / auto-rebind / FreeBuff acceptance evidence

Date: 2026-09-20. Ticket: T-1425. Sources: SRC-079 (one-line task + handoff
path), SRC-080 (full handoff body, `external_audit`).

## 1. Repairs implemented and proved in-repo

| Repair | Where | Proof |
|---|---|---|
| 1 — bootstrap/admission consistency + automatic rebind | `tools/saipen_engine/host_bootstrap.py`, `tools/saipen_engine/operations.py` (`rebind_home_auto`, `HOST_BINDING_CONVERGED`), `tools/saipen.py` (`_converge_home_binding` in `cc`/`start`/`user-request`; `rebind-home --auto`) | `tools/test_host_bootstrap.py` tests 04b/13/20/21/22/23 |
| 2 — unknown explicit host fails closed | `host_bootstrap.resolve_bootstrap` / `_finalize_host` (`HOST_UNSUPPORTED`, `ok:false`, boundary `host_registry`, `runtime_discovered` kept separate) | tests 06 and 10 (CLI exit != 0) |
| 3 — `saipen host activation` argument contract | `tools/saipen.py` `_host_command`: asks the managed PROJECT root, never the install home | tests 11 (installed home without `.saipen/`) and 12 |
| 4 — launcher vs transport truth | `host_bootstrap._launcher` (`discovered`/`executable`/`transport`, no bridge claim) | test 07 red+green |
| 5 — FreeBuff activation delivery proved; no engine-shortcut substitution | `tools/test_host_bootstrap.py` `ActivationDeliveryTests` (byte-exact UTF-8 block on the FreeBuff surface); bundle evidence in section 3 | test 30 |
| 6 — live FreeBuff `cc` acceptance | bounded probes in `V:\_TEMP_\opencode\t1425-freebuff-live\` (artifacts copied into this directory when writable) | EXTERNALLY_BLOCKED — section 4 |
| 7 — single-verdict tests / filesystem fixtures | `tools/test_host_bootstrap.py` rewritten (22 tests); carrier-leak harness repairs in `test_hostile_wave_regressions.py` and `test_session_binding.py` (`isolate_host_session`) | focused suite + named regression families |

## 2. Required regression results (run 2026-09-20, this worktree)

| Family | Result |
|---|---|
| `tools/test_host_bootstrap.py` (focused acceptance) | 22 tests OK |
| `tools/test_runtime_bootstrap.py` | 23 OK |
| `tools/test_guard_admission.py` | 15 OK |
| `tools/test_guard_hostile_matrix.py` | 43 OK |
| `tools/test_native_host_guard.py` | 3 OK |
| `tools/test_host_launch_net.py` | 5 OK |
| `tools/test_opencode_bound_launch_smoke.py` | 4 OK |
| `tools/test_opencode_host_smoke.py` | 48 OK |
| `tools/test_hostile_wave_regressions.py` | 11 OK (harness now isolates host carriers) |
| `tools/test_session_binding.py` | 17 OK (harness now isolates host carriers) |
| `tools/test_project_root_session_binding.py` | 20 OK |
| `tools/test_crew_liveness_drift.py` | 10 OK |
| `tools/test_crew_applicability.py` | 48 OK |
| `tools/test_t1389_foreign_delta_adoption.py` | 9 OK |
| `tools/test_generation_migration.py` | 8 OK |
| `ruff check` on all touched files | All checks passed |

`python tools/validate.py` remains FAIL on exactly two classes, both expected
and named: (a) the two T-1424-era untracked files named by
`saipen/MANIFEST.json` (they must be committed before publication — the
handoff forbids committing yet); (b) a pre-existing stale Improve report
(`.saipen/improve/imp-vacterro-saipen-20260919-2/...`, protocol fingerprint
predates HEAD b7f5b512), unrelated to this work.

Final rerun after the two test-harness isolation fixes: focused 22 tests OK,
`ruff check` on every touched file All checks passed.

## 3. FreeBuff activation delivery — mechanical evidence

FreeBuff 0.0.115 (manicode), installed at
`C:\Users\vac34\.config\manicode\freebuff.exe`. Facts read from the binary's
own embedded code (offsets are byte positions in `freebuff.exe`):

- `~/.knowledge.md`, `~/.AGENTS.md`, `~/.claude.md` are the home knowledge
  surfaces; `xbA(...)` (offset 103102839) reads the FIRST existing one in that
  order and stores it as `userKnowledgeFiles` — one file, not three.
- `userKnowledgeFiles` is expanded into the session system prompt:
  `KNOWLEDGE_FILES_CONTENTS` (offset 102669671) joins the entries into fenced
  blocks substituted into the prompt — i.e. the block is ALWAYS-ON, delivered
  before the first user message.
- Skills are pre-loaded at session start from `~/.agents/skills` (and
  `~/.claude/skills`, plus cwd variants), each skill being a directory with
  `SKILL.md` (offsets 102942024/102638141/102943451; prompt text at 99712972).

Installed surfaces verified on this host:

- `~/.knowledge.md` carries the canonical `<!-- SAIPEN:BEGIN -->` block; strict
  UTF-8 decode passes and the Cyrillic twins are present as real bytes
  (`d181d181`). (An earlier apparent corruption was console rendering only.)
- `~/.agents/skills/saipen/SKILL.md` exists with `name: saipen` and the
  shortcut description; `.saipen_runtime.json` records
  `adapter_id: freebuff`.
- The regression `ActivationDeliveryTests.test_30` runs
  `bootstrap/inject.ps1 -AdapterId freebuff` against a disposable HOME and
  asserts the winning surface carries the exact block (strict UTF-8, no
  `{{SAIPEN_HOME}}` placeholder, skill copy present).

Conclusion: with the injector run on the host, FreeBuff receives the `cc`
activation semantics before conversational interpretation. What could NOT be
proved here is a live fresh session — see section 4.

## 4. Live FreeBuff acceptance — EXTERNALLY_BLOCKED

Two bounded probes (stdin/stdout/stderr as FILES, whole tree force-killed on
timeout; all `SAIPEN_*` carriers stripped so the model can only bind the
disposable fixture):

1. `freebuff --cwd <disposable managed project>`, stdin `cc\n` — the binary
   opened its full-screen TUI (recommendation/model banner) and never consumed
   piped stdin as a prompt. It stayed interactive until the 240 s bound; killed.
   stdout 3447 bytes of ANSI frames; `--help` exposes no non-interactive
   prompt transport (only `login`, `--continue [id]`, `--cwd`).
2. Staged keystrokes (`Enter`, then `cc` + `Enter`) over a parent-owned stdin
   pipe — the host answered with its own quota gate:

       Freebuff ⚠ Session limit reached
       You've used 105 of 105 sessions today. Try again in 4h 34m.
       Press Ctrl+C to exit.

Boundary: `freebuff` daily session quota exhausted (05/105 consumed at
2026-09-20T16:28 local; reset ≈ 21:02 local). This is an external host limit,
not a SAIPEN defect.

Exact operator acceptance (after reset), expected observations 1-6 of the
handoff REPAIR 6:

1. fresh `freebuff` session, cwd = a SAIPEN-managed project;
2. send exactly `cc` (no preamble, no path, no bootstrap command);
3. expect: `cc` interpreted as SAIPEN continuation (activation block loaded
   from `~/.knowledge.md`), `saipen continue` attempted automatically;
4. if the project's `STATE.saipen_home` is a dead foreign pointer while the
   executing engine proves, expect `HOST_BINDING_CONVERGED` and continued
   routing with no operator-supplied path;
5. no conversational "what does cc mean" fallback;
6. runtime genuinely unreachable -> structured `SAIPEN_HOST_RUNTIME_UNAVAILABLE`
   with the exact boundary.

Probe artifacts: `live-cc-probe.json`, `live-cc-probe2.json`,
`freebuff2-screen.txt` (this directory).
