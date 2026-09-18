# RAPORT — SAIPEN guard restart-loop / fresh-install bricks live sessions

- **Report id:** RAPORT-SAIPEN-GUARD-RESTART-20260918
- **Date:** 2026-09-18
- **Reporter:** agent `buffy` (SAIPEN seat inherited from project STATE), host opencode (`SAIFREN`)
- **Reporter project:** `V:\___VAC\__K\__CODE\_PY\_SAIPENVIEW`
- **Project lineage:** `lineage-3d3c3d12923e46d5808f1545a72e3c6c`
- **Protocol version (all homes):** 8.0.1
- **Observed runtime home:** `C:\Users\vac34\.config\opencode\skills\saipen`
- **Guard plugin:** `C:\Users\vac34\.config\opencode\plugins\saipen-guard.js`
- **Defect class:** `guard-runtime-freshness-race` + `refusal-without-route` (SRC-053 family)
- **Severity:** P1

## 0. TL;DR

The guard plugin enforces a **loaded-vs-installed module hash freshness gate**. When
the bytes of the guard file change under a live OpenCode process, every
consequential tool (`bash`, `write`, `edit`) is refused for the whole session with:

```
SAIPEN_GUARD_REFUSAL: PLUGIN_RESTART_REQUIRED: loaded build=... sha256=<A>;
installed sha256=<B>; restart OpenCode; the host tool did not execute
```

Three defects compose into a bootstrap dead-end:

1. **The refusal has no canonical route.** Unlike every other refusal this runtime
   prints, `PLUGIN_RESTART_REQUIRED` carries **no `next:` line**. Its only stated
   fix is a host restart. There is no `saipen` verb to clear it, and the guard
   refuses the tools a session would need to record it.
2. **The protocol's own installer causes the byte change.** A scheduled injector
   runs every 15 minutes and writes the guard file from a second source tree.
   Live sessions therefore get bricked by SAIPEN's own background job, not by an
   operator action.
3. **The reported loaded/installed pair is non-deterministic (TOCTOU race).** In
   this field session the guard reported `loaded=a056…; installed=67087339…`,
   yet the on-disk plugin file was `a056…` at the time the refusal was written.
   Independent startup diagnostics captured from sibling processes in the same
   wall-clock second show **both** byte-generations loaded from the same path —
   proof that a concurrent writer rewrites the live module.

No `saipen defects` verb exists in 8.0.1 (returns `RUNTIME_DRIFT`), so this
failure has no first-class incident channel (`SRC-053` unimplemented). This
report and its mirrored packet use the `SRC-053` shape by hand.

---

## 1. Observed evidence (files and live commands, not memory)

### 1.1 The refusal itself (first tool call of the session)

`bash git status --short` (2026-09-18, project `_SAIPENVIEW`, phase `DONE`, no DOING):

```
SAIPEN_GUARD_REFUSAL: PLUGIN_RESTART_REQUIRED: loaded build=T-1327-zero-manual-recovery-20260914.1
sha256=a0562237015830e69d794a2e84043e8fd1d21c51030d8a9a3d0a1e01017b6743;
installed sha256=67087339d5e03f59deca9c275e34cb204dfeefdcf3be7c5943f66938a58ddd23;
restart OpenCode; the host tool did not execute
```

`write` (any path) and `edit` returned the identical refusal. Only the exact
read-only fast-path tools (`read`, `glob`, `grep`, `todowrite`, …) were admitted.

### 1.2 The same module has two live byte-generations on disk

```
hash (sha256, first 16)   mtime                 path
a0562237015830e6          2026-09-17 19:01:10   C:\Users\vac34\.config\opencode\plugins\saipen-guard.js
a0562237015830e6          2026-09-17 19:01:10   C:\Users\vac34\.config\opencode\skills\saipen\extensions\adapters\opencode\saipen-guard.js
a0562237015830e6          2026-09-17 19:01:10   C:\Users\vac34\.agents\skills\saipen\extensions\adapters\opencode\saipen-guard.js
a0562237015830e6          2026-09-17 19:01:10   V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\extensions\adapters\opencode\saipen-guard.js
67087339d5e03f59          2026-09-17 16:32:24   C:\Users\vac34\AppData\Local\saipen\scheduled-source\extensions\adapters\opencode\saipen-guard.js
```

