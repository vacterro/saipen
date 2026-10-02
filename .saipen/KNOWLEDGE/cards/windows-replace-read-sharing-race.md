<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: runtime state files, atomic replace, cross-process readers, Windows
trigger: one process atomically replaces a file that another process reads without a shared lock
status: active
evidence: T-1500, E-8999, tools/saipen_engine/watchdog.py _contended
supersedes: none

# On Windows an atomic replace and a concurrent read both fail as PermissionError

When a writer calls `os.replace` onto a file that another process is reading, Windows reports the collision on both sides as `PermissionError`: the reader cannot open the file and the writer cannot replace it. Neither outcome means the file is missing, corrupt or forbidden.

Why:
Python opens files without `FILE_SHARE_DELETE`, so a replace over an open target is refused, and an open that races the rename is refused too. Measured under contention for T-1500: readers failed about 6% of reads and the writer failed about 75% of replaces. A reader that maps any `OSError` to "absent" turns contention into a false negative (a healthy lease read as fenced), and a writer that lets the error escape crashes its caller (a supervisor heartbeat killing the whole run). Neither shows up on POSIX or in single-process tests.

How to apply:
- Retry `PermissionError` briefly on both the read and the replace before believing it, and keep `FileNotFoundError` immediate.
- Let a periodic writer treat a still-contended write as a missed beat, never as a fatal error.
- Keep short-lived runtime writers such as heartbeats off the canonical project mutex. Canonical APPLY fails fast on WRITER_BUSY, so every collision becomes a failed operation.
