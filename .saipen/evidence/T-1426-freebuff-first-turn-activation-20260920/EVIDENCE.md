# T-1426 — FreeBuff first-turn `cc` activation: evidence

Date: 2026-09-20. Ticket: T-1426 (SRC-081, handoff
`V:\_TEMP_\fastprompter_drag\SAIPEN_20260920_1939.md`). Supersedes the
remaining scope of T-1425 (unblocked E-7613 after its external blocker
cleared).

## 1. LIVE_FREEBUFF_CC_RED — first-turn command semantics absent

Operator acceptance (handoff): a fresh real FreeBuff session against a
SAIPEN-managed project, message exactly `cc`. Model treated `cc` as
ambiguous, inspected repository files, and only concluded "SAIPEN continue"
after archaeology.

Measured RED evidence, from the host's own persisted assembly state:

| Fact | Value |
|---|---|
| Host surface | FreeBuff **Desktop** (orchestrator pid 19412, started 2026-09-20T16:35:35Z) |
| Project | `V:\___VAC\__K\__CODE\_TAMPERMONKEY\_WIN95THEME\Wintage` (SAIPEN-managed, `.saipen/STATE.md` T-268) |
| Thread | `b3102adf-bab3-490d-8924-885be4a1d58c`, harness `codebuff`, model `z-ai/glm-5.3-flash` |
| User message | `cc` at 2026-09-20T16:36:16Z (`messages.parts_json`) |
| Effective knowledge files | `threads.harness_state.sessionState.fileContext.userKnowledgeFiles = {}` |
| Project knowledge files | `knowledgeFiles` = `[]` |
| Raw 506 KB assembly state | contains no `<!-- SAIPEN:BEGIN -->`, no `AGENTS.md`, no `knowledge.md`, no `cc` semantics |

The first-turn prompt carried **zero** SAIPEN command semantics.

## 2. Effective FreeBuff prompt path (measured, not inferred)

Two FreeBuff loaders share the same home directory but not the same contract.

**CLI** (`C:\Users\vac34\.config\manicode\freebuff.exe`, 0.0.115; string
evidence recorded under T-1425): reads the FIRST existing of
`~/.knowledge.md`, `~/.AGENTS.md`, `~/.claude.md`.

**Desktop** (installed orchestrator bundle,
`%LOCALAPPDATA%\Programs\@codebufffreebuff-desktop\resources\orchestrator\orchestrator.js`):

- `loadUserKnowledgeFiles` (bundle byte ~7174329): scans the home for
  **dot-prefixed** entries only, matches names in
  `KNOWLEDGE_FILE_NAMES_LOWERCASE` = `["agents.md", "claude.md"]`, reads the
  FIRST match; `~/.knowledge.md` is not a home surface for it (`*.knowledge.md`
  is recognized only as a PROJECT file name).
- `KNOWLEDGE_FILES_CONTENTS` (bundle byte ~6628886) merges
  `fileContext.userKnowledgeFiles` into the always-on system-prompt block.
- `initialSessionState` (call site ~7262038) runs the loader for every fresh
  run, so an EXISTING thread keeps the `userKnowledgeFiles` it was born with.
- `projectInstructions` / `injectAgentsMd` (bundle byte ~9974508, host
  `state.json` has `injectAgentsMd: false`) gates PROJECT files only; the home
  knowledge loader is not pref-gated.

Pre-fix host state: `~/.knowledge.md` existed with the block; `~/.AGENTS.md`,
`~/.claude.md` did not. The desktop loader therefore delivered `{}` —
exactly what the RED thread's persisted `userKnowledgeFiles` proves.

## 3. Delivery fix

- `bootstrap/inject.ps1` (freebuff-backstop) and `bootstrap/inject.sh`: the
  either/or surface choice is replaced by a data-driven install of EVERY
  registry-declared `instruction_surfaces` entry
  (`~/.knowledge.md` and `~/.AGENTS.md`). One surface can only satisfy one
  loader.
- Live host repair (canonical injector, `-AdapterId freebuff`):
  `~/.knowledge.md  block refreshed` / `~/.AGENTS.md  file created`.

## 4. First-turn contract

