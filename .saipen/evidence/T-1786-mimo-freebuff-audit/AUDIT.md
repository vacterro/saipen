# T-1786 / SRC-252 -- MiMo 2.6 Pro in FreeBuff Desktop: SAIPEN entry overhead

Scope: observable output only. The supplied FreeBuff transcript is diagnostic
evidence; it is referenced by locator and digest and is not reproduced here.
No hidden reasoning of any model is inferred.

## Evidence

- Transcript: operator message queued into Claude session
  `e0c801c2-7cbb-4bfa-aebc-8ebe132fb3d6` (jsonl entry 2852,
  2026-10-14T17:57:53Z). Transcript body 9715 bytes, sha256
  `90c4d9c00d4f1e9fa584c4cdc7a2459e60675655d9d5fc41734848c2e787e072`.
- Host facts visible in it: input `cc`; host label "Working for 7m 35s";
  global instructions `~/.AGENTS.md`; account skill `saipal`; host read tool
  limited to the workspace; Git Bash shell.
- Live checks, 2026-10-14 (this machine): `~/.AGENTS.md` (3854 B, SAIPEN
  block); FreeBuff account skills under
  `~/.config/freebuff-desktop/account-skills/` (saipal present, no saipen);
  `extensions/adapters/registry.json` entry `freebuff`; `saipen cc --json`
  in this repo and in an empty directory; installed skill directories of
  Claude, Codex, OpenCode and generic `~/.agents`.

## Observable timeline

1. `cc` arrives. Before the first tool call the session emits 7361 characters
   of visible deliberation. Recurring subjects (counts of plain mentions):
   `cc` 34, SAIPAL/saipal 24, `CORE.md` 14, `BOOT.md` 8. It weighs the SAIPEN
   shortcut gate against the SAIPAL skill trigger, searches for the right
   document order, converts the launcher path by hand, and reconciles the
   FIRST-OUTPUT GATE with the fact that reading files needs tool calls.
2. Two terminal commands: workspace probe (`pwd`, `ls -a`, `.saipen`
   presence, `command -v saipen`) and a listing of the SAIPEN home. Result:
   workspace `_PLUG_SCRIPT/_FREEBUFF_SAI` holds `.saipen/`; `saipen` is on PATH
   (`/c/Users/vac34/bin/saipen`).
3. A second deliberation (1884 characters) plans `cat` of BOOT, STYLE,
   EXECUTION and STATE because the host read tool refuses paths outside the
   workspace.
4. End of the supplied evidence: no SAIPEN command has run. The one command
   that answers routing, binding, STATE and phase (`saipen cc --json`) was
   available from the first second.

## Findings

### 1. Conflicting command ownership (SAIPEN vs SAIPAL)

- Root cause: two installed artifacts claim bare `cc`. SAIPEN's global block
  declares it a SAIPEN command; SAIPAL's skill description says "Trigger on
  ... the `cc` shortcut" (`saipal/REGISTRY.json` `"cc": "saipal continue"`;
  installed copies `~/.agents/skills/saipal/SKILL.md` and the FreeBuff account
  skill). In FreeBuff Desktop the account skills carry no saipen skill, so the
  only *skill* claiming `cc` there is SAIPAL's.
- Same class, SAIPEN side: the installer's sibling backup
  `.saipen-user-backup-<hash>/` kept a live `SKILL.md` (`name: saipen`) inside
  each host's skill scan root -- one per host in `~/.claude/skills`,
  `~/.agents/skills`, `~/.codex/skills`, `~/.config/opencode/skills`
  (created 2026-10-04). Claude Code lists it as a second `saipen` skill.
- Owners: SAIPAL owns its trigger (operator decision 2026-10-14: SAIPEN keeps
  `cc`, SAIPAL takes its own token). SAIPEN owns the installer.
- Correction: SAIPAL handoff below. SAIPEN: the block states one owner
  ("SAIPEN owns it even when a skill or persona also lists it");
  `bootstrap/install_ownership.py` keeps a backed-up `SKILL.md` as
  `SKILL.md.user-backup`, bytes preserved, never registered.

### 2. Ambiguous resolution of `cc`

