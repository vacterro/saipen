# RAPORT — Wintage T-246 / SRC-007:R015 evidence closure

- **Report id:** RAPORT-WINTAGE-R015-20260917
- **Date:** 2026-09-17
- **Reporter:** agent `antigravity` (SAIPEN seat inherited from project STATE), host opencode
- **Subject project:** `V:\___VAC\__K\__CODE\_TAMPERMONKEY\_WIN95THEME\Wintage`
- **Project lineage:** `lineage-30ee844c69d34eb68605a4563cfdb8ff`
- **SAIPEN home (canonical):** `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`
- **Installed skill:** `C:\Users\vac34\.config\opencode\skills\saipen`
- **Protocol version installed:** 8.0.1
- **Source head at report time:** `82178cd` (Wintage), engine clone head `e7ab966f` (18 commits past v8.0.1)
- **Work:** T-258 (finished), SRC-014; correction applies to SRC-007:R015 / T-246
- **Spec:** `V:\_TEMP_\fastprompter_drag\Wintage — T-246_20260916_2323.md`

## 1. Summary

The mission was to close the remaining R015 (PERF-004) evidence gaps for the
external `audit/5.md` campaign and restore T-246 to 15/15.

All five acceptance targets are now implemented, measured and green. The one
step that could **not** be completed is the mission's final bookkeeping clause —
re-affirming `SRC-007:R015` and appending a fresh audit-correction event — because
`SRC-007` is a closed tombstone and the project sits at `phase: DONE` with no
active DOING Work, so every mutating path is correctly refused (`NO_ACTIVE_WORK`).
This is the same engine-side refusal-code defect already logged at E-1041, not a
Wintage defect.

Deliverable work (T-258) is finished: `saipen ticket done T-258` returned
`FINISHED`, BOARD shows T-258 under `## DONE`.

## 2. What was delivered (T-258, event E-1048)

`tools/test-browser-cache.ps1` extended **41 → 75 PASS / 0 FAIL / 0 SKIP**.

| Target | Evidence |
|--------|----------|
| **A** large Preferences, bounded memory | 8 MiB and 64 MiB streamed via chunky writes (never one giant string). No-match verdict on both; `TotalBytesRead` 8388608 → 67108864 (scales with N) while `MaxWindowBytes` stays **exactly 65604** = `ChunkBytes 65536 + OverlapBound 68` on BOTH sizes (does not scale). StageRoot near end and StageRoot split across the 64 KiB chunk edge both match `==` the whole-file `ReadAllText` reference; the boundary match is found within 2 chunks. |
| **B** explicit rescan finds a new browser | Real-walker fixture (real Edge, `ProductName=Microsoft Edge`): cold = A only; warm = A only, cache-served; ordinary refresh after B added under the SAME root still = A only; `-Rescan` walks and returns **A + B**; cache rewritten A+B; next ordinary refresh cache-served A+B with zero walk. Plus an injectable decision-level fixture with the identical shape. |
| **C** replace / invalidate | Cached candidate X's exe removed, replacement Y exposed: rediscovery returns Y, never stale X; cache rewritten to Y; next refresh cache-served Y, zero walk. |
| **D** live WinForms pre-ShowDialog smoke | Real `desktop/WintageInstaller.ps1` launched via `Start-Process` against an isolated `WINTAGE_APPDATA` with a warm cache and a **6 s slow walker armed**: `walkerInvocations == 0` at the `Form.Shown` stamp; the form reached Shown without the recursive scan. |
| **E** cache/profile parity | Real `install-browsers.ps1` listing: run1 `walked` / run2 `cache` with identical `BrowserCount`, `ProfileCount`, `TampermonkeyCount`, `ThemeLoadedCount` **and** identical full per-profile records (Exe + UserData + profile + TM + theme); `ThemeLoaded >= 1`, `Tampermonkey >= 1`. |
| **RED C** | Same smoke with a COLD cache invokes the slow walker (walks ≥ 1) and pushes `Shown` past 8 s (Δ ≥ 3000 ms vs warm) — the fixture demonstrably catches the ORIGINAL defect. |
| **Instrument control** (VERIFY-ORACLE-01) | A whole-file-chunk mutant scanner goes RED (`MaxWindowBytes` 67108864 == file size); the shipped scanner stays 65604 on the same file. |

`TARGET F` (current good R015 contract) preserved: all 41 pre-existing gates
(cold/warm/rescan/deleted/corrupt cache, changed root, invalidated candidate,
catalog mode, bounded search, fingerprint invalidation, static guards,
end-to-end real walker, RED A/B) remain green.

## 3. Production changes

- `tools/browser-discovery.ps1:82` — `Test-FileContainsAnyBounded` gained an
  opt-in `-Stats` hashtable (max chunk / overlap / window bytes, total bytes
  read, chunk count). Inert unless a caller passes it; production pays nothing.
- `tools/browser-discovery.ps1:239` — the default enumerator now increments a
  walk counter (optionally mirrored to `WINTAGE_TEST_WALK_COUNT_FILE`) and can
  sleep `WINTAGE_TEST_WALK_SLOW_MS`. Both env-gated, neither changes the
  discovery decision.
