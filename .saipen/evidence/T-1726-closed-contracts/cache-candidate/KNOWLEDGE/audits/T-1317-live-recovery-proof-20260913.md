# T-1317 Phase B/C/D — installed-generation and live-session proof (2026-09-13)

Companion to `T-1317-fresh-session-reproduction-20260913.md` (Phase A, unchanged).
Phase A established the root cause; this record is the repair evidence and the
gate verdict. Adapter generation accepted here:

`T-1317-opencode-active-generation-20260913.3`

## 1. Accepted generation and byte identity (P0-2)

| surface | path | SHA-256 |
| --- | --- | --- |
| source artifact | `extensions/adapters/opencode/saipen-guard.js` | `5b435deb1c340a9a333f2b9fdda8f56bbf9446d09ead9a810413848c852f44c9` |
| installed (isolated run) | `<run-home>/.config/opencode/plugins/saipen-guard.js` | `5b435deb…44c9` |
| loaded module | same path, read at module evaluation | `5b435deb…44c9` |
| installed (USER HOME, this machine) | `~/.config/opencode/plugins/saipen-guard.js` | `5b435deb…44c9` |

Invariant `source SHA == installed SHA == loaded SHA` holds for all three.

The previous durable native-smoke record (`T-1317-opencode-native-smoke`) was
superseded: it recorded behavioural outcomes only and its adapter generation
(`…20260913.1`) is not the accepted one. The `.1` generation is preserved at
`.saipen/kitchen/t1317-opencode-install-backup/real-home-installed-before-.1.js`
(`b5d4accdd747e68c2e1a5f0fbdc03ce22eb8a51429e00dbe1244ac29df51b6a0`) — that is
the byte identity of the hook loaded in the FAILING Phase A session, so the
before/after generations are both anchored.

Live-generation evidence: `.saipen/evidence/T-1317-opencode-live-session/live-session-proof.json`.

## 2. P0-1 — no untrusted text in system authority

The model-visible bootstrap payload is now a CLOSED four-field record:
`binding_code`, `project_root`, `project_lineage`, `provenance` (bounded enum
`explicit|host-session|git-worktree|git-common|ancestor`) plus one fixed
adapter-generated instruction. The guard's `detail` — which echoes project- and
environment-controlled text — is no longer serialized into a system message; it
stays in the startup diagnostic, evidence and ordinary tool output.

Values carried into system authority are bounded: control characters and
newlines are stripped and an over-long value is refused rather than truncated,
so no carried string can smuggle a second authority line.

Red control (proven, not asserted): driving the same hostile case against a
copy of the adapter with `detail` re-added to the payload gave
`payload keys ['binding_code','detail','project_lineage','project_root','provenance']`
and `hostile text in system: True`. The regression therefore goes red on the
pre-fix shape.

Regression: `tools/test_opencode_adapter.py::test_p0_1_project_derived_text_never_becomes_system_instruction`.

## 3. Two host facts found while building the live proof

Both were measured against OpenCode `1.18.30` and both change adapter behaviour.

1. **`context.worktree` can be a placeholder.** For a session started in a
   directory OpenCode does not recognize as a VCS worktree, the factory
   `context.worktree` is `/` while `context.directory` is the real project.
   A single worktree-first pick therefore LOST a binding the host had supplied
   (measured: `binding_code: NOT_SAIPEN_PROJECT`, `context_worktree: "/"`,
   `context_directory: V:\_TEMP_\…`). The adapter now rolls the canonical
   resolver against the host candidates in order — worktree first, then
   session directory — and takes the FIRST candidate that yields a canonical
   binding. The second candidate is only ever consulted to FIND a binding, so
   an asserted-but-invalid carrier (matrix E) still fails closed identically
   for every candidate and no ambient fallback can appear. The resolved
   candidate, not the placeholder, is used as the admission cwd.
   The adapter's own process cwd is NOT a candidate while the host supplied any
   context (that would adopt an unrelated ambient repository and make a
   genuinely non-SAIPEN session look bound).

2. **The session directory comes from `PWD`.** With `PWD` inherited from the
   launching shell, `opencode run` created the session instance for that
   directory instead of the child's working directory (measured with
   `--print-logs`: `creating instance directory="V:\…\_SAIPEN"` followed by
   `created … directory="V:\…\_SAIPEN"`). Every control that launches a real
   OpenCode process now clears `PWD`/`OLDPWD` before launch. Without this a
   test that intends to write into a fixture silently writes into the auditor's
   repository — which is exactly what the three
   `tools/test_opencode_bound_launch_smoke.py` controls did before the fix.

## 4. P0-3 — real fresh-process session proof

Harness: `tools/test_opencode_live_session.py` (opt-in, `SAIPEN_LIVE_OPENCODE=1`).
It runs the project's own `bootstrap/inject.sh` into a run-owned home, then
starts genuine new OpenCode processes with a real tool-capable model and reads
the host's own `--format json` event stream. Result: **6 passed**.

