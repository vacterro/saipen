# Wave 5 — sandbox and discovery decision

SRC-285 R006, current source generation d23c49152ef1f81d. These are mechanism
observations, not suite acceptance. No production copy/discovery contract was
weakened. The current implementation retains consistent snapshots, private
mutable workers, exact occurrence manifests and owned cleanup.

## Measured input and stages

The corrected paired experiment captured one frozen input: 126,351 files/links,
1,622,323,227 bytes. Windows measured a 54.618 s consistent source/state copy,
51.303 s private worker clone and 3.203 s real discovery. The private clone's
complete ordered relative-path/type/length/content inventory equals its input,
not merely the count. Discovery found 7,076 occurrences, digest
`a6ca2c9a90f79269cd9ca847f9f4384cd6db2609a43b2a0556723eb241864a04`,
with no import errors. It deliberately executed zero assertions and grants no
test acceptance. Owned Windows roots were reclaimed in 13.027/15.968 s.

Native Ubuntu Python 3.12.3 copied the SAME frozen input from the Windows WSL
mount into native /tmp in 135.860 s; inventory hashing took 34.755 s and owned
cleanup 15.391 s. This cross-mount read is not a native-to-native Linux copy
benchmark and is not a platform speedup comparison. Linux worker-clone and
whole-discovery stages did not execute, as described below. Antivirus cost and
peak memory were not observed. The final acceptance still owes its platform
coverage; copying is no substitute for executing that coverage.

## Instrument failures and exact recovery evidence

The first existing/new paired attempts stopped before Linux execution because
WSL's default shell consumed Windows backslashes in wslpath arguments. That
failure was preserved, then native --exec plus forward-slash transport was
independently preflighted before the corrected expensive run.

The corrected Linux copy then hit a distinct instrument defect: Windows Path
sorting folds case and POSIX Path sorting does not, so the same content entries
produced different ordered digests. While the exact Windows snapshot was still
owned/live, check_inventory_order.py independently inventoried it again. Its
legacy digest matched the original Windows input, proving the snapshot had not
changed; its portable path-parts ordering gave
`97ba952d4921486f74101eea92cb7cd4d8b3490762410e67e85e1717ac88db78`.
The completed Linux copy independently recorded that EXACT digest, count and
byte total. audit_sandbox_pair.py verifies these links from preserved reports.
This proves byte equality of the completed first copies. It does not convert
the interrupted Linux experiment into PASS or invent its missing later stages.
Every newly owned root was actually reclaimed. The harness now orders entries
portably; no further expensive copy is needed to rediscover that established
ordering defect. Original measurements and errors remain unchanged.

## Decision, savings and risk

* Required state copying dominates the observed discovery cost. Durable evidence
  is the largest known input namespace; blanket omission/deletion is rejected.
  T-1831 already removes an unnecessary live-state dependency from a cleanup
  acceptance fixture while retaining all 21 original assertions.
* Hardlinks are rejected for mutable workers. The isolated witness's worker
  write changed its private original on Windows. No hardlinks touched the live
  repository. No proven cross-platform copy-on-write helper was found in the
  bounded existing implementation; speculative sharing is not introduced.
* A separate shared discovery manifest is deferred. The measured Windows
  discovery is about 3.2 s versus about 54.6 s copy and 51.3 s worker clone.
  Multiplying 3.2 s by worker count would be process-time arithmetic, not a
  measured wall saving. Canonical module imports, fixture order, imported test
  multiplicity, import errors and newly added tests would still need proof.
  Current exact manifests/partition coverage address correctness without claiming
  that discovery itself became faster. No new manifest authority is justified
  by this observation.
* Private physical copies remain the safe current default. Same-generation
  compatible evidence sharing and the removed extra CI outer copy reduce how
  often copies are needed without sharing mutable fixture state. No additional
  whole-family performance gain is claimed here.

REGRESSION EVIDENCE: T-1830 exact copy/membership controls, T-1831 unchanged
21-control cleanup acceptance and independent fixture boundary, T-1837 actual
import/empty-partition/failure controls, and the same-scope 46-control real
copy/shard/cleanup corpus executed on Windows and native Linux. Final whole
generation/platform acceptance remains required under ACCEPTANCE.md.

NEXT ACTION: resolve the established cumulative pending-cohort publication
constraint through T-1839 before freezing final release metadata and running the
one strategically scheduled full-generation acceptance. Reject unchanged unsafe
hardlink/exclusion hypotheses; retain the incomplete Linux-stage limitation.