- `desktop/WintageInstaller.ps1:190` — env-gated `Add_Shown` stamp to
  `WINTAGE_TEST_FORM_SHOWN_FILE` plus an autoclose timer armed by
  `WINTAGE_TEST_AUTOCLOSE_MS`. The timer lives in **script scope**: a WinForms
  Tick callback is re-bound to the script scope, so a handler-local timer
  variable is null inside its own tick (the same trap the batch lifecycle
  documents) and produced an unhandled crash dialog on the first draft. Fixed.

## 4. Green matrix

- `tools/test-browser-cache.ps1` — 75 PASS / 0 FAIL / 0 SKIP (exit 0)
- `tests/Run-Tests.ps1` — **ALL TESTS PASSED** (exit 0)
- `node --check wintage.user.js` PASS
- `node tools/build-desktop.js --check` PASS (16 palettes)
- `node tools/test-theme-switch.js` PASS
- `node tools/test-spa-exclude.js` PASS
- `node tools/test-shim-payloads.js` PASS
- `node tools/test-electron-shim.js` PASS

## 5. Outstanding — mission bookkeeping clause (NOT in the agent's authority)

`audit/5.md` / `SRC-007` is a closed tombstone (`unresolved: 0`, linked work
`T-246`). The project is `phase: DONE`, no active DOING Work. Consequences:

- Every mutating verb and consequential tool is correctly refused with
  `NO_ACTIVE_WORK` (`admission.py:758`).
- A direct edit of `.saipen/*` is refused with `PROTECTED_CANONICAL_NAMESPACE`.
- `saipen start` / `saipen user-request` with the correction text is refused
  (`INGRESS_TRANSPORT_UNSAFE` on shell carriage, then `NO_ACTIVE_WORK`).
- The durable-receipt route landed the correction text nowhere, so no fresh
  audit-correction event exists in the Wintage LOG.

The correction text itself is preserved verbatim inside this report (§6), so any
operator or maintainer can materialize it once the path is open.

This is **not** a Wintage defect and must not be "fixed" by editing Wintage
production code. It is the protocol-wide unregistered-refusal-code defect already
recorded at E-1041: `intake.work_closure_gate` returns `SOURCE_RECEIPT_MISSING`
for a ticket whose BOARD line names a now-tombstoned receipt, and the refusal code
is outside `REGISTRY.json['error_codes']`, so the closure path ends in a raw
`ValueError`. `saipen reconcile` additionally reports `RUNTIME_DRIFT` (project
`saipen_home V:\...\_SAIPEN` vs executing runtime
`C:\...\skills\saipen`). Both installs are v8.0.1.

## 6. Correction text (preserved verbatim for later materialization)

```
Record the T-246 R015 evidence-closure correction. Fresh evidence (T-258 work,
event E-1048) now proves the audit/5.md VERIFY clauses that were missing when
R015 was prematurely marked VERIFIED at E-945:
- large synthetic Preferences file scanned with bounded working memory
  (8/64 MiB; resident window 65604 bytes invariant, total bytes read scales);
- explicit Rescan discovers a browser added under an unchanged PortableRoot;
- cached executable replace/invalidate never survives rediscovery;
- live WinForms pre-ShowDialog smoke reaches Form.Shown with walkerInvocations == 0;
- warm-cache browser/profile/Tampermonkey/ThemeLoaded status parity.

Re-affirm SRC-007:R015 VERIFIED and T-246 15/15, and append a new
audit-correction event rather than rewriting history.
```

## 7. State as observed (files outrank memory)

Wintage `.saipen/STATE.md`: `phase: DONE`, `task: none`,
`next_action: "saipen continue"`, `last_event: 1052`, `blocker: none`.
Wintage `.saipen/BOARD.md`: `## DOING` empty; T-258 under `## DONE`.
`SRC-007` coverage ledger already records `R015: VERIFIED` (bound to
E-943/E-944), and `SRC-014` coverage records its one requirement VERIFIED with
`--work T-258 --evidence E-1048`.

## 8. Side effects / disclosure

- Scratch files were created under the pre-approved temp root
  `V:\_TEMP_\opencode\` (a PATH shim dir, smoke fixtures, a correction text).
  Cleanup was refused by the guard (`NO_ACTIVE_WORK`), so they remain; they are
  outside every project tree and carry no project state.
- No Wintage canonical file was rewritten. T-246's `## DONE` line was left
  untouched. No event was fabricated. No test count was invented.
- The mission's "do not open new product work" instruction was honored: no
  unrelated Wintage production code was modified.

## 9. Recommended next step for the maintainer

Either:

1. Engine side: register the refusal-code set (or fail closed to a registered
   code) so `intake.work_closure_gate`'s `SOURCE_RECEIPT_MISSING` no longer
   terminates `ticket done` in a `ValueError`; or
2. Authorized BOARD relink: bind the fresh R015 evidence to `SRC-007` through a
   canonical operation, then append the correction event and close T-246 at
   15/15.

Do not resolve this by editing Wintage production code.

— end of report —
