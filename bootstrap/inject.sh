#!/usr/bin/env bash
# saipen injector (macOS/Linux) -- installs saipen as default on every agentic system found.
# Run from clone dir:  bash inject.sh
# Idempotent: re-run safe.

set -u
FAILURES=0
SKILL_HOME="$(cd "$(dirname "$0")/../saipen" 2>/dev/null && pwd)"
# BOOT.md, not RFC.md: the sanity check must name the file the injected block
# actually sends agents to. RFC.md has been a redirect stub since the v7.190.0
# split, so a clone missing BOOT.md but carrying the stub would pass this guard
# and install an entry point with no rules behind it.
[ -f "$SKILL_HOME/BOOT.md" ] || { echo "FATAL: saipen/BOOT.md not found"; exit 1; }

# Under git bash / MSYS / Cygwin on Windows, `pwd` yields an MSYS path such as
# /v/proj/saipen. The agents that later READ these instructions are Windows
# programs, and they cannot open that form -- only the shell that produced it
# can. Writing it into CLAUDE.md hands every Windows user who ran the .sh
# injector a config pointing at files their agent will never find, and nothing
# reports an error: the block is present, the paths are simply dead.
# cygpath ships with git bash, so the conversion is free where it is needed
# and skipped entirely everywhere else.
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*)
    if command -v cygpath >/dev/null 2>&1; then
      SKILL_HOME="$(cygpath -w "$SKILL_HOME")"
    fi
    ;;
esac

ROOT="$(dirname "$SKILL_HOME")"
MANIFEST="$SKILL_HOME/MANIFEST.json"
[ -f "$MANIFEST" ] || { echo "FATAL: saipen/MANIFEST.json not found"; exit 1; }
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  echo "FATAL: Python is required to parse saipen/MANIFEST.json safely"
  exit 1
fi

manifest_query() {
  "$PYTHON_BIN" - "$MANIFEST" "$1" <<'PY'
import json
import sys
from pathlib import PurePosixPath

manifest_path, query = sys.argv[1:]
sys.stdout.reconfigure(newline="\n")
with open(manifest_path, encoding="utf-8") as handle:
    manifest = json.load(handle)

def safe(value):
    if not isinstance(value, str) or not value or "\\" in value or "|" in value:
        raise ValueError(f"unsafe runtime manifest path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe runtime manifest path: {value!r}")
    return value

managed = manifest.get("managed_dirs")
trees = manifest.get("copy_trees")
files = manifest.get("files")
phases = manifest.get("phase_docs", {}).get("files")
if not all(isinstance(group, list) and group for group in (managed, trees, files, phases)):
    raise ValueError("runtime manifest lacks nonempty managed_dirs/copy_trees/files/phase_docs.files")
managed = [safe(item) for item in managed]
trees = [(safe(item["src"]), safe(item["dst"])) for item in trees]
files = [safe(item["src"]) for item in files if item.get("required") is True]
phases = [safe(f"phases/{item}")[len("phases/"):] for item in phases]
if not files:
    raise ValueError("runtime manifest has no required files")
if query == "all":
    for item in managed:
        print(f"M|{item}|")
    for src, dst in trees:
        print(f"T|{src}|{dst}")
    for item in files:
        print(f"F|{item}|")
    for item in phases:
        print(f"P|{item}|")
else:
    raise ValueError(f"unknown manifest query: {query}")
PY
}

MANIFEST_ROWS=$(manifest_query all) \
  || { echo "FATAL: saipen/MANIFEST.json is invalid"; exit 1; }
[ -n "$MANIFEST_ROWS" ] \
  || { echo "FATAL: saipen/MANIFEST.json produced an empty inventory"; exit 1; }

