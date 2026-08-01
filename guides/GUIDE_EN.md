<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Guide

Problem: AI agents have goldfish memory. Yesterday half day explaining architecture. Today fresh chat builds from scratch asking stupid questions.

**SAIPEN** = fireproof notebook in `.saipen/` folder. Agent wakes, reads STATE, BOARD. Sees where it left off. Gets back to work.

**Fast keys:** `cc` keeps active Goal Mode moving, `sss` checks status without touching code, and `ss` hits the brake after checkpointing. [Full 11-key map](../saipen/RFC.md#110-command-surface); Cyrillic twins `сс`, `ссс`, `аа`, `ее`, `рр` work too.

## Fire it up

**1. Beat rules into agent skull (once per machine)**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Start in your project**
Open agent in project folder. Tell it:
> `saipen set`

Creates `.saipen/`. Starts task list.

**3. Make it work**
- Type `saipen continue`. Agent reads board, picks top task, does it.
- Next day, blank chat, `saipen continue` again. Picks old notes. Resumes.

Want agent to remember tabs not spaces? Drop text file in `.saipen/KNOWLEDGE/`. Read like Ten Commandments before every task.

Kitchen (`.saipen/kitchen/`) = workbench. Half-finished files, scratchpads. Agent dies mid-task? Next one picks up from kitchen.

**4. Evolution (lazy mode)**
Board empty? Type `saipen`. No active work → auto HUNT. No bugs → ADD new feature. Zero hardcoding. Bulletproof. You just watch.

**5. Spring cleaning**
`saipen clean`. Agent scrubs repo. Prunes tickets. Deletes orphans. Fixes paths.

**6. Messy folder? Normal**
Uncommitted changes = Tuesday. Agent commits only at `ship`. Checks ownership before touching: own ticket → continue. Your edits → leave alone.

**7. Remember forever**
Drop architecture decisions in `.saipen/KNOWLEDGE/`. `decisions.md` or `ADR-001.md`. Read like scripture before planning.

**When stuck**
No git? Says so. No shell? Hands you command. `WAIT: <category> -- <question>` = needs you. The category is one of seven
(`manual-verify`, `destructive-op`, `first-publish`, `user brake`, `blocked`,
`safety valve`, `init`) and tells you what kind of answer unblocks it.

**Paranoid?**
```bash
python <saipen-clone>/tools/install_hook.py
```
Pre-commit hook. Broken board caught before commit. Remove:
```bash
python <saipen-clone>/tools/uninstall_hook.py
```

**SubSaipen in production**
`saipen sub spawn saihunt` — bootstraps `.saipen/extensions/subs/`, spawns read-only agent. Reports via OUTBOX.md. Never touches code. Built-in: saiwiki (wiki docs), saihunt (drift hunts), saitranslate (translation builds), saipython (minor fixes). Running in production since v7.84.0 — 4 live instances, proven across 30+ wiki pages and 32 locale translations.

## Commands Cheat Sheet

| Command | What it does | When |
|---|---|---|
| `saipen set` | On-switch. Creates memory folder, starts planning | New project |
| `saipen continue` | Workhorse. Reads notes, picks top task, does it | Resume after break |
| `saipen stop` | Brakes. Save progress, wait | Agent going crazy |
| `saipen status` | Report. Reads board, tells you state | Check what's happening |
| `saipen goal <text>` | Boss move. Pivots to new objective. Plans, builds, tests, ships solo. Then auto HUNT→ADD until mature or capped | Boss says "pivot now" |
| `saipen clean` | Janitor. Prunes, deletes, fixes | Before release |
| `saipen translate` | Builds 32-language bundle in sealed folder. Never touches source | Global release |
| `saipen markhunt` | Auditor. Dry exhaustive audit, records only, fixes nothing | Health check |
| `saipen prepare` | Handoff. Packages work for next agent, freshness check | Session wrap |
| `saipen ship` | Launch. Version bump, changelog, tag, push | Cut release |
| `saipen validate` | Checks `.saipen/` structure, fixes corruption | When state feels wrong |