`saipen/ACTIVATION_BLOCK.md` (rendered): `cc` / `сс` mean canonical SAIPEN
continue; bootstrap first; no conversational interpretation of a shortcut;
project memory at `.saipen/`. The block is now the first thing the desktop
loader reads (`~/.AGENTS.md`, 3151 bytes, strict UTF-8, placeholder
substituted, no `{{SAIPEN_HOME}}`).

## 5. Test evidence (tools/test_host_bootstrap.py)

| Test | What it proves | Result |
|---|---|---|
| `test_30` | ps1 injector leaves the exact block on BOTH loader contracts | PASS |
| `test_31` | red control: `.knowledge.md` alone is invisible to the desktop loader | PASS |
| `test_32` | executes the HOST's own extracted `loadUserKnowledgeFiles`: red home → `{}`, green home → block delivered under `~/.AGENTS.md` | PASS |
| `test_33` | red control: the pinned pre-fix injector blob (7fdcdac) fails the desktop contract | PASS |

Focused suite: 25 tests OK. `ruff check tools/test_host_bootstrap.py`: clean.

## 6. Live assembly proof (real home, host's own loader)

Ran the extracted desktop `loadUserKnowledgeFiles` (installed bundle) against
`C:\Users\vac34`:

```json
{
  "~/.AGENTS.md": {
    "bytes": 3151,
    "hasBlock": true,
    "hasCc": true,
    "hasCyrillicTwin": true,
    "hasPlaceholder": false
  }
}
```

Before the repair the same probe returned `{}`. The activation bytes are
present in the assembly input before any request is sent.

## 7. Regression scope and inherited reds

- `tools/test_runtime_bootstrap.py` 23 OK; `test_instruction_home_parity` 11 OK;
  `test_t1389_foreign_delta_adoption` 9 OK after the inject.sh repair.
- `test_adapter_parity` 1 failure (`FIRST-OUTPUT LANGUAGE GATE` template drift)
  and `test_command_routing` 46-47 failures (fixture flake + inherited) are
  IDENTICAL at clean HEAD worktree `ec53042a` — not introduced here.
- `python tools/validate.py`: 3 FAIL = the 2 known untracked manifest files
  (`tools/saipen_engine/host_bootstrap.py`, `tools/test_host_bootstrap.py`,
  must be committed at the next ship) + the pre-existing stale Improve report.
- OpenCode surfaces untouched.

## 8. Live GREEN — operator acceptance pending (GUI)

Cannot be driven from this session: mutating `/api/` routes of the running
desktop orchestrator require `x-freebuff-launch-id` (401 on `/healthz`), and
the CLI has no non-interactive prompt transport.

Operator steps: open a NEW thread in a disposable managed project
(`V:\_TEMP_\t1425-cc-fixture-2mynjxx8`, or Wintage), send exactly `cc`,
expect: no ambiguity, no cc-meaning question, no repository search for the
meaning of `cc`, immediate SAIPEN bootstrap. New thread is required — old
threads keep their birth `userKnowledgeFiles`.

## 9. T-1425 disposition

T-1425 unblocked at E-7613 (external quota blocker cleared, acceptance ran and
failed). Supersession T-1425 -> T-1426 is recorded at closure under SRC-081.

## 10. Regression anchors

- verifier `tools/test_host_bootstrap.py`: sha256 `b2b949800a1c4be372faf9b3b68e9fbb52076d18cfdf51c4dc6c773bdff2619d`
- pre-fix subject `bootstrap/inject.ps1` (git blob `7fdcdac`): sha256 `20275404ce27be016e90e73a9fd3a3c90a040fb7825b5b7997c77df2112a441c`
- post-fix subject `bootstrap/inject.ps1` (worktree): sha256 `c9d0d653cba622c3570f43a01d67e61f7ca8740cc32ceda4e6440230ad867f76`
- LOG: REGRESSION-EVIDENCE FAIL E-7619, PASS E-7620; MANUAL-VERIFY STEPS E-7621;
  VERIFY summary E-7622. BUILD E-7617, VERIFY boundary E-7618.
- Freshness gap filed as T-1427 (E-7616).
