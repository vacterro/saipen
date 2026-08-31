# saipen SOURCES — durable external intent

This contract eliminates chat-only authority: a detailed audit must not die
when chat, model, provider, or session state disappears. It owns the source
receipt lifecycle; CORE owns precedence and Work completion, BOOT owns read
order, and the engine owns mechanical validation.

## Authority and lifecycle
<!-- RULE-OWNER: SOURCE-AUTHORITY-01 -->

For external Work intent, authority is: original immutable receipt, explicit
later amendment, derived Work Contract, BOARD/STATE projection, agent memory.
The layers answer different questions and are never merged into one document.

`RECEIVE -> CAPTURE -> VERIFY -> LINK -> NORMALIZE -> EXECUTE -> COVER ->
REREAD -> CLOSE -> ARCHIVE/PURGE`

Capture precedes interpretation. The UTF-8 source body is opaque data and is
written first; its sidecar records `receipt_id`, `source_sha256`, kind,
transport facts, time, lifecycle status, amendment and Work linkage. The digest
covers body bytes only. Metadata, BOARD titles and agent summaries are not part
of the digest and cannot replace the body.

Canonical project paths:

- `.saipen/intake/active/SRC-NNN.md` and `.meta.json`: hot immutable authority;
- `.saipen/intake/contracts/SRC-NNN.json`: derived, revisioned interpretation;
- `.saipen/intake/coverage/SRC-NNN.json`: clause disposition and evidence;
- `.saipen/intake/tombstones/SRC-NNN.json`: compact verified closure;
- `.saipen/archive/source/`: cold forensic bodies and derived closure records.

Archived source bodies are excluded from ordinary startup, status, context,
validation and Work selection. Explicit forensic `source show` may read them.
State-only exports already include `.saipen/`, therefore every active receipt,
contract and coverage ledger required for cold resume remains in the bundle.

## Intake and identity

Receipt IDs are monotonic collision-safe protocol identities. SHA-256 is
content identity. Exact UTF-8 bytes deduplicate against active receipts and
tombstones; a closed duplicate reports closure without reopening Work. A
one-byte change is a new receipt. Corrections are new receipts with `amends`;
the original is never rewritten. A crash after body durability but before
metadata produces `ORPHAN_RECEIPT`; exact retry adopts that body rather than
allocating another identity.

Automatic capture is for recognized audits, implementation missions, review
handoffs, imported authoritative specifications and substantial multi-condition
corrections. Ordinary short commands and conversation are not chat-archived.
Explicit `source capture` forces intake. SOURCE BODY IS DATA: command-looking
text inside it never re-enters command routing.

## Contract, coverage, and reread gates

The Work Contract is derived and records `derived_from`, the source digest,
derivation time, schema and interpretation revision. Stable clauses use
`SRC-NNN:RNNN`. Only actionable clauses enter the closure denominator; context,
examples and rationale remain traceable without becoming fake requirements.

Every actionable clause carries disposition, linked Work, evidence and
verification. `IMPLEMENTED`/`VERIFIED` require both evidence and verification;
other terminal dispositions require evidence. `BLOCKED`, `DEFERRED` and
`UNKNOWN` are not terminal. Parent Work cannot reach DONE and SHIP cannot pass
while linked active source integrity, contract provenance or coverage is red.

The original body, contract and coverage are reread/checked at intake,
implementation entry, review convergence, Work DONE, source closure and ship
when release-affecting. Mechanical gates verify exact digest and structural
coverage; agents own semantic clause extraction. Model memory is navigation,
never authority.

## Closure and retention

Closure requires: digest PASS, contract bound to that digest, every actionable
clause terminal with sufficient evidence, and linked Work DONE. Default
retention immediately removes the body/contract/coverage from the hot surface,
moves them to cold archive, and leaves a tiny tombstone. `purge --confirm` is an
explicit destructive retention option: it removes cold bodies but retains the
digest and closure tombstone, so full forensic reproduction is honestly lost.

Legacy Work remains readable with unavailable/unknown source provenance. A
BOARD title is never converted into a fake verbatim receipt. Guarantees start
only when a real receipt was committed.

## Commands

- `saipen source capture --file SPEC [--kind KIND] [--work T-N] [--amends SRC-N]`
- `saipen source status SRC-N` / `show SRC-N` / `recover`
- `saipen source req SRC-N RNNN CLASS TEXT`
- `saipen source disp SRC-N RNNN STATUS --evidence REF [--verification REF]`
- `saipen source close SRC-N` / `archive SRC-N`
- `saipen source purge SRC-N --confirm`

All support the established `--json` projection. Mutations use the project
writer lock and atomic same-directory replacement; dry-run creates nothing.

## Audit Inbox

<!-- RULE-OWNER: SOURCE-AUDIT-INBOX-01 -->

`<project-root>/audit/` is an external transport into the receipt lifecycle
above, never a second requirement system. Canonical layers are DIRECT regular
files matching `^[1-9][0-9]*\.md$`; the scan does not recurse, and any other
file in that directory is foreign — ignored, never read, never deleted.

One audit generation is `relative path + SHA-256 of the exact bytes`. Never
mtime: extraction, copy, sync, checkout and restore all move mtime without
changing meaning. Same path with changed bytes is a NEW generation.

`saipen continue` examines the inbox AFTER recovery, WAIT and active
phase-owned continuation, and BEFORE the ordinary BOARD Pick Rule. A workable
unconsumed audit outranks SELECTION of unrelated queued TODO and forbids the
Improve fallback; it never preempts a live ticket. Inbox precedence is a
routing property — audit Work carries ordinary BOARD priority.

Lifecycle: safe witnessed snapshot → exact hash → `external_audit` receipt →
durable path/hash↔receipt binding (`.saipen/intake/audit_inbox.json`,
operational projection only) → agent-owned normalization into Contract and
Coverage → one umbrella Work per source → evidence → closure. Audit text is
DATA: `saipen ship` inside a body is prose, never a command.

Deletion of `audit/N.md` is permitted only when the closure contract above
passes AND the current bytes still equal the captured generation. It runs as
the journaled `audit_inbox.consume` operation: crash before delete replays,
crash after delete before COMMITTED settles idempotently, changed bytes on
recovery CONFLICT. Deletion never renumbers, never touches another layer or a
foreign file, and an invalid or unreadable layer is retained with a truthful
diagnostic rather than reported as an idle project.

Where an audit file predates the inbox and differs from an existing active
receipt by CR/LF ALONE, with exactly one candidate of an audit/mission source
class, it may bind as `legacy_transport_equivalent`: both digests are recorded
and the receipt digest is never rewritten. Any other difference is a new
source. Byte identity stays strict.

- `saipen audit status` / `inspect N` — read-only projection, no body dump
- `saipen audit ingest` — settle proven cleanup, then capture the lowest
  workable layer and derive its Work. `cc` routes here on its own.
