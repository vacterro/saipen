<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: .gitattributes, core.autocrlf, git stash, byte-bound evidence, managed projects, Windows
trigger: a digest-verified SAIPEN file (source body, archive, log detail, board compaction) fails its sha256 in a project on Windows
status: active
evidence: T-1508, AUDAPACK .saipen/archive/source/SRC-037..SRC-047 (dangling stash commits 2026-09-17T20:10:47Z..20:11:37Z), tools/saipen_engine/runtime_namespace.py BYTE_BOUND_PATTERNS
supersedes: none

# Git line-ending conversion silently breaks byte-bound SAIPEN evidence, even in untracked files

Git for Windows ships with `core.autocrlf=true` in its system config. Without a `-text` attribute, Git rewrites LF as CRLF whenever it writes a file into the working tree. That includes files the project never committed: `git stash -u` stores untracked files and `git stash pop` checks them out again, converted.

Why:
SAIPEN proves source bodies, archived sources, LOG details and BOARD compaction records by the sha256 of their exact bytes. Measured in AUDAPACK, a project with no `.gitattributes`: four `git stash -u` round-trips inside 50 seconds rewrote every file of seven untracked archived sources with CRLF. Their digests were of the LF bytes, so attribution refused them with a bare ARCHIVE_BODY_SHA_MISMATCH and status reported SOURCE_CORRUPTION. Nothing in the tree or the history pointed to Git, because the files had never been committed. The evidence was the identical mtime on every rewritten file and the dangling stash commits that `git fsck --unreachable` still lists.

How to apply:
- A byte-bound path must be `-text`. `eol=lf` is not enough, because a source that really arrived with CRLF would still be rewritten on the next commit. SAIPEN appends the missing rules at every source capture (`runtime_namespace.ensure_gitattributes_policy`).
- Before calling a digest mismatch corruption, check whether replacing CRLF with LF reproduces the recorded digest (`intake.line_ending_drift`). If it does, the source is intact and that rewrite is a proven, lossless repair.
- `.saipen/evidence/**` is left out on purpose. It holds ordinary tracked text, and marking it `-text` would show every CRLF working copy as modified.
