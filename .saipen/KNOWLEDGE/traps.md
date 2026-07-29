# Traps

## Never write repo files with PowerShell Set-Content / Add-Content

Windows PowerShell 5.1 `-Encoding utf8` writes a **BOM** and mangles
non-ASCII (em-dash `—` becomes `вЂ"`, arrows `→` become `в†'`). Bit us twice:
the FreeBuff skill copy was unreadable for this exact reason (v1.2.2), then
the same command corrupted README.md at v3.1.1 seconds after we fixed it.

Use the editor tools (Write/Edit) for any file with prose or Unicode.
PowerShell is fine for git commands, not for authoring.

Recovery: `git checkout <tag> -- <file>` restores clean bytes; strip a BOM
with `sed -i '1s/^\xEF\xBB\xBF//' <file>`.

## Never ask "continue?" when board empty

RFC § 2.1 ZERO-PROMPT AUTO-TRANSITION: bare command + empty `## TODO` = MUST
go to HUNT, never WAIT at DONE. If HUNT clean, MUST go to ADD immediately.
A `WAIT:` at DONE with an empty `## TODO` is legal in exactly two forms since
v7.92.0 (RFC § 1.2): the § 2.4 safety valve, and `WAIT: user brake -- <reason>`.
Anything else there is drift, and `tools/validate.py` FAILs it. A `[MARKHUNT]`
ticket in `## BLOCKED` is a different situation entirely -- it means the board
has not halted, so the rule above never applies. This paragraph said the
MARKHUNT case was the *only* legal WAIT until v7.101.0, which had been wrong
for nine releases. Violated this session: stopped at
DONE asking vague "continue?" instead of running ADD.

## Never write LOG timestamps from local clock

LOG timestamps MUST be UTC (RFC § 1.2). Using local clock produces off-by-hours
drift that corrupts Recovery's audit trail. `tools/validate.py` FAILs a timestamp more than 3h in the *future* and WARNs
when one moves backwards by more than 5 minutes. It also once carried a third
check that compared the absolute difference -- that one never fired at all
(its regex did not match a LOG line) and was removed in v7.99.0. This line
said "WARNs on >3h drift" until v7.101.0, describing neither the severity nor
the check that actually exists. Violated this session: wrote 07:55-08:25 timestamps when UTC was
~01:21.

## Never skip REVIEW phase STATE update

BUILD -> VERIFY -> REVIEW -> SHIP -> DONE. Each phase gets its own STATE.md
entry, even if REVIEW is a quick diff check. Skipping it (going VERIFY -> SHIP
without `phase: REVIEW`) creates a jump the protocol's transition table
doesn't show. Violated this session on T-200 and T-202.

## Readers that skip junctions

`~/.agents/skills` (FreeBuff-class) and Antigravity plugin dirs only see
real directories with lowercase names — junctions/symlinks are ignored, and
the IDE holds a lock so junctions can't even be created while it runs. The
injector copies files there instead, which means those copies go stale:
re-run `inject.ps1` after every `git pull`.
