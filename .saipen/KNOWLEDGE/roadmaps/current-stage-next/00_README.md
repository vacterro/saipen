# SAIPEN CURRENT-STAGE NEXT ROADMAP
## 31 AUG 2026 — TRUTH RECONCILIATION → AUDIT INBOX ACTIVATION → PRODUCER FOUNDATION

This pack is written for the current supplied SAIPEN tree, not for an earlier conceptual state.

## Verified current state

The repository already contains substantial completed compression work:

- `saipen/BOOT.md` ≈ 4.9 KB
- `saipen/INDEX.md` ≈ 2.35 KB
- `saipen/CORE.md` ≈ 23.1 KB
- `saipen/CONFORMANCE.md` ≈ 2.46 KB
- human `saipen/**/*.md` ≈ 278 KB
- conformance machine corpus is 256/256
- protocol budget reports PASS
- cold load target is already <= 20 KB
- command machine facts are registry-backed
- `external_audit` already exists as a Source Intake kind

However canonical project truth is behind the implementation:

- STATE is still `BUILD T-1222`
- BOARD still contains many W4 sub-tickets as TODO
- the current core validator still reports three failures
- no native `audit_inbox.py` / automatic numbered audit consumer exists
- the prior roadmap pack has been unpacked into `audit/`, creating noncanonical reference files alongside live `1.md/2.md/3.md`

Therefore the next mission is NOT "compress everything again."

The mission is:

> Reconcile canonical truth with what is already implemented, close the current three audit missions without duplicate work, activate the native Audit Inbox using those same files as migration dogfood, then establish one safe producer boundary for AUDAPACK and later SAIPAL.

## Wave order

0. Truth Reconciliation / Baseline Repair
1. Close `audit/1.md` Semantically
2. Execute `audit/2.md` Phase Delta Compression
3. Implement `audit/3.md` Native Audit Inbox
4. Bootstrap Migration + Audit Directory Hygiene
5. Shared Audit Producer API
6. HUSH Runtime Activation
7. SAIPAL Bridge Readiness
8. Backlog Re-entry / Cleanup

Do not implement all waves at once.

Every wave ends at a reproducible green stop gate.
