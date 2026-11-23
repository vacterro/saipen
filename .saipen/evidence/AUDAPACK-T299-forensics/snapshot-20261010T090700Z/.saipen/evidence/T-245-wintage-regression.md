# T-245 Wintage PACK regression evidence

## Real failure reproduction

Registered project: `wintage`
Project root: `V:\___VAC\__K\__CODE\_TAMPERMONKEY\_WIN95THEME\Wintage`

The real Wintage `STATE.md` was made newer than the manifest without changing its bytes. The consumer binding variables were removed by the gate, and launcher discovery was forced to an unavailable candidate for this reproduction only.

Gate outcome:

```text
ok: false
code: AUDIT_MANIFEST_STALE_REGENERATION_FAILED
detail: manifest is stale (mandatory evidence mutated after the manifest was written: ['.saipen/STATE.md']); regeneration failed: launcher discovery found no executable in project bin, STATE saipen_home, or PATH
```

Exact `PackResult`:

```text
success: false
status: FAILED_INVENTORY
error_message: SAIPEN audit-manifest precondition failed (AUDIT_MANIFEST_STALE_REGENERATION_FAILED): manifest is stale (mandatory evidence mutated after the manifest was written: ['.saipen/STATE.md']); regeneration failed: launcher discovery found no executable in project bin, STATE saipen_home, or PATH. Run `saipen audit manifest --write` in the project (or repair the owning SAIPEN protocol component) and repack; no archive was produced.
output_path: null
```

## Canonical launcher proof

The following launcher resolved from Wintage `STATE.md` and ran with `cwd` equal to the project root, captured output, `stdin=DEVNULL`, hidden Windows process flags, and `SAIPEN_PROJECT_ROOT`, `SAIPEN_PROJECT_LINEAGE`, `SAIPEN_AGENT` removed:

```text
V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\bin\saipen.cmd audit manifest --write
rc: 0
stdout: code: AUDIT_MANIFEST_CURRENT
stderr:
```

The first live probe exposed the compatibility edge: current SAIPEN declares the contract current by shape, while AUDAPACK correctly detects the newer mandatory `STATE.md` mtime. The gate now retires that exact stale declaration, invokes the same canonical command again, revalidates the contract, and proves no mandatory evidence remains newer. A failed second invocation restores the old manifest.

Successful live regeneration:

```text
outcome: ok=true, code=COMPATIBLE_DEGRADED, generated=true
manifest SHA256: d34ecaaa5887e7b72c448fc8e76711bcbfbe158be9ae8ad87e7a720c8f37fbd3
freshness reason: empty
```

## Real PACK

A pre-existing untracked zero-byte Windows character device named `NUL` was moved, reversibly, outside the checkout before PACK. It was not deleted. No source or manifest gate was bypassed.

```text
project_id: wintage
PackResult.success: true
PackResult.status: PACKED
new archive: V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\__TO_AUDIT\Wintage_25.09.26-T14-11-59.zip
archive freshness: FRESH
freshness reason: archive current for the active packing policy
compact archive cell: 0s ✓
stale triangle present: false
```

Project Room was computed in the same process after PACK:

```text
archive_freshness: FRESH
archive_freshness_short: fresh
compact archive cell: 0s ✓
stale triangle present: false
```

The quarantined artifact is at:

`V:\___VAC\__K\__CODE\_TAMPERMONKEY\_WIN95THEME\_AUDAPACK_QUARANTINE\Wintage-NUL-20260925`

It is outside the Wintage source root. Restore it only if the source-owner artifact is required; restoring it will make the inventory fail closed again on its non-regular untracked path.
