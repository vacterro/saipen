# T-1708: bounded verification metadata correction

The existing journaled `ticket_verify` operation now accepts a declaration-only
`regression: required` update. The native command is
`saipen ticket regression T-N required`. It introduces no second writer,
operation family, grant, permission bypass, or removal/relaxation route.
Existing verify updates retain their preimage history. Declaration reads one
snapshot and does not replace the verify field with a model reconstruction.

The exact owned delta is `OWNED.diff`, against the four byte-preserved files
at the start of BUILD, plus the new verifier. Earlier foreign edits in those
files remain intact. The only index change is intent-to-add for the new test;
the original index projection was `46b44c7aa50434fd5`, afterward
`b3a3a30a49f44fe2`. HEAD remains `025bf596c683464788ab698248e8a3c5eb44dfec`.
No commit, tag, push, runtime refresh, consumer repair, or source rollback ran.

The unchanged verifier SHA-256 is
`e9b27215cf9fa9017c573298a37bf90e930dc876000feb904dd746b78b4e375e`.
The initial live pre-fix run collected 13 tests, with 11 named failures and
zero errors; the corrected live run passed all 13. In `verify-control.json`,
two restored-old runs repeat exactly those 11 names, then two restored-current
runs pass all 13. Only `operations.py` and `saipen.py` change between subjects;
the live subject and verifier are unchanged. E-14257/E-14258 bind the actually
executed pair in the current VERIFY cycle.

The earlier `build-control.json` is retained as an unavailable instrument:
the subset copy omitted a required home document. Its known-good subject
failed HOME_REQUIRED, so its failures are not product regression evidence.
`build-control-v2.json` and `verify-control.json` include the complete required
home and pass their instrument controls.

The tests drive the real API, native CLI and real VERIFY-to-REVIEW gate. They
cover verify/Source/seat/phase/goal preservation, malformed and relaxing values,
missing and historical DONE Work, write-free preview and refusal, original
oversized contract preservation, and unchanged behavior of unrequired Work.
Source linkage is established through the real capture owner in the fixture.
The current-cycle gate refuses an ordinary green alone after declaration and
admits a genuine unchanged-verifier, changed-subject pair.

The combined neighbor run collected 224 tests. Its only failure was the new
COMMANDS row exceeding the existing command-resolution load budget. Sharing
the capability/metadata row corrected that; the unchanged budget test passes
in `t1708-registry-budget-v2.json`. No budget or oracle was relaxed. Ruff
0.16.0 over `tools/ tests/` and whitespace checks pass.

Current native validation after adding the test to the index is CURRENT_PASS,
0 problems / 9 warnings (`t1708-native-validate-after-index.json`, receipt
`receipt-cb81eb18594b`, 2026-10-10T14:26:04Z). RV-000016 is executed evidence
on this source generation; the later reverify command returned REVERIFY_REUSED,
not a second execution. Earlier failures remain retained.

The full 6121-test family is still running on source fingerprint
`ca37381939e67b4e473ba5cdd6e62165751e3f8280eee5986923475822b43b2e`.
No overall PASS or independent phase-REVIEW verdict is asserted by this file
until its actual completion and the separate REVIEW execution are appended.

Static diff assessment: the route preserves the existing CAS preconditions,
board-compaction targets, seat calculation, fast validation and journal commit.
Invalid declarations refuse before planning, historical DONE before projection.
No P0/P1 finding is demonstrated in this bounded delta. Memory promotion: NO;
the canonical command and contract are already the durable owners.

Candidate commit message under caveman-commit, for later authorized publication:

```text
fix: declare regression on existing Work
```

The first completed full family on this source collected 6121 tests and failed
seven native OpenCode cases (E-14263, record
`ca37381939e67b4e-20261010T144201Z.json`). All report a non-executable host
entrypoint, not a changed plugin checksum. The default installed `.exe` was
replaced during that run by its 479-byte postinstall text stub; the writer is
not attributed. The matching installed 1.18.35 x64 payload is a real PE and
executes. Prepending only its directory to the verification process PATH makes
all seven unchanged native cases pass (119.443 seconds). Global install files
and the external ZAICODE OpenCode process are untouched. The default entrypoint
remains an incomplete install; no machine-wide repair is asserted.

`OPENCODE-RUNTIME.json` records sizes, hashes and timestamps. The full family
is rerunning on the identical `ca37381939e67b4e` source with this executed native
instrument. This is a new complete run, not a baseline waiver or a sum of
selective rechecks. Its result remains pending here.

The subsequent actual full run completed at 2026-10-10T15:12:24Z:
**6121 ran, 0 red, 0 new red**, exit 0, 1397.0 seconds, source unchanged.
Immutable record `ca37381939e67b4e-20261010T151224Z.json`, SHA-256
`493651e39321f5e07aa65d903dfef3752458c7fb2a88a33b142b742dfd2c96b5`,
is anchored at E-14265. No sandboxes leaked; the six recorded process IDs
were absent in the subsequent actual process query. VERIFY native validation
at E-14266 also passed freshly: receipt `receipt-f077345e6d69`, 0 problems /
9 warnings. The REVIEW transition is E-14267.

Independent phase-REVIEW execution (`review-control.json`) again collected
13 tests per subject: current green, two identical restored-old sets of 11
failures without setup errors, then two restored-current greens. Verifier,
live source, HEAD and original index entries remain unchanged. The reviewed
five-path scope is journaled at E-14269. Native REVIEW's first execution
reported a changed-input fingerprint and is retained as CURRENT_FAIL; its
serialized recheck is pending. No SHIP verdict follows from that failed run.

The serialized REVIEW native recheck passed at 15:19Z, receipt
`receipt-7a70ed379efe`, CURRENT_PASS 0 problems / 9 warnings. Independent
REVIEW SHIP verdict E-14270 and SHIP transition E-14271 preceded the canonical
local release `release-7b9ee0604806458aab1cc93aa0ec2d14`, COMMITTED at 15:20Z.
T-1708 is DONE under no-publish policy: validation and truthful skipped-publish
event plus atomic closure; zero Git writes. No tag was created or pushed.
T-1705 is restored unclaimed at its saved BUILD/SCOUT tuple; its acceptance
and parent T-1703's saved REVIEW position remain intact. The operator's newer
AUDAPACK recovery priority is now being applied before further improvements.