install_rel() {
  case "$1" in
    saipen/*) printf '%s\n' "${1#saipen/}" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

backup_file() {
  if [ -f "$1" ] && [ ! -f "$1.bak" ]; then
    cp "$1" "$1.bak" || { echo "backup FAILED ($1)"; return 1; }
  fi
}

BLOCK="
<!-- SAIPEN:BEGIN -->
## saipen protocol (global)
On \"saipen set\" / \"saipen ...\" commands, or when project root contains
.saipen/: read $SKILL_HOME/BOOT.md (cold-start kernel) + $SKILL_HOME/STYLE.md
and follow them. BOOT.md routes on to INDEX.md, and to CORE.md when a rule
question comes up. RFC.md is a redirect stub - it holds no rules.
Chat tone: caveman-ded (STYLE.md) - compressed + blunt, on by default,
off only on \"stop caveman\"/\"normal mode\".
Memory: .saipen/ at project root - read .saipen/STATE.md before work;
checkpoint BOARD + STATE after every ticket, LOG line after every run.
Path missing (new machine)? clone github.com/vacterro/saipen.
Crew (bonus): a bare subSaipen name (saihunt/saipython/saiwiki) = adopt that
role and start working (extensions/subs/crew.md); saipen crew = 3-window layout.
UI work: also obey $SKILL_HOME/UI.md (Win95 dark golden, Verdana, no AA).
<!-- SAIPEN:END -->"

add_block() { # $1=file
  # Compare content instead of stripping unconditionally, or every re-run
  # would rewrite an already-current block for no reason.
  local marker_status=1
  if [ -f "$1" ]; then
    grep -q "SAIPEN:BEGIN" "$1"
    marker_status=$?
    [ "$marker_status" -le 1 ] \
      || { echo "block marker read FAILED ($1)"; return 1; }
  fi
  if [ "$marker_status" -eq 0 ]; then
    local existing canonical
    existing=$(sed -n '/<!-- SAIPEN:BEGIN -->/,/<!-- SAIPEN:END -->/p' "$1") \
      || { echo "block read FAILED ($1)"; return 1; }
    canonical=$(printf '%s\n' "$BLOCK" | sed -n '/<!-- SAIPEN:BEGIN -->/,/<!-- SAIPEN:END -->/p') \
      || { echo "block render FAILED ($1)"; return 1; }
    if [ "$existing" = "$canonical" ]; then echo "already"; return; fi
    backup_file "$1" || return 1
    # sed's in-place suffix MUST NOT be plain .bak: backup_file() above owns
    # "$1.bak" and put the user's ORIGINAL, pre-SAIPEN file there on the FIRST
    # install. Using -i.bak here would overwrite that original with the
    # current, already-SAIPEN-containing content on every later refresh --
    # silently destroying the only copy of what the user had before us.
    # (Reproduced live 2026-07-26. uninstall.sh:6-10 carries the same warning
    # and inject.ps1's Write-NoBom is guarded; this was the last of the four.)
    if sed -i.saipen-strip-tmp '/<!-- SAIPEN:BEGIN -->/,/<!-- SAIPEN:END -->/d' "$1" 2>/dev/null \
       || sed -i '' '/<!-- SAIPEN:BEGIN -->/,/<!-- SAIPEN:END -->/d' "$1"; then
      rm -f "$1.saipen-strip-tmp" \
        || { echo "block cleanup FAILED ($1)"; return 1; }
    else
      rm -f "$1.saipen-strip-tmp" 2>/dev/null || true
      echo "block refresh FAILED ($1)"
      return 1
    fi
    printf '%s\n' "$BLOCK" >> "$1" \
      || { echo "block write FAILED ($1)"; return 1; }
    echo "block refreshed"
    return 0
  fi
  backup_file "$1" || return 1
  mkdir -p "$(dirname "$1")" \
    || { echo "directory create FAILED ($1)"; return 1; }
  printf '%s\n' "$BLOCK" >> "$1" \
    || { echo "block write FAILED ($1)"; return 1; }
  echo "block added"
}

build_skill_stage() { # $1=empty stage
  local stage="$1"
  local kind src rel target symlink
  while IFS='|' read -r kind src rel; do
    case "$kind" in
      M|P) ;;
      T)
        [ -d "$ROOT/$src" ] \
          || { echo "runtime manifest tree missing: $src"; return 1; }
        symlink=$(find "$ROOT/$src" -type l -print -quit) \
          || { echo "runtime manifest tree scan failed: $src"; return 1; }
        [ -z "$symlink" ] \
          || { echo "runtime manifest tree contains symlink: $symlink"; return 1; }
        target="$stage/$rel"
        mkdir -p "$(dirname "$target")" \
          && cp -R "$ROOT/$src" "$target" \
          || { echo "tree copy failed: $src"; return 1; }
        ;;
      F)
        rel="$(install_rel "$src")"
        [ -f "$ROOT/$src" ] \
          || { echo "runtime manifest file missing: $src"; return 1; }
        [ ! -L "$ROOT/$src" ] \
          || { echo "runtime manifest file is a symlink: $src"; return 1; }
        target="$stage/$rel"
        mkdir -p "$(dirname "$target")" \
          && cp "$ROOT/$src" "$target" \
          || { echo "file copy failed: $src"; return 1; }
        ;;
      *) echo "runtime manifest cache contains unknown row: $kind"; return 1 ;;
    esac
  done <<< "$MANIFEST_ROWS"

  find "$stage" -type d -name __pycache__ -prune -exec rm -rf {} + \
    && find "$stage" -type f \( -name '*.pyc' -o -name '*.pyo' \) -exec rm -f {} + \
    || { echo "bytecode cleanup failed"; return 1; }

  while IFS='|' read -r kind src rel; do
    case "$kind" in
      F)
        rel="$(install_rel "$src")"
        [ -f "$stage/$rel" ] \
          || { echo "staged runtime file missing: $src"; return 1; }
        ;;
      P)
        [ -f "$stage/phases/$src" ] \
          || { echo "staged phase document missing: $src"; return 1; }
        ;;
    esac
  done <<< "$MANIFEST_ROWS"
}

copy_skill() { # $1=dst
  # Build and verify a sibling stage before moving the old install. A failed
  # copy therefore leaves the active skill byte-for-byte untouched.
  local dst="${1%/}"
  [ -n "$dst" ] && [ "$dst" != "/" ] && [ "$dst" != "." ] || {
    echo "copy FAILED ($1) -- unsafe destination"; return 1
  }
  local parent leaf stage backup had_old=0
  parent="$(dirname "$dst")"
  leaf="$(basename "$dst")"
  stage="$parent/.$leaf.saipen-stage-$$"
  backup="$parent/.$leaf.saipen-backup-$$"
  mkdir -p "$parent" \
    || { echo "copy FAILED ($1) -- create destination parent"; return 1; }
  if [ -e "$stage" ] || [ -L "$stage" ] || [ -e "$backup" ] || [ -L "$backup" ]; then
    echo "copy FAILED ($1) -- stale staging/backup path exists; inspect before retry"
    return 1
  fi
  mkdir "$stage" \
    || { echo "copy FAILED ($1) -- create staging directory"; return 1; }
  if ! build_skill_stage "$stage"; then
    rm -rf "$stage" 2>/dev/null || true
    echo "copy FAILED ($1) -- staged copy or verification failed"
    return 1
  fi
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    mv "$dst" "$backup" \
      || { rm -rf "$stage" 2>/dev/null || true; echo "copy FAILED ($1) -- preserve active install"; return 1; }
    had_old=1
  fi
  if ! mv "$stage" "$dst"; then
    [ "$had_old" -eq 0 ] || mv "$backup" "$dst" 2>/dev/null || true
    rm -rf "$stage" 2>/dev/null || true
    echo "copy FAILED ($1) -- activate staged install; old install restored"
    return 1
  fi
  if [ "$had_old" -eq 1 ] && ! rm -rf "$backup"; then
    echo "copy FAILED ($1) -- new install active but old backup cleanup failed: $backup"
    return 1
  fi
  echo "copied (re-run after updates)"
}

report() { # $1=label, remaining=function + args
  local label="$1" output status
  shift
  output=$("$@" 2>&1)
  status=$?
  printf '%-28s %s\n' "$label" "$output"
  [ "$status" -eq 0 ] || FAILURES=1
}

configure_aider() { # $1=config
  local A="$1" P="$SKILL_HOME/BOOT.md" S="$SKILL_HOME/STYLE.md"
  if [ ! -f "$A" ]; then
    mkdir -p "$(dirname "$A")" \
      && printf '# saipen protocol auto-loaded\nread:\n  - %s\n  - %s\n' "$P" "$S" > "$A" \
      || { echo "create FAILED ($A)"; return 1; }
    echo "created"
  else
    local p_status s_status read_status
    grep -qF "$P" "$A"; p_status=$?
    grep -qF "$S" "$A"; s_status=$?
    [ "$p_status" -le 1 ] && [ "$s_status" -le 1 ] \
      || { echo "read check FAILED ($A)"; return 1; }
    if [ "$p_status" -eq 0 ] && [ "$s_status" -eq 0 ]; then
      echo "already"
      return 0
    fi
    grep -q "^read:" "$A"; read_status=$?
    [ "$read_status" -le 1 ] \
      || { echo "read key check FAILED ($A)"; return 1; }
    if [ "$read_status" -eq 1 ]; then
      backup_file "$A" || return 1
      # Always add one separator byte. uninstall.sh removes that exact byte
      # with byte offsets, preserving CRLF/LF and surrounding user content.
      printf '\n# saipen protocol auto-loaded\nread:\n  - %s\n  - %s\n' "$P" "$S" >> "$A" \
        || { echo "write FAILED ($A)"; return 1; }
      echo "read: appended"
    else
      echo "has own read: - add manually: $P + $S"
    fi
  fi
}

echo "saipen injector (source: $SKILL_HOME)"
echo "------------------------------------------------------------"
[ -d "$HOME/.claude" ]          && { report "Claude Code skill" copy_skill "$HOME/.claude/skills/saipen";
                                     report "Claude Code CLAUDE.md" add_block "$HOME/.claude/CLAUDE.md"; } \
                                || printf '%-28s %s\n' "Claude Code" "not installed - skip"
[ -d "$HOME/.config/opencode" ] && { report "OpenCode skill" copy_skill "$HOME/.config/opencode/skills/saipen";
                                     report "OpenCode AGENTS.md" add_block "$HOME/.config/opencode/AGENTS.md"; } \
                                || printf '%-28s %s\n' "OpenCode" "not installed - skip"
[ -d "$HOME/.codex" ]           && { report "Codex skill" copy_skill "$HOME/.codex/skills/saipen";
                                     report "Codex AGENTS.md" add_block "$HOME/.codex/AGENTS.md"; } \
                                || printf '%-28s %s\n' "Codex" "not installed - skip"
[ -d "$HOME/.gemini" ]          && report "Gemini GEMINI.md" add_block "$HOME/.gemini/GEMINI.md" \
                                || printf '%-28s %s\n' "Gemini" "not installed - skip"

if [ -d "$HOME/.agents/skills" ]; then # copy, lowercase: these readers skip links/uppercase
  report "~/.agents skills" copy_skill "$HOME/.agents/skills/saipen"
else printf '%-28s %s\n' "~/.agents" "not installed - skip"; fi

# --- Antigravity plugins (copy: IDE locks dirs, junction impossible while open) ---
PLUG_ROOT="$HOME/.gemini/config/plugins"
if [ -d "$PLUG_ROOT" ]; then
  for plugin_dir in "$PLUG_ROOT"/*/; do
    [ -d "$plugin_dir" ] || continue
    plugin_name="$(basename "$plugin_dir")"
    skills_dir="${plugin_dir}skills"
    if [ -d "$skills_dir" ]; then
      report "Antigravity [$plugin_name]" copy_skill "$skills_dir/saipen"
    fi
  done
fi

# Aider boot set is BOOT.md + STYLE.md, same promise as every platform.
if command -v aider >/dev/null 2>&1; then
  report "Aider conf" configure_aider "$HOME/.aider.conf.yml"
else printf '%-28s %s\n' "Aider" "not installed - skip"; fi

echo "------------------------------------------------------------"
if [ "$FAILURES" -ne 0 ]; then
  echo "FAILED. Fix reported errors and re-run."
  exit 1
fi
echo "Done. Test: open any project in any agent, say: saipen set"
