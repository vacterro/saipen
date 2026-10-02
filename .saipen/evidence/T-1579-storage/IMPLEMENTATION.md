# T-1579 storage safety work map

Authority: SRC-153, with operator clarifications SRC-154 and SRC-155. The operator confirmed `V:/___VAC/__K/__STATE/SAILEARN_HOME` is persistent and outside cleanup. A SAILEARN source repository is not available yet; do not invent or rebuild SAIBUD-1..7.

The production loss occurred when SAILEARN's sole HOME was `V:/_TEMP_/sailearn-home-m7`; external cleanup deleted it. SAIPEN's defect is admitting that path for durable state. T-1570 is parked at BUILD while this ticket owns the seat.

Implementation boundaries:

1. A machine policy in the existing SAIPEN user configuration home records explicitly trusted durable roots, arbitrary ephemeral roots and an optional scratch root. OS temporary roots are always ephemeral. Unknown paths stay unknown for durable writes.
2. A path classifier resolves environment variables, relative paths and existing links, and compares paths by platform identity. Known ephemeral roots take precedence over durable declarations. Durable use under one returns `STORAGE_POLICY_VIOLATION` with the requested path, matched root and repair route.
3. A project declaration records named stores with class, lifetime, resolved path, ownership and recovery policy. Durable declarations and canonical references are checked before publication or Work completion; transient scratch remains usable.
4. Promotion copies into a declared durable store, verifies hash, then atomically publishes a registry reference. Crash before reference publication leaves the previous registry intact. Migration of existing temp references reuses that operation with provenance and never deletes user data.
5. A missing canonical artifact is classified as reconstructable, partial or unrecoverable from its declared recovery policy. It is never silently treated as a fresh install.
6. CLI covers policy status, durable root configuration, ephemeral root add/remove, path classification, project store declaration/validation, promotion and migration.
7. Controlled SAILEARN fixture covers HOME rejection, scratch promotion and scratch deletion with durable registry survival. Add OS TEMP, custom roots, nesting, Windows case/slash, relative path, unknown, atomicity and legitimate scratch controls.
8. Audit SAIPEN-controlled projects by store role, flagging durable or sole-copy state under ephemeral roots only. SAILEARN recovery awaits its repository; preserve SAIBUD-8 and report unreconstructable history exactly.

Known reuse: `tools/userperson.py:user_config_home` for global policy placement, `tools/saipen_engine/paths.py` for safe owned file operations, `tools/saipen_engine/lock.py` for serialized mutation. Canonical gates and the declared whole core-unit family are documented in `.saipen/KNOWLEDGE/harness.md`.
