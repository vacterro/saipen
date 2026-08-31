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
place ONE deliberate numbered audit file -- and the supported way to do that
is `saipen audit enqueue`, which allocates the number for you and never reuses
a consumed one (`SOURCE-AUDIT-ENQUEUE-01`).

- `next-2026-08-31/` -- the 31 Aug 2026 pack, Waves 0-10. Every wave is
  discharged: 0-5 shipped in v7.232.0/v7.232.1, and 6-10 (shared producer
  enqueue, provenance envelope, maintainer disposition projection,
  multi-producer hardening, operator surface, real HUSH runtime, SAIPAL
  bridge, transport dogfood, backlog re-entry) shipped in this release under
  `SRC-015` R001-R009. The pack is kept as the acceptance-bar evidence behind
  those dispositions, not as pending scope.

Two earlier packs (`audit-ecosystem-next/`, `current-stage-next/`) were
deleted once their remaining scope was discharged: their bodies are preserved
VERBATIM inside the `SRC-015` receipt, which is the authority anyway. Restore
them from git history if a forensic need ever arises:

    git checkout 538eb8fe -- .saipen/KNOWLEDGE/roadmaps/audit-ecosystem-next
    git checkout 538eb8fe -- .saipen/KNOWLEDGE/roadmaps/current-stage-next

Read the receipt, not a memory of the ZIP.
