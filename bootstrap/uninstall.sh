#!/usr/bin/env bash
# saipen uninstaller (macOS/Linux)
set -u

strip_block() {
  if [ -f "$1" ] && grep -q "SAIPEN:BEGIN" "$1"; then
    cp "$1" "$1.uninstalled.bak"
    sed -i.bak '/<!-- SAIPEN:BEGIN -->/,/<!-- SAIPEN:END -->/d' "$1" 2>/dev/null || sed -i '' '/<!-- SAIPEN:BEGIN -->/,/<!-- SAIPEN:END -->/d' "$1"
    rm -f "$1.bak"
    echo "block removed"
  else
    echo "clean"
  fi
}

rm_skill() {
  if [ -d "$1" ] || [ -L "$1" ]; then
    rm -rf "$1"
    echo "skill removed"
  else
    echo "clean"
  fi
}

rm_aider() {
  if [ -f "$1" ]; then
    if grep -q "# saipen protocol auto-loaded" "$1"; then
      cp "$1" "$1.uninstalled.bak"
      sed -i.bak '/# saipen protocol auto-loaded/d' "$1" 2>/dev/null || sed -i '' '/# saipen protocol auto-loaded/d' "$1"
      sed -i.bak '/read:/d' "$1" 2>/dev/null || sed -i '' '/read:/d' "$1"
      sed -i.bak '\|saipen/RFC\.md|d' "$1" 2>/dev/null || sed -i '' '\|saipen/RFC\.md|d' "$1"
      rm -f "$1.bak"
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