Both files declare the **same** `BUILD_ID` (`T-1327-zero-manual-recovery-20260914.1`),
so the build label cannot distinguish them — only the hash can. `67087339…` is
the scheduled-source generation; `a0562237…` is the clone/skills/plugin
generation.

### 1.3 Two generations loaded from one path in the same second

OpenCode writes one bounded per-process startup diagnostic under the temp root.
Collected on this host:

```
pid     module_sha256 (first 16)   factory_started_ms
30464   a0562237015830e6           1789728385828
6464    a0562237015830e6           1789728385265
22996   a0562237015830e6           1789728387285
27348   a0562237015830e6           1789728387746
9508    67087339d5e03f59           1789728390856
15580   67087339d5e03f59           1789728393140
```

All carry `module_path = C:\Users\vac34\.config\opencode\plugins\saipen-guard.js`.
Two different byte-generations were read from **the same path** within roughly
one second. A file cannot be two things at once; a concurrent writer rewrote it.

### 1.4 The background writer refuses to converge

`%LOCALAPPDATA%\saipen\inject.log`, 2026-09-18 runs:

```
=== saipen scheduled inject run=b277231838f241de902c73e4846b067d ===
surface: bootstrap bootstrap/inject.ps1 ... tools/validate.py VERSION
dirty:  M bootstrap/inject.ps1
dirty:  M bootstrap/inject.sh
dirty:  M extensions/adapters/opencode/saipen-guard.js
dirty:  M tools/saipen_engine/admission.py
dirty:  M tools/saipen_engine/entry.py
dirty:  M tools/saipen_engine/runtime_bootstrap.py
dirty:  M tools/test_t1326_board_compaction.py
SKIP: DIRTY_SOURCE
=== end rc=2 ===
```

Every scheduled run exits `rc=2 SKIP: DIRTY_SOURCE`. The install is frozen at a
dirty generation and can never self-heal, while `saipen status` reports
`"distribution": {"installed": 6, "stale": 5, "unknown": 6, "fresh": false,
"blocked": "DIRTY_SOURCE"}`.

### 1.5 No canonical incident channel

```
saipen defects list --json
REFUSE [RUNTIME_DRIFT]
reason: command 'defects' is not implemented by this runtime, and this project's
saipen_home points at a DIFFERENT SAIPEN install ...
```

