# ADR-0003: Detached Handoff Project Binding and Host Launch Envelopes (T-1318)

## Status

Accepted (v8.0.2 / T-1318 P0). Implemented in `tools/saipen_engine/paths.py`, `tools/saipen.py`,
`tools/validate.py`, `saipen/BOOT.md`, and `bootstrap/inject.{ps1,sh}`.

## Context

When an AI agent is launched via an external tool (such as FastPrompter or an IDE drag-and-drop
launcher), the launcher often stages the handoff payload file in a temporary staging directory, e.g.:

```
V:\_TEMP_\fastprompter_drag\SAIHANDOFF_20260912_0418.md
```

If the launcher also spawns the agent process with its working directory (`cwd`) set to that
temporary directory, prior SAIPEN bootstrap observed:

1. `git rev-parse --show-toplevel` failed because the staging directory is not a Git repository.
2. Nearest ancestor lookup failed because no `.saipen/` existed in `%TEMP%` or its parents.
3. The agent halted and asked the user: "What is the SAIPEN Git worktree root containing `.saipen/`?"

This question was completely unnecessary because the launching workflow already knew the intended
project before generating the staging file. The handoff transport simply lost the project-root
provenance during handoff creation.

Furthermore, machine admission guards evaluating an agent invocation from a detached staging cwd
would observe `NOT_SAIPEN_PROJECT` and incorrectly treat the invocation as outside SAIPEN or
fail admission, preventing machine enforcement.

## Principle: Transport State vs Execution State

**The location of the handoff payload file is transport state.**
**The location of the project is execution state.**
**They must never again be inferred to be the same thing.**

## Three Distinct Identities

To avoid semantic collapse, the system strictly separates three identities:

1. **Protocol Installation (`saipen_home` / loaded skill anchor / `protocol_dir`)**
   The canonical SAIPEN installation owning the executable engine (`tools/saipen.py`),
   normative protocol specifications (`BOOT.md`, `STYLE.md`, `CORE.md`), and execution
   machinery. The installed skill path (e.g. `C:\Users\...\.config\opencode\skills\saipen`)
   identifies the protocol tools; it DOES NOT identify the target project's `.saipen/` directory.

2. **Portable Project Identity (`project_lineage` from `.saipen/IDENTITY.md`)**
   A durable, portable lineage identifier canonically stored in tracked `.saipen/IDENTITY.md`
   (format: `lineage-<32-hex-chars>`). It survives directory moves, machine replacements, Git
   clones, and detached handoffs. Cold handoffs (`saipen brief`), receipts, and host session
   bindings bind to this portable identity.

3. **Local Working-Tree Location (`project_root`)**
   The machine-local path on disk containing the target project repository/working tree and its
   `.saipen/` directory. Single-writer locking collapses path aliases via `runtime_lock_identity`
   (`realpath` + `normcase`), but machine-local paths are never durable portable identity.

## Decision

### 1. Single Root Resolution Authority & Precedence

Project root resolution is centralized in `tools/saipen_engine/paths.py:resolve_project_root(...)`.
No independent environment or session root logic may be implemented in commands, validators, guards,
or host adapters.

The resolution precedence is:

1. **Explicit `--project-root`**
2. **Verified host/session project-root carrier** (`SAIPEN_PROJECT_ROOT` / `SAIPEN_PROJECT_LINEAGE`)
3. **Active Git worktree** (`git rev-parse --show-toplevel`)
4. **Main Git worktree** (`git rev-parse --git-common-dir`)
5. **Nearest ancestor `.saipen/`**
6. **Refusal** (`NOT_SAIPEN_PROJECT`, fails closed)

Arbitrary drive scanning, basename guessing, and automatic `.saipen/` creation in staging folders
are forbidden.

### 2. Host Root Validation & Fail-Closed Semantics

When `SAIPEN_PROJECT_ROOT` is present in the environment or passed to `resolve_project_root`:

* The path is expanded and normalized.
* It must exist and be a directory (`PROJECT_BINDING_INVALID` on failure).
* It must contain a valid, owned non-link `.saipen/` directory (`PROJECT_BINDING_INVALID` on failure).
* Its `.saipen/IDENTITY.md` must be readable and valid (`PROJECT_BINDING_INVALID` on failure).
* If `SAIPEN_PROJECT_LINEAGE` is supplied, it must match the project's lineage exactly
  (`PROJECT_LINEAGE_MISMATCH` on failure).
