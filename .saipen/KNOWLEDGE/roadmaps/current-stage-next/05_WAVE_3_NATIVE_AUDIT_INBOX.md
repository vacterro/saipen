# 05 — WAVE 3: IMPLEMENT `audit/3.md` NATIVE AUDIT INBOX

## Goal

Make `cc` automatically consume numbered audits.

This is the pivotal feature wave.

## Architecture

Audit Inbox is a transport adapter into existing Source Intake.

It is NOT:

- a phase;
- a second BOARD;
- a second requirement system.

Pipeline:

```text
audit/N.md
→ exact witnessed bytes
→ external_audit Source Receipt
→ Source Contract/Coverage
→ canonical Work
→ evidence
→ Source close
→ hash-guarded journaled delete
```

## Routing order

Canonical continue ordering:

```text
recovery
→ mandatory interaction / WAIT
→ active legitimate continuation
→ Audit Inbox
→ ordinary BOARD Pick Rule
→ maintenance
→ bounded Improve fallback
```

Fresh audit never preempts active Work.

Fresh workable audit outranks unrelated queued TODO.

## Canonical files

Only direct regular files matching:

`^[1-9][0-9]*\.md$`

No recursion.

No renumbering.

Noncanonical files are ignored by the inbox engine.

## Generation identity

`relative path + exact-byte SHA-256`

Never mtime.

Same filename + changed bytes = new generation.

## Module boundary

Prefer a focused module such as:

`tools/saipen_engine/audit_inbox.py`

It owns:

- scan;
- safe snapshot;
- generation classification;
- receipt binding;
- read-only projection;
- cleanup planning.

It does not own semantic interpretation of audit prose.

## Delete gate

Delete only after:

- Source CLOSED;
- linked Work terminal;
- required evidence complete;
- current file digest still equals captured generation;
- journaled delete operation prepared.

Changed bytes are never deleted as old cleanup.

## Crash safety

Prove:

- crash before delete;
- crash after delete before commit marker;
- already absent;
- locked;
- changed-on-recovery.

## `next` / dry-run

Read-only.

No capture.

No deletion.

## `continue -> improve`

A workable audit means the project is not idle.

Improve stays last.

## Closure of audit/3

Do not finish T-1224 merely because scanner works.

The feature must also perform the bootstrap migration in Wave 4.

T-1224 may enter VERIFY after core implementation, but final completion should wait until current legacy layers are reconciled safely.