`SRC-053` (CENTRAL PROTOCOL INCIDENT INBOX) is registered in the home but
explicitly not implemented; `%LOCALAPPDATA%\saipen\protocol_incidents\` exists
only because prior reports hand-mirrored the packet.

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

This is a **TOCTOU comparison**: `MODULE_PATH` is rewritten by an external
process between module load and tool call, and the gate then blocks all effects
with a host-restart demand and **no `next:` command**. The refusal string in
2.1 is the only one in the guard that omits the canonical `next:` route
contract (compare the `admission.py` refusals, which all print a route).

### 2.2 The writer — the installer/injector schedule

`bootstrap/inject.ps1` / `bootstrap/inject.sh` copy the guard into the global
plugin directory. A scheduled task
(`%LOCALAPPDATA%\saipen\schedule-run-hidden.vbs`, `inject.log`) runs it every
15 minutes. When the source tree is clean it rewrites the plugin file; that is
the byte change the freshness gate detects. So the protocol's own distribution
mechanism is what bricks live sessions.

The `DIRTY_SOURCE` guard (§1.4) is the intended protection against installing a
dirty tree, but it is *also* what leaves the fleet permanently stale — the
scheduled-source clone carries modifications that never clear, so the injector
can neither converge nor be bypassed legally.

### 2.3 No route out — `admission.py` / `REGISTRY.json`

`PLUGIN_RESTART_REQUIRED` is produced in the JS adapter, not by the Python
admission engine, so it never passes through the `_BRAKE_ROUTES` /
refusal-route machinery (`admission.py:682`) that guarantees every other
refusal names the single command that lifts it. This is the `SRC-053` trigger
verbatim: *"guard blocks the only engine-required repair path"*.

---

## 3. Deterministic reproduction

Preconditions: Windows, OpenCode, SAIPEN installed with a scheduled injector;
any bound project.

1. Start an OpenCode session in the project (guard loads, captures
   `LOADED_SHA256 = A`).
2. Externally overwrite `%CONFIG%\opencode\plugins\saipen-guard.js` with any
   other generation `B` (here: run `bootstrap/inject.ps1`, or drop the
   `scheduled-source` copy in place).
3. Call any consequential tool (`bash`, `write`, `edit`).
4. Observe:

```
SAIPEN_GUARD_REFUSAL: PLUGIN_RESTART_REQUIRED: loaded build=... sha256=A; installed sha256=B;
restart OpenCode; the host tool did not execute
```

and no `next:` route. `read`/`grep`/`glob` still work.

Expected: the refusal either (a) names one executable `saipen` route that
re-binds the session to the installed generation, or (b) is downgraded to
`ADVISORY` for generations that differ only in distribution provenance, or
(c) the installer never rewrites a live module — the change is staged and
applied at host start.

Actual: hard block, host-restart-only, no canonical route; and because
`saipen defects` is unimplemented, the blocked session cannot even record the
incident through the protocol.

### Minimal, race-free variant (from §1.3)

Hold two processes that load the same path while a third rewrites it; their
startup diagnostics show two different `module_sha256` values with an identical
`module_path`. This proves the race without needing to observe the refusal
window.

---

## 4. Impact

- Any Windows OpenCode session whose guard file is rewritten mid-flight loses
  `bash`/`write`/`edit` until manual host restart. Automated/scheduled installs
  make that a recurring, unattended event.
- The refusal cannot be recorded through the protocol: no `saipen defects`, and
  the tools that would write the report are the ones refused.
- `DIRTY_SOURCE` freeze + 5/6 stale homes means the fleet cannot converge; the
  freshness gate therefore keeps firing across the fleet.
- Non-determinism: the loaded/installed pair can invert (loaded matches disk,
  installed does not), so the diagnostic in the refusal is not trustworthy for
  triage — another reason the incident needs a first-class packet.

---

## 5. Suspected owner

- `extensions/adapters/opencode/saipen-guard.js` — the `LOADED_SHA256`/
  `PLUGIN_RESTART_REQUIRED` gate and its missing `next:` route.
- `bootstrap/inject.ps1`, `bootstrap/inject.sh` and the scheduled task — live
  module rewrite and the `DIRTY_SOURCE` stall.
- `saipen_engine/admission.py` — route contract for refusals emitted outside the
  Python engine.
- `SRC-053` — the still-unimplemented canonical incident channel.

## 6. Repair candidates (non-binding; maintainer decides)

1. Give `PLUGIN_RESTART_REQUIRED` a canonical route: a read-only
   `saipen status --json` or a dedicated `saipen rebind-home`/`saipen rebind`
   that re-verifies the installed generation and admits consequence against the
   live module, instead of a bare host-restart demand.
2. Make the installer atomic w.r.t. live processes: write to a new
   generation-named file and repoint, or defer module replacement to host start,
   so a scheduled install never mutates the loaded path.
3. Distinguish "different runtime generation" from "same generation, different
   distribution provenance" before refusing; `BUILD_ID` is identical here, so a
   spurious refusal is possible whenever only whitespace/provenance differs.
4. Implement `SRC-053` so this class has a first-class route regardless.

## 7. Related

- `RAPORT-SAIPEN-GUARD-20260917` (home `.saipen/evidence/`) — backslash path
  drops the canonical-operation exemption; same refusal family.
- `SAI-DEFECT-20260917-wintage-guard-filepath` (protocol_incidents/inbox).
- `audit/18.md`, `audit/19.md` (home) — one-DOING gate and
  state-history-binding deadlock; the "refusal with no route" family.
- Wintage `E-1041` — `SOURCE_RECEIPT_MISSING` outside `REGISTRY.json`; a refusal
  code with no registered route.

— end of report —
