# SAIPEN AUDIT ECOSYSTEM — NEXT ROADMAP FULL
## AUDIT INBOX CLOSURE + MULTI-PRODUCER FOUNDATION + SAIPAL BRIDGE

This pack is the next implementation roadmap for the current SAIPEN tree.

It assumes the current tree already contains the three queued audit layers:

- `audit/1.md` — Load Topology / Conformance cutover
- `audit/2.md` — Phase delta compression
- `audit/3.md` — Native `cc` Audit Inbox

Do NOT replace or duplicate these audits.

The immediate mission is:

> Finish the existing audit queue correctly, then turn `audit/` from a manually managed folder into a durable producer/consumer boundary that SAIPAL, AUDAPACK, humans, and future audit producers can use safely.

## Current verified direction

The current implementation has already achieved major compression milestones:

- BOOT is already in the ~5 KB class.
- INDEX is already in the ~2–3 KB class.
- CONFORMANCE human document is already tiny.
- machine conformance corpus contains 256/256 scenarios.
- cold load is already below the original 20 KB target.
- command authority is registry-backed.
- Source Intake already knows `source_kind=external_audit`.

Therefore do NOT restart semantic compression from scratch.

The remaining architectural gap is the **audit transport lifecycle**.

Today:

```text
audit/N.md
→ human/agent notices file manually
→ manually creates Work
```

Target:

```text
audit producer
→ atomic enqueue
→ audit/N.md
→ cc discovers it
→ Source Receipt
→ canonical Work
→ evidence
→ closure
→ hash-guarded delete
→ producer disposition linkage
```

## Roadmap order

1. Wave A — Seal Current Audit Backlog
2. Wave B — Native Audit Inbox Consumer
3. Wave C — Shared Audit Enqueue Producer API
4. Wave D — Audit Envelope / Provenance
5. Wave E — Maintainer Disposition Loop
6. Wave F — Multi-Producer / Concurrency Hardening
7. Wave G — Operator Surface
8. Wave H — SAIPAL Bridge Contract
9. Wave I — Dogfood / Final Hardening

Do one wave at a time.

Later SAIPAL implementation should use the separate `SAIPAL_FOUNDING_ROADMAP_FULL` pack.

This roadmap prepares SAIPEN to consume SAIPAL output safely. It does not implement SAIPAL itself.
