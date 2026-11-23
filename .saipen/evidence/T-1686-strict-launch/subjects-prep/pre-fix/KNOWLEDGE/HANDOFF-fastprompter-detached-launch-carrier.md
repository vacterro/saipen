# CROSS-PROJECT HANDOFF — FastPrompter detached-launch SAIPEN carrier

Status: OPEN (explicit closure blocker for T-1317 CLOSE-7 / SRC-029:R012)
Owner: FastPrompter repository (`V:\___VAC\__K\__CODE\_PY\_FastPrompter`, v0.8.67)
Consumer contract owner: SAIPEN (this repository) — T-1317
Created: 2026-09-12 (T-1317 Target C / CLOSE-7)

## Required change (FastPrompter side)

When FastPrompter stages a handoff payload (e.g.
`V:\_TEMP_\fastprompter_drag\SAIHANDOFF_*.md`) and spawns an agent session, it
must preserve the initiating project by doing BOTH of:

1. spawn the agent with `cwd` set to the initiating project root; and
2. export the project binding into the spawned process environment:

   ```
   SAIPEN_PROJECT_ROOT=<initiating project root>
   SAIPEN_PROJECT_LINEAGE=<project lineage from .saipen/IDENTITY.md>
   ```

`SAIPEN_AGENT` may additionally carry an explicit actor for pinned launches or
handover, but is optional provenance rather than authentication. Without it,
Core inherits canonical `STATE.agent` and applies ordinary ownership and
protocol-state checks (ADR-0003 §8).

## Why (verified current state)

Read-only inspection of the FastPrompter 0.8.67 tree (2026-09-12):

- `src/fastprompter/core/silo_export.py` defines `_SCRATCH = "fastprompter_drag"`.
- No `SAIHANDOFF`, `SAIPEN_PROJECT`, `SAIPEN_LINEAGE` or `SAIPEN_AGENT`
  handling exists anywhere under `src/fastprompter` (grep evidence archived
  in `.saipen/intake/contracts/SRC-031.r008.json` coverage ledger).
- Consequently a staged spawn leaves the session with a detached staging cwd
  and no root/lineage/actor carrier — the exact SRC-029 incident.

## Consumer-side readiness (already shipped in SAIPEN)

- `tools/saipen_engine/paths.py`: `SAIPEN_PROJECT_ROOT` /
  `SAIPEN_PROJECT_LINEAGE` carrier with fail-closed validation
  (`PROJECT_BINDING_INVALID`, `PROJECT_LINEAGE_MISMATCH`).
- `tools/saipen_engine/admission.py`: optional explicit actor via
  `SAIPEN_AGENT`, otherwise canonical `STATE.agent` inheritance; read
  diagnostics remain unaffected.
- `KNOWLEDGE/ADR-0003`: full decision record.

## Acceptance for closure

A real FastPrompter-launched session must demonstrate (transcript evidence):

1. cwd or carrier resolves to the initiating SAIPEN project;
2. a consequential write is ADMITTED through canonical actor inheritance, or
   through an explicitly supplied actor when the launch intentionally pins one;
3. no user question about the project root;
4. the staging directory never becomes project identity.

Until then `SRC-029:R012` and `SRC-031:R008` remain explicitly DEFERRED and
T-1317 stays non-terminal. Do not modify FastPrompter from inside SAIPEN.
