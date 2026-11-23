# RAPORT — SAIPEN guard: two producers, one plugin path, and a read-only probe gap

- **Report id:** RAPORT-SAIPEN-GUARD-PRODUCER-DIVERGENCE-20260918
- **Date:** 2026-09-18
- **Reporter:** agent `opencode` (SAIPEN seat inherited from project STATE), host opencode (`SAIFREN`)
- **Reporter project:** `V:\___VAC\__K\__CODE\_PY\_LIMISAW`
- **Project lineage:** `lineage-a41c0e3a81534f02a4cc4520a399cca6`
- **Protocol version (all homes):** 8.0.1
- **Observed runtime home:** `C:\Users\vac34\.config\opencode\skills\saipen`
- **Bound saipen_home (project):** `C:\Users\vac34\AppData\Local\saipen\scheduled-source`
- **Protocol home (source):** `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`
- **Guard plugin:** `C:\Users\vac34\.config\opencode\plugins\saipen-guard.js`
- **Defect classes in this report:** 2 (dual-producer artifact divergence / read-only probe set gap)
- **Severity:** P1

## 0. TL;DR

Measured live this session on protocol 8.0.1:

1. **Two byte-different guard artifacts exist under one `BUILD_ID`**, produced by
   two different source trees, and both are written to the single global plugin
   path `~/.config/opencode/plugins/saipen-guard.js`. The live module's hash
   therefore flips, and the guard's own freshness gate refuses every
   consequential tool with a **route-less** `PLUGIN_RESTART_REQUIRED`.
2. **The guard's closed read-only shell-probe verb set is incomplete on
   Windows/PowerShell.** `Get-Location`, `whoami`, `hostname`, `Get-Date` are
   provably read-only, are not in `_READ_ONLY_SHELL_VERBS`, and are refused
   `NO_ACTIVE_WORK` in a `phase: DONE` project with no `## DOING` Work — the same
   "one question, two answers" class `guard_events.py`'s own T-1363 comment says
   it closed (native `read` is admitted; the equivalent probe is not).

A sibling report, `RAPORT-SAIPEN-GUARD-RESTART-20260918` (home
`.saipen/evidence/`, untracked at this HEAD), and its protocolist packet
`SAI-DEFECT-20260918-saipenview-guard-restart` (inbox) already cover the restart
gate and its missing route. **This report does not file a duplicate packet for
that class** (SRC-053: do not create twenty reports for one defect). It (a) adds
the measured dual-producer hash table with sizes and the byte/mtime provenance
that names the two producers, and (b) files one packet for the independent
read-only verb gap, which no prior report covers.

---

## 1. Observed evidence (files and live commands, not memory)

### 1.1 The refusal — first consequential tool call of the session

`bash echo probe` (2026-09-18, project `_LIMISAW`, `phase: DONE`,
`task: none`, no `## DOING`):

```
SAIPEN_GUARD_REFUSAL: PLUGIN_RESTART_REQUIRED: loaded build=T-1327-zero-manual-recovery-20260914.1
sha256=a0562237015830e69d794a2e84043e8fd1d21c51030d8a9a3d0a1e01017b6743;
installed sha256=67087339d5e03f59deca9c275e34cb204dfeefdcf3be7c5943f66938a58ddd23;
restart OpenCode; the host tool did not execute
```

