# Tutorials

## 1. First project setup

```bash
git clone https://github.com/vacterro/saipen
cd my-project
saipen set
```

Creates .saipen/ with STATE.md (INIT), BOARD.md (empty), LOG.md (skeleton). Agent reads BOOT.md -> CORE.md -> STYLE.md -> executes INIT.

## 2. Running with goal mode

```
> saipen goal 'add CSV export'
Agent: PLAN -> creates T-1 (CSV export)
       SCOUT -> claims T-1
       BUILD -> implements
       VERIFY-> tests pass
       REVIEW-> self-review clean
       SHIP  -> v0.2.0 tagged
       DONE  -> HUNT -> clean -> ADD -> ... (autonomous)
```

Goal mode: auto-pilot until mature or cap (3 waves / 20 tickets).

## 3. Manual workflow (one ticket at a time)

```
> saipen plan 'add dark mode'
Agent: creates T-2 (theme toggle), T-3 (dark CSS)
> (agent auto-claims T-2 and builds it)
> saipen stop
Agent: checkpoints, writes digest, halts
> (next day) saipen continue
Agent: reads STATE -> T-2 in DOING -> resumes BUILD
```

## 4. Handling a blocker

T-4 has `needs: T-2`. T-2 not done -> agent leaves T-4 in TODO, works T-2 first. All tickets blocked -> BLOCKED.

## 5. SubSaipen parallel research

```
> saipen sub spawn saihunt
Agent: dispatches saihunt (read-only)
       saihunt scans 6 HUNT categories
       writes findings to OUTBOX
       main agent collects OUTBOX
       creates tickets for real findings
```

Collect discipline: main agent runs `git status` against whole tree before folding findings. A confused sub that wrote outside its folder gets caught (boundary check, v7.98.0+).

## 6. MARKHUNT dry audit

```
> saipen markhunt
Agent: exhaustive audit (no cap)
       finds everything: bugs, dead code, symmetry gaps
       records to BOARD as [MARKHUNT] tickets
       NEVER fixes anything
       Human triages: move to TODO or dismiss
```

## 7. Translation workflow

```
> saipen translate
Agent: quarantined env in .saipen/saitranslate/
       builds locale packs for all 32 languages
       never touches main tree
       OUTBOX with translation bundle
```

## 8. Validating conformance

```
> saipen validate
Agent: runs tools/validate.py
       checks STATE/BOARD/LOG/CORE agreement
       fixes structural shape only (never content)
       reports PASS or lists FAILs
```

## 9. Validator linting (v7.99.0+)

The validator itself (1418 lines) had never been linted before v7.99.0. First run found 9 cp1251-mangled section signs inside its own FAIL messages — valid UTF-8, invisible to its own U+FFFD check. CI now runs `ruff`.

## 10. Push-claim verification (v7.99.0+)

A `next_action` claiming "shipped, committed, pushed" while commits sit local-only now FAILs. The repository itself holds the answer. Caught v7.98.0 shipping with three uncommitted CI changes.

## 11. Fixture-based validation (v7.100.0+)

5 key failure modes have standing fixtures with pinned failure reasons. `tools/validate.py` has 93 failure paths — a fixture proves each one still fires.

The portable floor is also fixtured: `tools/audit_floor.py` breaks a scratch project 20 different ways and asserts both `validate.sh` and `validate.ps1` report each specific failure. Both halves proven red. First run exposed a wording divergence — aligned. On Windows the floor adds Git's `usr/bin` to the child PATH only — a directly launched Git Bash otherwise inherits a PATH without `grep`/`sed`/`sort` (v7.127.0).

## 12. SHIP preflight repair (v7.128.0+)

SHIP requires 100% green, but a fixable failure found before commit used to have no legal way back to BUILD.

```
> saipen ship
Agent: preflight -> validator FAIL (injector bug, fix known)
       SHIP -> BUILD (narrow edge, current ticket only)
       BUILD -> VERIFY -> REVIEW -> SHIP (repeat all gates)
       commit, push branch, push exact refs/tags/vVERSION
```

Publish failures and already-pushed work never return to BUILD. Release order is explicit: prepare VERSION/README/CHANGELOG → rerun validators against that metadata → commit → push.

## 13. Shortcut shorthand (v7.148.0+)

Each key has one exact assignment; repetition is not an effort level:

```
gg   -> saipen goal       (new objective; bare gg prints usage)
hh   -> saipen hunt       (run the defect/improvement sweep now)
cc   -> saipen continue   (resume; under converge, continue the target)
sss  -> saipen status     (reports without touching code)
ss   -> saipen stop       (checkpoint, then halt)
ccc  -> continue + shipping chain (the one that pushes)
dd   -> saipen plan
aa   -> saipen markhunt
ee   -> prepare the complete translation package; never integrate or push
eee  -> collect a ready translation package + gates + push; otherwise run ee
qq   -> prepare the complete wiki package; never integrate or push
qqq  -> collect a ready wiki package + gates + push; otherwise run qq
pp   -> spawn/adopt saipython
tt   -> run the declared test suite
sc   -> run the serial full-platoon crew circuit
```

Length has no global cost or routing meaning; only the declared row counts, so `ppp` is not inferred. Cyrillic twins work too — `сс`, `ссс`, `аа`, `ее`, `еее`, `рр` normalize through the confusable set before matching. The full 15-key table lives in [CORE § 1.10](https://github.com/vacterro/saipen/blob/main/saipen/CORE.md#110-command-surface).

## 14. Preparing two producers safely (v7.226.0+)

Run translation and wiki preparation as separate isolated jobs when the host supports it:

```text
ee -> saitranslate lock/epoch/staging -> READY
qq -> saiwiki      lock/epoch/staging -> READY
```

They may overlap because their namespaces and locks differ. Two jobs for the same producer serialize. A producer writes only its own namespace and cannot collect, integrate, commit, tag, or push. Core later revalidates exact dependency hashes and integrates one named READY package; stale input means prepare again, never auto-rebase.

## WAIT category cheat sheet

| next_action | Means | What agent does |
|---|---|---|
| `WAIT: manual-verify -- test the export feature` | Human must test | Reports to human, waits |
| `WAIT: blocked -- T-4 needs T-2 which is not done` | Dependency stuck | Skips, works other tickets |
| `WAIT: user brake -- check if this design is right` | Human paused | Stops, writes digest |
| `WAIT: safety valve -- 3 waves completed, re-invoke saipen goal` | Caps hit | Stops, requires re-auth |
| `WAIT: first-publish -- confirm repo name and visibility` | First push | Asks human, one-way door |

## ДED Voice

> "Tutorial? Одна команда — и работает. Не надо ничего настраивать. Не надо ничего объяснять. Просто saipen set — и всё. Потом saipen goal — и агент сам делает. Хочешь остановиться? saipen stop. Хочешь продолжить? saipen continue. Четыре команды — и ты управляешь проектом. Остальное агент делает сам."