- Root cause: the block and BOOT step 7 ordered "resolve through CORE.md 1.10's
  shortcut table". CORE § 1.10 holds no table: it delegates to `REGISTRY.json`
  (machine) and `COMMANDS.md` § Shortcut table (human). The engine already
  resolves every whole-message token mechanically from `REGISTRY.json`
  (`tools/saipen.py` shortcut resolution before dispatch,
  `saipen_engine.commands.load_shortcut_table`). A model was told to read a
  32 KB constitution for a table that is not in it -- the 14 CORE mentions.
- Owner: SAIPEN protocol text.
- Correction: the block says the CLI resolves the token; BOOT step 7 points at
  `saipen <token>` (REGISTRY.json; COMMANDS.md as human view). The stale
  "cannot load CORE.md" comment in `tools/saipen.py` and the validator warning
  text now name the registry.

### 3. Excessive instruction before the first tool call

- Root cause: the 3664-byte block put five pre-conditions on the model before
  it could act: establish that the root holds `.saipen/`; read BOOT and follow
  its router ("Follow BOOT, run `saipen continue --json`" leaves the order
  open); read CORE for the table; read STYLE and EXECUTION "BEFORE composing
  ANY assistant response (... tool preamble ...)", which a model that can
  only read through tool calls cannot satisfy literally; read STATE before
  work. On FreeBuff each read outside the workspace costs a terminal `cat`.
  Mandated pre-reads before the first command: about 57 KB (BOOT 10.4 KB,
  CORE 32 KB, STYLE 7.3 KB, EXECUTION, STATE).
- Host side: FreeBuff is ADVISORY -- no session-start injection, no
  pre-output interception, no prompt-to-work binding (`registry.json`
  `freebuff`). Claude Code receives BOOT/STYLE/EXECUTION from its SessionStart
  hook; FreeBuff receives only the block.
- Correction: a FIRST ACTION paragraph -- one tool call, `saipen <token>
  --json`, before any text; no pre-reads for that call; a tool call is not
  assistant text; style through `saipen response style --json` (the compiled
  contract EXECUTION designates for hosts). Pre-reads before the first command:
  0. Block size 3664 -> 3983 bytes; the growth is the one paragraph that
  replaces the five pre-conditions.

### 4. Broken launcher reference

- Root cause: `{{SAIPEN_HOME}}` renders the PROTOCOL directory (it must, for
  BOOT.md, STYLE.md, UI.md). The LAUNCHER line appended `/bin/saipen` to it,
  but in a source clone the launchers live under the runtime root, the parent
  of `saipen/`. All six installed instruction surfaces (`~/.claude/CLAUDE.md`,
  `~/.AGENTS.md`, `~/.codex/AGENTS.md`, `~/.knowledge.md`,
  `~/.gemini/GEMINI.md`, `~/.config/opencode/AGENTS.md`) name
  `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\saipen/bin/saipen`, which does
  not exist, with mixed separators on top. BOOT's own rule was right: STATE's
  `saipen_home:` is the runtime root.
- Owner: SAIPEN activation template.
- Correction: LAUNCHER uses `<saipen_home>` from `.saipen/STATE.md` (BOOT's
  one-read rule). The block renders no launcher path at all.

### 5. Missing verified project binding

- Root cause: FreeBuff supplies no project-root carrier
  (`SAIPEN_PROJECT_ROOT`), and the block made activation conditional on a fact
  the model had to establish itself. The CLI binds already (Git worktree, then
  nearest `.saipen/` ancestor) and fails closed: in an empty directory
  `saipen cc --json` returns `NOT_SAIPEN_PROJECT` and writes nothing (verified
  live and by `test_t1786_cli_first_activation`).
- Owners: host for an optional carrier; SAIPEN for delegating binding.
- Correction: the block hands binding to the CLI. Binding rules, the guard and
  every lifecycle gate are unchanged.

### 6. Responsibilities that belong to the host or protocol

| Duty | Before | Owner now |
|---|---|---|
| Shortcut to command | model reads a (missing) CORE table | CLI, `REGISTRY.json` |
| Project binding | model `pwd`/`ls` | CLI; host carrier where available |
| STATE validation | model reads STATE | CLI |
| Launcher path | model converts a broken path | PATH launcher; STATE one read on a miss |
| Style/response contract | model reads two files | `saipen response style --json`; host injection where hooks exist |
| Trigger arbitration | model weighs skills | artifact owners: one token, one owner; installer leaves no registered duplicate |
| FreeBuff account-skill freshness | nobody | operator / host sync route (HOST_SKILL_SYNC) |

