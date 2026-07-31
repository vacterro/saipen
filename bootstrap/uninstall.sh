#!/usr/bin/env bash
# saipen uninstaller (macOS/Linux)
set -u
FAILURES=0
END_MARKER='<!-- SAIPEN:END -->'

strip_block() {
  # sed's in-place suffix MUST NOT be plain .bak: inject.sh's backup_file()
  # already owns "$1.bak" and put the user's ORIGINAL, pre-SAIPEN file there.
  # Using -i.bak here would overwrite that original with the current
  # SAIPEN-containing content, and the cleanup rm would then delete it --
  # uninstalling would silently destroy the very backup installing made.
  if [ -f "$1" ] && grep -q "SAIPEN:BEGIN" "$1"; then
    # Deleting only BEGIN..END is not a clean reverse of what inject.sh did:
    # its $BLOCK starts with a newline, so each install adds one blank line
    # that a plain range-delete leaves behind. Measured: install+uninstall
    # five times grew a 2-line CLAUDE.md to 7 lines, one stray line per
    # cycle, forever -- while README promises we leave the rest of the file
    # alone. Drop exactly ONE newline immediately before BEGIN (the one we
    # added) and the newline after END, copying every other byte untouched.
    # Text processors are wrong here: Git Bash awk converts CRLF to LF.
    cp "$1" "$1.uninstalled.bak" \
      || { echo "backup FAILED ($1)"; return 1; }
    local begin_line end_line begin end file_size prefix_count suffix_start
    begin_line=$(grep -b -m1 '^<!-- SAIPEN:BEGIN -->' "$1") \
      || { echo "block BEGIN read FAILED ($1)"; return 1; }
    end_line=$(grep -b -m1 '^<!-- SAIPEN:END -->' "$1") \
      || { echo "block END read FAILED ($1)"; return 1; }
    begin=${begin_line%%:*}
    end=${end_line%%:*}
    file_size=$(wc -c < "$1") \
      || { echo "block size read FAILED ($1)"; return 1; }
    prefix_count=$((begin > 0 ? begin - 1 : 0))
    suffix_start=$((end + ${#END_MARKER} + 1))
    : > "$1.saipen-strip-tmp" \
      && { [ "$prefix_count" -eq 0 ] || head -c "$prefix_count" "$1" >> "$1.saipen-strip-tmp"; } \
      && { [ "$suffix_start" -ge "$file_size" ] || tail -c "+$((suffix_start + 1))" "$1" >> "$1.saipen-strip-tmp"; } \
      && mv "$1.saipen-strip-tmp" "$1" \
      || { rm -f "$1.saipen-strip-tmp" 2>/dev/null || true; echo "block remove FAILED ($1)"; return 1; }
    echo "block removed"
  else
    echo "clean"
  fi
}

rm_skill() {
  if [ -d "$1" ] || [ -L "$1" ]; then
    if rm -rf "$1"; then
      echo "skill removed"
    else
      echo "remove FAILED ($1)"
      return 1
    fi
  else
    echo "clean"
  fi
}

rm_aider() {
  # Remove exactly the block the injector wrote: the comment line, the
  # read: key that immediately follows it, and the consecutive saipen
  # RFC/STYLE items -- never any other read: line the user owns.
  if [ -f "$1" ]; then
    if grep -q "# saipen protocol auto-loaded" "$1"; then
      cp "$1" "$1.uninstalled.bak" \
        || { echo "backup FAILED ($1)"; return 1; }
      awk '
        /^# saipen protocol auto-loaded$/ { inblk = 1; next }
        inblk && /^read:$/ { next }
        inblk && /^[[:space:]]*-[[:space:]].*saipen\/(RFC|STYLE)\.md$/ { next }
        { inblk = 0; print }
      ' "$1" > "$1.tmp" && mv "$1.tmp" "$1" \
        || { rm -f "$1.tmp" 2>/dev/null || true; echo "aider clean FAILED ($1)"; return 1; }
      echo "aider conf cleaned"
    elif grep -q "saipen/RFC.md" "$1"; then
      echo "manual aider conf (please remove manually)"
    else
      echo "clean"
    fi
  else
    echo "clean"
  fi
}

report() { # $1=label, remaining=function + args
  local label="$1" output status
  shift
  output=$("$@" 2>&1)
  status=$?
  printf '%-28s %s\n' "$label" "$output"
  [ "$status" -eq 0 ] || FAILURES=1
}

echo "saipen uninstaller"
echo "------------------------------------------------------------"
report "Claude Code skill" rm_skill "$HOME/.claude/skills/saipen"
report "Claude Code CLAUDE.md" strip_block "$HOME/.claude/CLAUDE.md"
report "OpenCode skill" rm_skill "$HOME/.config/opencode/skills/saipen"
report "OpenCode AGENTS.md" strip_block "$HOME/.config/opencode/AGENTS.md"
report "Codex skill" rm_skill "$HOME/.codex/skills/saipen"
report "Codex AGENTS.md" strip_block "$HOME/.codex/AGENTS.md"
report "Gemini GEMINI.md" strip_block "$HOME/.gemini/GEMINI.md"
report "~/.agents skills" rm_skill "$HOME/.agents/skills/saipen"
PLUG_ROOT="$HOME/.gemini/config/plugins"
if [ -d "$PLUG_ROOT" ]; then
  for plugin_dir in "$PLUG_ROOT"/*/; do
    [ -d "$plugin_dir" ] || continue
    plugin_name="$(basename "$plugin_dir")"
    report "Antigravity [$plugin_name]" rm_skill "${plugin_dir}skills/saipen"
  done
fi
report "Aider conf" rm_aider "$HOME/.aider.conf.yml"
echo "------------------------------------------------------------"
if [ "$FAILURES" -ne 0 ]; then
  echo "FAILED. Fix reported errors and re-run."
  exit 1
fi
echo "Done. SAIPEN global hooks removed."