No `next:` route is present. `read`/`glob`/`grep`/`skill`/`question` were admitted
throughout (the adapter's identity-scoped fast path, `saipen-guard.js:91-113`).

### 1.2 Two byte-generations under one BUILD_ID, in two source trees

```
sha256 (full)                                                        bytes   mtime (UTC)          path
a0562237015830e69d794a2e84043e8fd1d21c51030d8a9a3d0a1e01017b6743   36500   2026-09-17T16:01:10Z   C:\Users\vac34\.config\opencode\plugins\saipen-guard.js
a0562237015830e69d794a2e84043e8fd1d21c51030d8a9a3d0a1e01017b6743   36500   2026-09-17T16:01:10Z   C:\Users\vac34\.config\opencode\skills\saipen\extensions\adapters\opencode\saipen-guard.js
a0562237015830e69d794a2e84043e8fd1d21c51030d8a9a3d0a1e01017b6743   36500   2026-09-17T16:01:10Z   V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\extensions\adapters\opencode\saipen-guard.js
67087339d5e03f59deca9c275e34cb204dfeefdcf3be7c5943f66938a58ddd23   35954   2026-09-17T13:32:24Z   C:\Users\vac34\AppData\Local\saipen\scheduled-source\extensions\adapters\opencode\saipen-guard.js
```

Both declare `BUILD_ID = "T-1327-zero-manual-recovery-20260914.1"`
(`saipen-guard.js:54` in every copy). The build label cannot distinguish them;
only the hash can. `a0562237…` (36500 B) is the **clone/skill** generation;
`67087339…` (35954 B) is the older, smaller **scheduled-source** generation.

### 1.3 The live path oscillated between the two generations

- Refusal 1.1 reported `loaded=a0562237…`, `installed=67087339…` — the module
  had been loaded from the `a056` bytes and the on-disk file was `67087339…`
  at tool-call time.
- `Get-FileHash` of the same live path moments later returned
  `A0562237015830E6…` — the file was back to `a056`.

The one path served two different byte-generations during one session. A file
cannot be two things at once; a concurrent writer rewrote it. (This matches the
independent sibling measurement in `RAPORT-SAIPEN-GUARD-RESTART-20260918` §1.3,
where two sibling OpenCode processes loaded two different `module_sha256` values
from the same `module_path` within ~1 second.)

### 1.4 Two producers, one destination

- **Producer A — clone/skill tree:** source
  `V:\...\_SAIPEN\extensions\adapters\opencode\saipen-guard.js` →
  installed `~/.config/opencode/skills/saipen/extensions/...` and
  `~/.config/opencode/plugins/saipen-guard.js`. Bytes `a0562237…` (36500 B).
  Both installed copies carry the same mtime `2026-09-17T16:01:10Z`.
- **Producer B — scheduled-source tree:**
  `C:\...\Local\saipen\scheduled-source\extensions\adapters\opencode\saipen-guard.js`.
  Bytes `67087339…` (35954 B), mtime `2026-09-17T13:32:24Z` — 2.5 h older.

The host adapter registry declares **one** hook surface and **one** artifact:
`extensions/adapters/registry.json` (`"hook_install_surface":
"~/.config/opencode/plugins/saipen-guard.js"`, `"hook_artifact":
"extensions/adapters/opencode/saipen-guard.js"`). Two trees own byte-different
copies of that single artifact, so whichever producer injects last wins — and the
other producer's next write flips the live hash again.

### 1.5 The background injector cannot converge (context, not this report's core)

`%LOCALAPPDATA%\saipen\inject.log`, 2026-09-18 runs:

```
surface: bootstrap ... tools/validate.py VERSION
dirty:  M bootstrap/inject.ps1
dirty:  M bootstrap/inject.sh
dirty:  M extensions/adapters/opencode/saipen-guard.js
dirty:  M tools/saipen_engine/admission.py
dirty:  M tools/saipen_engine/entry.py
SKIP: DIRTY_SOURCE
=== end rc=2 ===
```

Every scheduled run exits `rc=2 SKIP: DIRTY_SOURCE`; `saipen status` reports
`"distribution": {"installed": 6, "stale": 5, "unknown": 6, "fresh": false,
"blocked": "DIRTY_SOURCE"}`. The scheduled-source generation is frozen 2.5 h
behind the clone, so the divergence in §1.2 is durable, not transient.

### 1.6 The refusal route contract is missing for this code

`admission.py` guarantees every protocol-state refusal names the single command
that lifts it (`_BRAKE_ROUTES`, `admission.py:670-678`; `snapshot["route"] =
ENTRY_COMMAND`, `admission.py:781`). `PLUGIN_RESTART_REQUIRED` is produced in the
JavaScript adapter (`saipen-guard.js:623-628`), never passes through the Python
`protocol_snapshot` route machinery, and carries no `next:` — the only stated fix
is a manual host restart.

### 1.7 The read-only probe gap (independent defect)

`guard_events.py:1137-1179` defines `_READ_ONLY_SHELL_VERBS`, the closed set that
decides `provably_read_only_shell` (line 1207). Measured matrix in the same
`DONE`/no-`## DOING` project, this session:

| command | admitted? | reason |
|---|---|---|
| `echo testA` | yes | `echo` ∈ set (line 1165) |
| `git rev-parse HEAD` | yes | `git` + read-only subcommand (`_READ_ONLY_GIT`) |
| `Get-FileHash <path> -Algorithm SHA256 …` | yes | `get-filehash` ∈ set (line 1163) |
| `whoami` | **no — `NO_ACTIVE_WORK`** | not in set |
| `hostname` | **no — `NO_ACTIVE_WORK`** | not in set |
| `Get-Date -Format o` | **no — `NO_ACTIVE_WORK`** | not in set |
| `Get-Location \| Select-Object -ExpandProperty Path` | **no — `NO_ACTIVE_WORK`** | `get-location` not in set (`pwd` is, line 1173) |

`whoami`, `hostname`, `Get-Location`, `Get-Date` cannot mutate the project. They
fall through to `action = "shell"` (`guard_events.py:1304-1305`), and
`admission.py:778-786` refuses ordinary shell effects `NO_ACTIVE_WORK` when
`## DOING` is not exactly one Work. This is the same class the T-1363 comment at
`guard_events.py:1128-1136` describes — "One question, two answers" — reopened
for every read-only verb that was left out of the closed set. (`pwd` is included;
its PowerShell spelling `Get-Location` is not.)

---

## 2. Root cause (exact sources)

### 2.1 The freshness gate — `extensions/adapters/opencode/saipen-guard.js`

Module evaluation captures the loaded bytes once (line 80):

```js
const LOADED_SHA256 = sha256(fs.readFileSync(MODULE_PATH));
```

Every consequential tool re-reads the file and compares (lines 619-629):

```js
let installedSha256;
try { installedSha256 = sha256(fs.readFileSync(MODULE_PATH)); } catch (_error) {
  installedSha256 = "missing";
}
if (installedSha256 !== LOADED_SHA256) {
  throw new Error(
    `SAIPEN_GUARD_REFUSAL: PLUGIN_RESTART_REQUIRED: loaded build=${BUILD_ID} ` +
      `sha256=${LOADED_SHA256}; installed sha256=${installedSha256}; ` +
      `restart OpenCode; the host tool did not execute`,
  );
}
```

This is a TOCTOU comparison against a path that external writers rewrite. It
blocks all effects with a host-restart demand and no `next:` route (§1.6).

### 2.2 The writers

`bootstrap/inject.ps1` / `bootstrap/inject.sh` copy the guard into the global
plugin directory from the source tree they run in. The scheduled task
(`%LOCALAPPDATA%\saipen\schedule-run-hidden.vbs` → `bootstrap\schedule-run.ps1`)
runs the injector from a published `scheduled-source` snapshot; a separate
launch/resync path injects from the clone/skill tree. Two producers, one plugin
path → the hash flip in §1.3. The `DIRTY_SOURCE` guard (§1.5) is intended to
prevent publishing an edited tree, but it is also what freezes the
scheduled-source generation, so the divergence never self-heals.

### 2.3 No route out

`PLUGIN_RESTART_REQUIRED` never reaches `admission.py`'s `_BRAKE_ROUTES`
(`admission.py:670-678`) because it is emitted in JS. This is the `SRC-053`
trigger verbatim: *"guard blocks the only engine-required repair path"*.

### 2.4 Read-only probe set

`_READ_ONLY_SHELL_VERBS` (`guard_events.py:1137-1179`) omits common Windows
read-only cmdlets. `provably_read_only_shell` (line 1207) is closed-set, so any
omitted verb loses the `read` class and pays the `NO_ACTIVE_WORK` brake in
`admission.py:778-786`.

---

## 3. Deterministic reproduction

Preconditions: Windows, OpenCode, SAIPEN installed with a scheduled injector;
any bound project at `phase: DONE` with no `## DOING` Work.

**Defect A — restart gate / producer divergence**

1. Confirm two generations on disk:
   `Get-FileHash ~/.config/opencode/plugins/saipen-guard.js` and
   `Get-FileHash ~/.config/opencode/skills/saipen/extensions/adapters/opencode/saipen-guard.js`
   vs `...\scheduled-source\extensions\adapters\opencode\saipen-guard.js`.
   Expect `a0562237…` (36500 B) vs `67087339…` (35954 B), same BUILD_ID.
2. Start an OpenCode session bound to the project (module loads, captures
   `LOADED_SHA256`).
3. Externally overwrite the live plugin path with the other generation (run
   `bootstrap/inject.ps1` from the other tree, or drop the copy in place).
4. Call any consequential tool (`bash`, `write`, `edit`).
5. Observe `PLUGIN_RESTART_REQUIRED` with no `next:` route; `read`/`grep`/`glob`
   still work.

Expected: the refusal names one executable `saipen` route that re-binds the
session to the installed generation, OR differing distribution provenance does
not trigger the gate, OR the installer never rewrites a live module.
Actual: hard block, host-restart-only, no canonical route.

**Defect B — read-only probe gap**

In the same `DONE`/no-`## DOING` project, run `whoami` (or `Get-Location`,
`Get-Date`, `hostname`) as an ordinary `bash` call. Expect `NO_ACTIVE_WORK`.
Run `echo ok` — admitted. Same read-only intent, two answers.

---

## 4. Impact

- Any Windows OpenCode session whose guard file is rewritten mid-flight loses
  `bash`/`write`/`edit` until manual host restart. Scheduled installs make this a
  recurring, unattended event.
- The refusal cannot be recorded through the protocol: `saipen defects` is
  unimplemented (returns `RUNTIME_DRIFT`), and the tools that would write the
  report are the ones refused — the `SRC-053` dead-end.
- The reported `loaded`/`installed` pair is non-deterministic when the writer
  races the reader (§1.3), so the refusal's own diagnostics are not trustworthy
  for triage.
- Read-only probes (`whoami`, `Get-Location`, …) are refused in an idle project,
  reopening the "one question, two answers" class T-1363 claims closed.
- `DIRTY_SOURCE` freeze + 5/6 stale homes means the fleet cannot converge, so the
  freshness gate keeps firing across the fleet.

---

## 5. Suspected owner

- `extensions/adapters/opencode/saipen-guard.js` — the `LOADED_SHA256` /
  `PLUGIN_RESTART_REQUIRED` gate and its missing `next:` route.
- `bootstrap/inject.ps1`, `bootstrap/inject.sh`, `bootstrap/schedule-run.ps1` —
  live module rewrite and the `DIRTY_SOURCE` stall.
- `tools/saipen_engine/guard_events.py` — `_READ_ONLY_SHELL_VERBS` closed set.
- `saipen_engine/admission.py` — refusal route contract for JS-emitted codes.
- `SRC-053` — the still-unimplemented canonical incident channel.

---

## 6. Repair candidates (non-binding; maintainer decides)

1. Give `PLUGIN_RESTART_REQUIRED` a canonical route (a read-only `saipen status
   --json` or a dedicated `saipen rebind`/`saipen rebind-home` that re-verifies
   the installed generation and admits consequence against the live module).
2. Make the installer atomic w.r.t. live processes: write a
   generation-named file and repoint, or defer module replacement to host start.
3. Enforce one producer for the hook artifact, or make injection compare
   provenance before overwriting; distinguish "different runtime generation"
   from "same generation, different distribution provenance" before refusing
   (BUILD_ID is identical here).
4. Add the missing provably-read-only Windows cmdlets to
   `_READ_ONLY_SHELL_VERBS` (`whoami`, `hostname`, `get-location`, `get-date`,
   `get-command`, …), so a read-only probe gets one answer.
5. Implement `SRC-053` so this class has a first-class route regardless.

---

## 7. Related

- `RAPORT-SAIPEN-GUARD-RESTART-20260918` (home `.saipen/evidence/`, untracked) and
  its packet `SAI-DEFECT-20260918-saipenview-guard-restart` (inbox) — same restart
  gate; this report adds the producer-divergence provenance and does not refile it.
- `RAPORT-SAIPEN-GUARD-20260917` (home `.saipen/evidence/`) — backslash path drops
  the canonical-operation exemption; same refusal family.
- `SAI-DEFECT-20260917-wintage-guard-filepath` (protocol_incidents/inbox).
- `audit/18.md`, `audit/19.md` (home) — one-DOING gate and state-history-binding
  deadlock; the "refusal with no route" family.

---

## 8. Side effects disclosed (this session)

- One protocolist packet was written to
  `%LOCALAPPDATA%\saipen\protocol_incidents\inbox\SAI-DEFECT-20260918-guard-readonly-probe-gap.md`
  (Defect B only; Defect A is already filed as
  `SAI-DEFECT-20260918-saipenview-guard-restart`).
- No canonical project file was hand-edited; no event was fabricated.
- Every command cited above was read-only; the only writes are this report and the
  packet.

— end of report —
