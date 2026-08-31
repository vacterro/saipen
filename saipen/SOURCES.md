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
