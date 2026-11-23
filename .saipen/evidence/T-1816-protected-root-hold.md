# T-1816 R006 bullet 2 — protected-root hold

Reference: `saipen/OPS.md` § 9 (OPS-EFFECT-01) and
`tools/saipen_engine/protected_root.py`.

## Protected-root hold (T-1816, DRIFT-01)

A REFUSAL THAT LEAVES NO DURABLE MARKER IS ADVISORY. DRIFT-01 measured exactly
that: a root was refused `FORENSICALLY_UNRECOVERABLE` /
`READ_ONLY_DIAGNOSIS_ONLY` with `Bash`, `Edit`, `Write` named as forbidden
probes, and the next turn wrote `LOG.md` and `STATE.md` through an embedded
Python script. The refusal was bound to a VERB NAME; the mutation arrived
through an interpreter. Mechanics live in
`tools/saipen_engine/protected_root.py`.

**Two records, deliberately separate.** The HOLD is `.saipen/HOLD.json`,
written only by a canonical operation: `{schema, root, mode, reason,
protected_paths, lift_command, declared_by}`. It is durable precisely because
the measured defect was a transient refusal that left nothing for the next
process to read. The VERDICT is a pure function `check(root, targets, effect)`
and depends on `(root, hold, target path)` ONLY -- never on the tool name, the
verb spelling, the command text, or the actor's declared intent.

**Fail-closed ladder.** No hold file -> `ALLOW` (`NO_HOLD`), so an ordinary
project is unaffected. Hold file unparseable or not an object -> `REFUSE`
(`HOLD_UNREADABLE`): deleting or corrupting the file must not lift a hold.
Unknown `mode` -> `REFUSE` (`HOLD_MODE_UNKNOWN`). A mutating effect on a
protected target -> `REFUSE` (`PROTECTED_TARGET`), whether it arrives as
`Edit`, `Write`, `Bash`, a nested shell, or `python -c`. A non-mutating effect
-> `ALLOW` (`NON_MUTATING`), because a read-only forensic pass is the purpose
of the hold. `ALLOW` otherwise reports `TARGET_NOT_HELD`: an active hold
protects its named set, not the whole tree.

**Path matching.** `.saipen/LOG.md` protects that file and NOT
`.saipen/LOG.md.bak`; a trailing-slash entry protects the subtree. Absolute
targets inside the root are normalized before comparison; a path outside the
root is another root's business and is never silently absorbed. The default
protected set is the mutable memory surface (`LOG.md`, `STATE.md`, `BOARD.md`,
`MANIFEST.json`, `IDENTITY.md`); code and evidence stay writable.

**Boundary.** This is a policy verdict, not a sandbox. It prevents mutation
only where an installed blocking hook actually calls it; an ADVISORY host does
not acquire enforcement from a green test, and the honest ENFORCEMENT value
stays what § 9 already requires. Lift a hold only through its
`lift_command`, never by deleting the file.

