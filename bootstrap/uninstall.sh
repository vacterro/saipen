#!/usr/bin/env bash
# saipen uninstaller (macOS/Linux)
set -u

strip_block() {
  # sed's in-place suffix MUST NOT be plain .bak: inject.sh's backup_file()
  # already owns "$1.bak" and put the user's ORIGINAL, pre-SAIPEN file there.
  # Using -i.bak here would overwrite that original with the current
  # SAIPEN-containing content, and the cleanup rm would then delete it --
  # uninstalling would silently destroy the very backup installing made.
  if [ -f "$1" ] && grep -q "SAIPEN:BEGIN" "$1"; then
    cp "$1" "$1.uninstalled.bak"
    sed -i.saipen-strip-tmp '/<!-- SAIPEN:BEGIN -->/,/<!-- SAIPEN:END -->/d' "$1" 2>/dev/null || sed -i '' '/<!-- SAIPEN:BEGIN -->/,/<!-- SAIPEN:END -->/d' "$1"
    rm -f "$1.saipen-strip-tmp"
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
      cp "$1" "$1.uninstalled.bak"
      awk '
        /^# saipen protocol auto-loaded$/ { inblk = 1; next }
        inblk && /^read:$/ { next }
        inblk && /^[[:space:]]*-[[:space:]].*saipen\/(RFC|STYLE)\.md$/ { next }
        { inblk = 0; print }
      ' "$1" > "$1.tmp" && mv "$1.tmp" "$1"
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

echo "saipen uninstaller"
echo "------------------------------------------------------------"
printf '%-28s %s\n' "Claude Code skill"     "$(rm_skill "$HOME/.claude/skills/saipen")"
printf '%-28s %s\n' "Claude Code CLAUDE.md" "$(strip_block "$HOME/.claude/CLAUDE.md")"
printf '%-28s %s\n' "OpenCode skill"        "$(rm_skill "$HOME/.config/opencode/skills/saipen")"
printf '%-28s %s\n' "OpenCode AGENTS.md"    "$(strip_block "$HOME/.config/opencode/AGENTS.md")"
printf '%-28s %s\n' "Codex skill"           "$(rm_skill "$HOME/.codex/skills/saipen")"
printf '%-28s %s\n' "Codex AGENTS.md"       "$(strip_block "$HOME/.codex/AGENTS.md")"
printf '%-28s %s\n' "Gemini GEMINI.md"        "$(strip_block "$HOME/.gemini/GEMINI.md")"
printf '%-28s %s\n' "~/.agents skills" "$(rm_skill "$HOME/.agents/skills/saipen")"
PLUG_ROOT="$HOME/.gemini/config/plugins"
if [ -d "$PLUG_ROOT" ]; then
  for plugin_dir in "$PLUG_ROOT"/*/; do
    [ -d "$plugin_dir" ] || continue
    plugin_name="$(basename "$plugin_dir")"
    printf '%-28s %s\n' "Antigravity [$plugin_name]" "$(rm_skill "${plugin_dir}skills/saipen")"
  done
fi
printf '%-28s %s\n' "Aider conf" "$(rm_aider "$HOME/.aider.conf.yml")"
echo "------------------------------------------------------------"
echo "Done. SAIPEN global hooks removed."
