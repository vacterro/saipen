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

## Readers that skip junctions

`~/.agents/skills` (FreeBuff-class) and Antigravity plugin dirs only see
real directories with lowercase names — junctions/symlinks are ignored, and
the IDE holds a lock so junctions can't even be created while it runs. The
injector copies files there instead, which means those copies go stale:
re-run `inject.ps1` after every `git pull`.
