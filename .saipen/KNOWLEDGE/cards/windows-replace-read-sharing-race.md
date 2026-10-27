<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: runtime state files, atomic replace, cross-process readers, Windows
trigger: one process atomically replaces a file that another process reads without a shared lock
status: active
evidence: T-1500, E-8999, tools/saipen_engine/watchdog.py _contended; T-1648, .saipen/evidence/T-1648-transient-lock/contention-ab.jsonl
supersedes: none

# On Windows an atomic replace and a concurrent read both fail as PermissionError

When a writer calls `os.replace` onto a file that another process is reading, Windows reports the collision on both sides as `PermissionError`: the reader cannot open the file and the writer cannot replace it. Neither outcome means the file is missing, corrupt or forbidden.

Why:
Python opens files without `FILE_SHARE_DELETE`, so a replace over an open target is refused, and an open that races the rename is refused too. Measured under contention for T-1500: readers failed about 6% of reads and the writer failed about 75% of replaces. A reader that maps any `OSError` to "absent" turns contention into a false negative (a healthy lease read as fenced), and a writer that lets the error escape crashes its caller (a supervisor heartbeat killing the whole run). Neither shows up on POSIX or in single-process tests.

How to apply:
- Retry `PermissionError` briefly on both the read and the replace before believing it, and keep `FileNotFoundError` immediate.
- `paths.safe_atomic_write_bytes` waits out a refused replace itself since T-1648 (winerror 5 and 32 only, proofs re-run before each look), so a canonical write needs no wrapper for the replace. A read still needs its own retry.
- Size a retry by the number of looks, not the length of one sleep: holders let go within milliseconds. Measured against a target busy two thirds of the time, 8 linear attempts over 1.4 s still lost 4% of writes; 40 looks (5 ms doubling to a 50 ms cap, 1.83 s in total) lost none and added about an eighth of the latency.
- Let a periodic writer treat a still-contended write as a missed beat, never as a fatal error.
- Keep short-lived runtime writers such as heartbeats off the canonical project mutex. Canonical APPLY fails fast on WRITER_BUSY, so every collision becomes a failed operation.