Secondary, not changed here: `saipen cc --json` in this repository answers
33 KB, of which 28 KB is the `parked_work` inventory. A compact default
projection would cut what a weaker model has to scan.

## Verdict on the proposed SAIPAL `cc` -> `pal` handoff

Right direction and matches the operator decision. `pal` lies outside SAIPEN's
doubled-letter namespace, so it cannot collide with a future SAIPEN shortcut.
Keeping `cc` as an observed SAIPEN token in the forensic adapters is correct.
Alone it is insufficient: findings 2-5 are SAIPEN-side. The ten-section form
repeats the failure under audit (instruction volume).

Status measured 2026-10-14 ~21:30: the SAIPAL source already carries the change
(uncommitted `saipal/REGISTRY.json` `{"pal": "saipal continue"}`, both
`SKILL.md`, `saipal.py cc` refusal naming `pal`), and
`~/.agents/skills/saipal/SKILL.md` was re-synced at 21:16. Still claiming bare
`cc`: the FreeBuff account skill
(`~/.config/freebuff-desktop/account-skills/.../saipal/SKILL.md`, 21:04) and
`~/.config/opencode/skills/saipal/SKILL.md` (2026-09-04). FreeBuff Desktop
reads the account skill, so the incident host still sees two owners until it
is re-synced. The handoff below covers only that remainder.

## SAIPEN changes in T-1786

- `saipen/ACTIVATION_BLOCK.md` -- CLI-first entry, single owner, launcher from
  STATE, style in one call, no phantom table.
- `saipen/BOOT.md` step 7 -- shortcut resolution through `saipen <token>`.
- `bootstrap/install_ownership.py` -- inert backup name for `SKILL.md`.
- `tools/saipen.py` (comment), `tools/validate.py` (warning text).
- `tools/test_t1645_zero_hunt.py` -- launcher pins follow the corrected rule.
- `tools/test_t1786_cli_first_activation.py` -- regression and claim tests.

## Security

Unchanged: fail-closed binding (`NOT_SAIPEN_PROJECT`), guard, admission,
lifecycle gates, STATE/BOARD/LOG write rule, STYLE language pin. The block
moves facts the model guessed to the component that already enforces them.

## Delivery

Installed instruction surfaces still carry the old block. The scheduled
injector `saipen-inject` skips while the source tree is dirty
(`SKIP: DIRTY_SOURCE`, `%LOCALAPPDATA%\saipen\inject.log`, 2026-10-14 21:16).
FreeBuff sees the new block after the source is committed and the injector
runs.

## Handoff -- SAIPAL (remainder: installed skill sync)

```
SAIPAL - SAIHANDOFF - INSTALLED SKILL SYNC FOR PAL

EXECUTOR: SAIPAL agent (SAIPAL repository, its install/sync route)
PRIORITY: P1
AUTHORITY: operator decision 2026-10-14 -- SAIPEN keeps bare `cc`,
  SAIPAL uses `pal`. Source change already present in the SAIPAL tree.
EVIDENCE: SAIPEN T-1786 audit (MiMo 2.6 Pro in FreeBuff Desktop weighed the
  SAIPEN gate against the SAIPAL skill trigger for `cc` before any tool call).

DEFECT
Installed SAIPAL skills that still advertise bare `cc`:
- ~/.config/freebuff-desktop/account-skills/<account>/<id>/saipal/SKILL.md
  (FreeBuff Desktop account skill; frontmatter: 'Trigger on "saipal",
  "/saipal cc", the "cc" shortcut')
- ~/.config/opencode/skills/saipal/SKILL.md (2026-09-04 copy)
Already current: ~/.agents/skills/saipal/SKILL.md ("pal").

CHANGE
1. Re-sync both copies from skills/saipal/SKILL.md through the supported
   route (FreeBuff account-skill import/upload; OpenCode skill install).
2. No local hand edit of the FreeBuff account-skill cache if the account sync
   would overwrite it; without an authorized route report
   HOST_SKILL_SYNC_REQUIRED with the exact path.

VERIFY
- No installed SAIPAL SKILL.md contains a bare `cc` trigger.
- FreeBuff Desktop, fresh session: `cc` selects no SAIPAL skill; `pal` does.
Report SOURCE_VERIFIED and HOST_VERIFIED separately.

OUT OF SCOPE
SAIPEN files, FreeBuff Desktop source, SAIPAL engine behavior.
```
