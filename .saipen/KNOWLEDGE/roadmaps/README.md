# Roadmap reference packs (NOT the audit inbox)

Reference material only. Nothing here is Work, and nothing here is an audit
layer.

`SOURCE-AUDIT-INBOX-01` (saipen/SOURCES.md) makes `<project-root>/audit/` the
live inbox and `^[1-9][0-9]*\.md$` its only canonical filenames. A roadmap ZIP
unpacked into `audit/` puts a pile of noncanonical files beside the live
layers: the scanner correctly ignores them and never deletes them, but the
folder stops reading as an inbox, and that is exactly the confusion the inbox
exists to remove.

**Operational rule: roadmap packs are reference artifacts. Do not unpack them
into the live `audit/` inbox.** If a roadmap is itself meant to be audited,
place ONE deliberate numbered audit file (`audit/N.md`), not the whole pack.

- `audit-ecosystem-next/` -- audit transport ecosystem, Waves A-I (producer
  enqueue API, provenance envelope, maintainer disposition projection,
  multi-producer hardening, operator surface, SAIPAL bridge, dogfood).
  Waves A and B are DONE: the native Audit Inbox shipped under T-1227 and
  consumed `audit/1.md`, `audit/2.md` and `audit/3.md` through its own
  journaled path.
- `current-stage-next/` -- the 31 Aug 2026 current-stage pack, Waves 0-8.
  Waves 0-4 are DONE (truth reconciliation, audit/1-3 closure, phase delta
  compression, native inbox, bootstrap migration + inbox hygiene, which is
  this move). Waves 5-8 remain.

The remaining scope is tracked as ordinary BOARD Work, bound to the source
receipt captured for these packs. Read the receipt, not a memory of the ZIP.
