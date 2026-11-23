# Prospective T-1597 verification

The current repair is already in local commit `5839da87`; the pre-fix subject
is the exact file from that commit's parent. No current source file changed.

The fixed external driver `run_pair.py` SHA256
`caeb4ac52cc3700fb37077b4b9a3b36861ba064873fdd946bc721587f6c2a8a7`
supplies one transient empty result at the sweeper boundary, then delegates to
the real sweeper on the real sandbox. Both subjects use the same engine bytes,
fixture, command, bound and expected removal. It judges the test harness's
handling of the documented temporary REPORT, not a core-unit engine change.

- Parent subject `54166df9b820a3bdb66f8fe272fedbf5874497e15dec3fbe357d9caf5a9684dd`:
  one collected test, one assertion failure, zero errors or skips; one sweep.
- Current subject `2afaef42922d0316ee84c052da824988297ea5ac9638bd34087ab4da9841e340`:
  one collected test, zero failures/errors/skips; two sweeps and real removal.
- Permanent-empty negative control: one collected test, one failure after the
  unchanged 30-second bound; 150 calls. A retry cannot invent successful cleanup.
- Engine `core_unit.py` SHA256 is identical throughout:
  `65dae1f6d4b3875850d5c445b3df11152442c8a454caa88e50bc47df9b993a3e`.

This establishes removal of the immediate-sweep assumption. It does not prove
which assumption caused the historical intermittent six-shard failure, and
does not claim that destructive polling establishes future holder readiness.
The historical notes explicitly left that mechanism unproven; they remain so.

These are prospective artifacts only. T-1597 is still TODO. Its own current
VERIFY cycle must bind the real pair, focused Windows controls and matching
complete-family evidence before any normal evidence closure.
