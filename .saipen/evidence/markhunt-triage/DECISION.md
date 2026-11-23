# Explicit audit triage requested

Proposed decision: accept T-1307 through T-1314 as Work for their exact original
criteria, preserving filing-pass attribution. No dismissal, automatic DONE or
publication is proposed. Existing implementation may be verified and closed
locally only if it satisfies the entire original criterion; remaining defects
need normal SCOUT/BUILD/VERIFY/REVIEW/SHIP.

`records.json` resolves all eight original descriptions and criteria through
14 hash-verified compaction records. The immutable filing events are actually
present and account for these exact tickets: E-5977 (T-1307/1308/1309), E-5978
(T-1310/1311), E-5979 (T-1312/1313), E-5980 (T-1314). Model-authored prior
unblocking decisions do not substitute for human triage.

| Ticket | Exact concern | Current observed facts and remaining proof |
| --- | --- | --- |
| T-1307 | One canonical translation producer state and outbox; conflicting mirrors must fail. | The mirror and its manifest advertisement are absent. Canonical STATE is also absent. This alone does not satisfy the complete original state and control criterion. |
| T-1308 | Collect compatible global drift using unchanged declared dependencies; refuse changed dependencies/targets. | The current collect branch still refuses global head/fingerprint drift in subs.py:4308-4344. Producer integration's compatibility classifier does not prove this collect criterion. |
| T-1309 | Ignore closed non-locale directory classes; retain missing real-locale failures. | Actual isolated directory control still counts both __pycache__ and .translation-cache. The missing real locale is retained. The defect remains despite the live cache directory being absent. |
| T-1310 | Diagnose and safely recover tombstone/active resurrection; preserve real missing-body failure. | SRC-024 has a tombstone, no active body, and current orphan diagnostics return none. The original recovery and hostile-control criteria still require independent verification. |
| T-1311 | Actionable distinction between explicit manifest entries and copied untracked files. | Current validator excludes untracked copy-tree noise and names explicit untracked files. This is changed behavior; the original distinguishing-output and hostile control must be checked, not assumed satisfied. |
| T-1312 | Advertised producer namespace must exist in tracked history or be retired by a recorded decision. | The old untracked mirror and its advertisement are absent. Tracking and the advertised-untracked negative control still require the exact original proof. |
| T-1313 | Own or archive changelog overflow; preserve descending-order control. | The current changelog has 11 headings, its archive is tracked and current core validation emits no changelog-unarchived warning. Archive preservation and the original ordering control still need exact verification. |
| T-1314 | Mechanical READY retention/settlement policy; stale snapshots never collectable. | The live READY directory exists; current.json reports its actual verified package count. The older claim that it was absent is not current proof. Publisher uses the shared staging implementation; policy and stale-package control remain to be verified. |

`current.json` records UTC observation time, source hashes, the actual locale
control, bounded filesystem facts and read-only package validation. None of
these observations admits a ticket or changes canonical Work.

The owner requirement is saipen/phases/markhunt.md:29:
"Only later explicit human triage may accept one into TODO or dismiss it."
The phase also requires a triage DEC naming both ticket and filing pass. This
is the exact rule requiring the human decision; publication is separately
excluded by the controlling scope.

A separate validator lifecycle concern is preserved: validate.py:2837-2848
requires a blocker on every raw [MARKHUNT] row regardless of section, while
canonical unblock removes that blocker. No guard was weakened or production
fix applied. If acceptance is granted, reproduce and repair that conflict
through normal Work before admitting records that would fail validation.
