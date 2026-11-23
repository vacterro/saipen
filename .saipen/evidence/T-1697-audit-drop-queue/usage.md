# Project audit drop queue

Place a UTF-8 `.md`, `.markdown` or `.txt` file directly in the bound project's
`audit/` directory. Filenames need no numeric allocation. Each project uses
its own inbox; the engine does not crawl the project registry.

The normal `saipen continue` loop finishes active Work and selects existing
workable BOARD tasks before admitting a fresh named handoff. It takes one
source at a time. Legacy numbered inbox entries retain their prior precedence.
Numbered files sort numerically, followed by named files in casefolded name
order. File modification times do not establish authority or ordering.

Use `saipen audit status`, `saipen audit inspect filename.md` and
`saipen audit trace filename.md` to inspect progress and retained provenance.
The original source is captured exactly. The inbox file is consumed only by
the journaled cleanup after proven Source closure and a matching current hash.
A changed file is a new generation and is retained for separate processing.

Polling happens through the active agent's canonical continuation loop. This
change does not install a daemon or wake a stopped host. The shared source CLI
implements the feature; existing copied runtimes need their normal supported
freshness/update path before they can provide it.

T-1696 / SRC-201 retains the requested AUDAPACK forensic mission. No AUDAPACK
project file was read or written while implementing this queue. The matching
new inbox document is visible but has not been consumed during T-1697.

Evidence includes an unchanged ten-case acceptance oracle, a foreign-project
public CLI smoke, preserved original owner files and the exact nine-file diff.
The canonical full family completed: 6023 tests, zero red and zero new red;
record `.saipen/evidence/core-unit/7befebf58cc38873-20261010T003913Z.json`.
Local no-publish closure is E-14085; SRC-202 is CLOSED. This update records
that observed result without changing the original verification history.