* On any error or mismatch, the resolver **fails closed immediately** with a structured refusal.
  It does NOT silently fall back to ambient CWD or foreign Git repositories.

When binding succeeds, the provenance is recorded as `host-session`.

### 3. Local SAIHANDOFF Launch Envelope

Handoff launchers (such as FastPrompter) construct a local launch envelope for session dispatch:

```json
{
  "project_root_hint": "V:\\___VAC\\__K\\__CODE\\_AI_STUFF_AGENTIC\\_SAIPEN",
  "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
  "handoff_payload_path": "V:\\_TEMP_\\fastprompter_drag\\SAIHANDOFF_20260912_0418.md",
  "producer": "FastPrompter",
  "created_at": "2026-09-12T04:18:00Z"
}
```

* `project_root_hint` is a local filesystem navigation hint.
* `project_lineage` is the cryptographic identity proof.

The launcher exports:
```
SAIPEN_PROJECT_ROOT=<project_root_hint>
SAIPEN_PROJECT_LINEAGE=<project_lineage>
SAIPEN_AGENT=<saipen_seat>
```
before spawning the agent process. `SAIPEN_AGENT` is exported whenever the launcher knows which
SAIPEN seat the session runs as; the first two are mandatory for a detached staging launch. The
actor carrier is optional explicit provenance (see § 8).

### 4. Preferred Launch Behavior

When launching an agent:
* Preferred: `cwd` = intended project root; handoff argument/path = temporary staging file.
* Detached staging: if the host platform requires spawning inside a temporary staging directory,
  setting `SAIPEN_PROJECT_ROOT` and `SAIPEN_PROJECT_LINEAGE` is mandatory.

### 5. FastPrompter Cross-Project Contract

When FastPrompter creates a handoff file under `fastprompter_drag/`, FastPrompter must retain the
initiating project root. It must:
- Launch the agent with `cwd` set to that project root; OR
- Set both `SAIPEN_PROJECT_ROOT` and `SAIPEN_PROJECT_LINEAGE` in the spawned agent's environment.

### 6. Portable Cold-Handoff Projection (`saipen brief`)

`saipen brief` derives a portable handoff projection containing:
- `project`
- `project_lineage`
- `phase`
- `work_id`
- `last_event`
- `state_updated`

It does NOT emit machine-local absolute paths in durable/portable handoff evidence by default.

### 7. Global Activation & Machine Admission Guard

The global activation instructions in `bootstrap/inject.{ps1,sh}` and `saipen/BOOT.md` activate
SAIPEN when `project root contains .saipen/ OR a verified SAIPEN handoff/session binding is active`.
Machine admission guards resolve the project root using the same canonical resolver, inspecting the
intended project's canonical state regardless of a detached staging cwd.

### 8. Host Actor Resolution (`SAIPEN_AGENT`)

Project binding says WHICH project; actor binding says WHO is acting.

* `SAIPEN_AGENT` (`paths.ENV_AGENT`) is an optional explicit actor/provenance
  carrier. A plain process environment value is not authenticated identity or a
  security credential.
* With an explicit carrier, admission checks that actor against live canonical
  ownership. A foreign actor fails `OWNERSHIP_CONFLICT`.
* Without one in a valid SAIPEN project, the existing protocol snapshot inherits
  canonical `STATE.agent`, then applies ownership, recovery, protected-path and
  operation-safety checks normally. Contradictory or invalid canonical ownership
  fails through those checks; absence of host metadata alone is not permission
  and is not an `ACTOR_UNBOUND` shortcut.
* A host SESSION id (OpenCode `sessionID`, Claude session id, ...) is diagnostic
  context, never an actor binding: it is not the same identity domain as a SAIPEN
  seat name. UI slots, process ids, window titles and ports are likewise never
  actor inputs.
* Read-only diagnostics remain available with no binding at all.
* Canonical saipen operations (the recovery path) own their own authority and
  stay admissible, so a missing binding can never wedge recovery.
* Strong authenticated host identity would require a separate capability design,
  such as signed short-lived tokens or OS-bound credentials; this environment
  carrier does not pretend to provide one.