| item | evidence |
| --- | --- |
| installation | `inject.sh` rc 0; hook + skill installed; legacy singular surface absent |
| fresh process | good session host pid `10360`, malformed session host pid `8248`; both after install |
| session identity | `ses_f6652470bffeRBU7pwqdCBFnF4`, `ses_f66521bf4ffeoCq2Qw2A2tE7L6` |
| binding visible before tools | factory captured `binding_code: ADMITTED`, `project_root` = the fixture, `root_resolution_provenance: git-worktree` at factory time, before any tool event |
| model actually saw it | the model printed `binding_code` `ADMITTED` and the exact `project_root` in both sessions |
| no root question | no `question` tool event in either session; no root-question phrasing in either transcript |
| native Todo | exactly one `todowrite` part, `status: completed`, no error |
| staging read | external audit file outside the project read successfully (`ADMITTED_EXTERNAL`) |
| ordinary work | `src/agent_note.txt` written with `ok` |
| protected mutation | `rm -f .saipen/STATE.md` → `SAIPEN_GUARD_REFUSAL: PROTECTED_CANONICAL_NAMESPACE` before host execution; STATE bytes unchanged |
| malformed state | `pwd` → `SAIPEN_GUARD_REFUSAL: PROTOCOL_STATE_INVALID` |
| interpretation | the model answered `ROOT_KNOWN_RECOVERY_REQUIRED`, not `ROOT_UNKNOWN` |

Because the fixture is a real git worktree, `context.worktree` named the
project and the resolution came from it: the staging/external-file workflow
(matrix B) now yields a known root and no root question.

## 5. BLOCKING FINDING — the canonical recovery path does not exist

Step 9 of the required sequence (restore valid protocol state through the
canonical path) **cannot be satisfied by the current Core engine**, and this is
not an adapter defect.

Reproduced against a COPY of the real FastPrompter `.saipen/` (the real tree was
not mutated):

```
$ saipen status          rc=1 REFUSE [VALIDATION_FAILED]
$ saipen stop            rc=1 REFUSE [VALIDATION_FAILED]
$ saipen recover         rc=1 REFUSE [VALIDATION_FAILED]
$ saipen transition DONE rc=1 REFUSE [VALIDATION_FAILED]
$ saipen next            rc=1 REFUSE [VALIDATION_FAILED]
STATE unchanged after all: True
```

Every canonical verb validates the checkpoint before dispatch, so a phase
outside the legal set (`phase: IMPL`) makes ALL of them refuse, while the guard
correctly refuses generic shell with `PROTOCOL_STATE_INVALID`. The canonical
namespace is the only surface allowed to write `STATE.md`, and direct mutation
of it is refused as `PROTECTED_CANONICAL_NAMESPACE`. The live session reproduced
the same deadlock end to end: `saipen transition DONE` was ADMITTED by the guard
(the canonical repair surface is reachable — the adapter's contract) and the CLI
then produced no repair (`state_changed: false`).

So the repaired semantics are:

```
KNOWN ROOT + INVALID PROTOCOL  !=  UNKNOWN ROOT      (adapter: satisfied)
KNOWN ROOT + INVALID PROTOCOL  ->  ??? (no legal action)   (Core: OPEN)
```

T-1317 therefore stays in BUILD. Step 10 ("after canonical recovery, prove
ordinary allowed project work can execute") is unreachable for the same reason.

## 6. Gate results

- Focused adapter/native/guard matrix (9 files incl. all OpenCode controls):
  **101 passed, 0 failed** (65 s).
- Live real-session proof: **6 passed** (35 s), opt-in.
- Broad `python tools/validate.py --gate core`: baseline from the Phase A record
  `37 problem(s), 25 warning(s)` → final **`38 problem(s), 25 warning(s)`**.
  Patch-owned delta = **+1**, and it is exactly
  `FAIL: runtime manifest names a file git does not track:
  tools/test_opencode_live_session.py` — the new opt-in live harness is present
  in the working tree and not yet committed. It clears on commit (or by dropping
  the file). The other seven untracked-manifest entries pre-date this gate. No
  validator finding names the adapter or the bootstrap payload.
- The stale `--gate core` delta is NOT claimed as green: the broad gate remains
  RED with carried historical debt, as before.

## 7. Status

- T-1317: **BUILD**, not closed. Acceptance is satisfied for the adapter repair
  (binding visible before consequential admission, exact native Todo, protected
  mutation refusal, known root under malformed state) and NOT satisfied for
  canonical recovery.
- Adaptive Runtime Wave 2: **NOT permitted to begin** — the hard stop requires
  known-root/malformed-state recovery to work without asking the user for a root,
  and no canonical repair of a malformed `STATE.md` exists.
