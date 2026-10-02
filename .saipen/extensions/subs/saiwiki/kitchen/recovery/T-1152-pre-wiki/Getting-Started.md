# Getting Started

## Install (once per machine)

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

Teaches Claude Code, Codex, Gemini, OpenCode, Aider, Antigravity, FreeBuff. Appends marked block to agent instruction files, copies protocol to skill folders. Backs up originals to .bak.

> **Installs are complete (v7.126.0+):** injectors now ship `VERSION` alongside the protocol — a fresh skill can prove which release it runs. Refreshes replace managed directories instead of overlaying, so deleted source files no longer survive forever in installed copies. The runtime manifest makes forgetting either a validation failure.

> **Windows users (v7.100.0+):** `inject.sh` now converts paths via `cygpath -w` under git bash / MSYS / Cygwin. Previously, `pwd` returned `/v/proj/saipen` — a path only that shell can resolve. Windows agents couldn't open it, leaving CLAUDE.md full of dead paths with no error at all.

**Uninstall:** `powershell ... uninstall.ps1` or `bash uninstall.sh` — strips exactly the marked block, saves `.uninstalled.bak`.

**Full list** of what every file change touches (nothing outside agent instruction files and skill folders): [GitHub README](https://github.com/vacterro/saipen).

## Start a project

Open agent in your folder, type:
> `saipen set`

No install? Paste one line to any agent:
> `Read <clone>/saipen/BOOT.md first, then <clone>/saipen/CORE.md + <clone>/saipen/STYLE.md`

## Core workflow

```
saipen set        -> INIT  -> creates .saipen/
saipen goal X     -> PLAN  -> tickets for objective
                     SCOUT -> claim first ticket
                     BUILD -> implement
                     VERIFY-> test
                     REVIEW-> human or manual-verify
                     SHIP  -> tag + push
                     DONE  -> HUNT -> ADD -> ...
```

## Commands

| Command | When | What |
|---|---|---|
| `saipen` / `saipen continue` | Any time | Resume: read STATE, execute next_action |
| `saipen goal <text>` | DONE | New objective, auto-run to caps |
| `saipen plan` | DONE/IDLE | Generate tickets from analysis |
| `saipen clean` | Any | Deep scrub: board, orphans, links, trash |
| `saipen translate` | Any | Isolated locale translation build |
| `saipen markhunt` | Any | Dry exhaustive audit (records only) |
| `saipen prepare` | Any | Package work for next agent |
| `saipen ship` | REVIEW | Version bump, changelog, tag, push |
| `saipen validate` | Any | Run conformance checker |
| `saipen status` | Any | Read-only report (read BOARD+STATE) |
| `saipen stop` | Any | Checkpoint + halt |
| `saipen hunt` | Any | Run the HUNT sweep now |
| `saipen crew` | Any | The whole circuit: hunt, reproduce, intake, build, translate, document, ship |
| `saipen test` | Any | Run the declared suite, report PASS/FAIL |
| `saipen userperson` | Any | Optional preference meta-control, off by default |
| `saipen improve` | Any | Meta-control audit: status / sweep / verify / clean |

## WAIT categories (v7.93.0+)

`next_action` must carry one of 7 tokens:

| Category | Meaning |
|---|---|
| `manual-verify` | Human must test this |
| `destructive-op` | Ask before deleting/overwriting |
| `first-publish` | Confirm name + public/private |
| `user brake` | Intentional pause by user |
| `blocked` | Stuck, needs human decision |
| `safety valve` | Goal caps hit, re-authorize |
| `init` | First-time setup question |

## Portable floor (v7.94.0+)

No Python? `tests/validate.sh` and `tests/validate.ps1` probe all 9 STATE fields. Never more permissive than `tools/validate.py`. Both check read-only bans, WAIT categories, required fields.

**Audited** (v7.100.0): `tools/audit_floor.py` breaks a scratch project 20 ways, then asserts both halves of the floor still go red. First run exposed a wording divergence between `.sh` and `.ps1` on the same defect — aligned.

Known gap: the portable floor checks that `next_action:` is present, never that it's executable. `tools/validate.py` covers executability on any host with Python.

## Pre-commit hook (v7.113.0+)

**Generation 7** (v7.205.2): the hook queries the CI status tool (gen 4, v7.200.0), skips a missing tool via the `-f` guard, resolves the cache path through git, and stays fail-open — a red CI must never block the commit that fixes it.

The hook carries a **generation stamp** compared against the installer's current version. A hook installed twenty releases ago runs the logic it was born with — the stamp catches silent staleness.

When neither `tools/validate.py` nor the portable floor is found (moved `saipen_home`), the hook still exits 0 (fail-open) but now prints what it could not find and the repair command. An unvalidated commit that *looks* validated was the problem; silence was the enabler.

## Audit tools (v7.109.0+)

| Tool | What it checks |
|---|---|
| `tools/audit_floor.py` | Portable floor still goes red on all 27 checks × 2 halves. Windows: adds Git `usr/bin` to child PATH only, rejects System32 WSL stub (v7.100.0, v7.127.0) |
| `tools/audit_tags.py` | Every git tag matches VERSION (v7.109.0) |
| `tools/audit_order.py` | No top-level name read before its definition (v7.112.0) |
| `tools/audit_checks.py` | Canonical mutation harness proving validator checks still catch their named failure; LOG mutations resolve sealed segments, no-op mutations are rejected, root `nul` is harmless, and chat-language/voice contracts stay exact — a skipped case is fatal, never a shrunken denominator (v7.119.0, v7.133.0, v7.155.0–v7.157.0) |
| `tools/audit_parity.py` | Floor baseline never drops; observes one real release-ledger process via Git Trace2 (v7.120.0, v7.129.0) |
| `tools/run_scenarios.py` | Executes both injectors in isolated homes, installed validators, floor behavioral cases — guards run the script, not its spelling (v7.126.0, v7.131.0) |

## Producer packages (v7.226.0+)

`ee` and `qq` are isolated prepares. They may run at the same time because saitranslate and saiwiki use different producer-local locks and namespaces; two `qq` runs serialize. A READY package carries exact payload bytes, source identity, role revision, read-set hashes, write-before hashes, scope, epoch, and deterministic identity. Core alone integrates it. Changed unrelated source may be COMPATIBLE_DRIFT; a changed declared dependency is STALE and must be prepared again. See [ADR-0001](https://github.com/vacterro/saipen/blob/main/KNOWLEDGE/ADR-0001-v7-producer-parallelism.md).

## Project root (v7.132.0+)

Checkpoints bind to one dynamically resolved project root per session — never ambient cwd. Git projects use the worktree/common-dir pair; linked worktrees use the main worktree's gitignored memory; non-Git projects use the nearest ancestor carrying `.saipen/`. `saipen continue --project-root <path>` deliberately overrides cwd from elsewhere. An unowned cwd fails instead of guessing or creating a second memory tree.

## ДED Voice

> "Ставишь один раз — и забыл. Потом в любой папке: saipen set — и работаешь. Не надо каждый раз объяснять агенту кто ты и что ты хочешь. Просто continue — и он уже читает твой STATE. Ленивый? Да. Работает? Ещё как."
