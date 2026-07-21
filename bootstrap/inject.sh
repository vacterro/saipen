#!/usr/bin/env bash
# saipen injector (macOS/Linux) -- installs saipen as default on every agentic system found.
# Run from clone dir:  bash inject.sh
# Idempotent: re-run safe.

set -u
SKILL_HOME="$(cd "$(dirname "$0")/../saipen" 2>/dev/null && pwd)"
[ -f "$SKILL_HOME/RFC.md" ] || { echo "FATAL: saipen/RFC.md not found"; exit 1; }

backup_file() {
  [ -f "$1" ] && [ ! -f "$1.bak" ] && cp "$1" "$1.bak"
}

BLOCK="
<!-- SAIPEN:BEGIN -->
## saipen protocol (global)
On \"saipen set\" / \"saipen ...\" commands, or when project root contains
.saipen/: read $SKILL_HOME/RFC.md + $SKILL_HOME/STYLE.md and follow them.
Chat tone: caveman-ded (STYLE.md) - compressed + blunt, on by default,
off only on \"stop caveman\"/\"normal mode\".
Memory: .saipen/ at project root - read .saipen/STATE.md before work;
checkpoint BOARD + STATE after every ticket, LOG line after every run.
Path missing (new machine)? clone github.com/vacterro/saipen.
UI work: also obey $SKILL_HOME/UI.md (Win95 dark golden, Verdana, no AA).
<!-- SAIPEN:END -->"

add_block() { # $1=file
  # Compare content instead of stripping unconditionally, or every re-run
  # would rewrite an already-current block for no reason.
  if [ -f "$1" ] && grep -q "SAIPEN:BEGIN" "$1"; then
    local existing canonical
    existing=$(sed -n '/<!-- SAIPEN:BEGIN -->/,/<!-- SAIPEN:END -->/p' "$1")
    canonical=$(printf '%s\n' "$BLOCK" | sed -n '/<!-- SAIPEN:BEGIN -->/,/<!-- SAIPEN:END -->/p')
    if [ "$existing" = "$canonical" ]; then echo "already"; return; fi
    backup_file "$1"
    sed -i.bak '/<!-- SAIPEN:BEGIN -->/,/<!-- SAIPEN:END -->/d' "$1" 2>/dev/null || sed -i '' '/<!-- SAIPEN:BEGIN -->/,/<!-- SAIPEN:END -->/d' "$1"
    printf '%s\n' "$BLOCK" >> "$1"; echo "block refreshed"; return
  fi
  backup_file "$1"
  mkdir -p "$(dirname "$1")"; printf '%s\n' "$BLOCK" >> "$1"
  echo "block added"
}

copy_skill() { # $1=dst
  mkdir -p "$1"
  cp "$SKILL_HOME/SKILL.md" "$SKILL_HOME/RFC.md" "$SKILL_HOME/UI.md" "$SKILL_HOME/STYLE.md" "$1/"
  cp -r "$SKILL_HOME/phases" "$1/"
  # validate.py resolves the schema relative to itself (../extensions/schemas),
  # so both must travel together for the skill copy to validate standalone.
  # templates/ makes init.md's "copy, do NOT freehand" reachable; tests/ makes
  # validate.md's no-Python shell fallback reachable.
  local root; root="$(dirname "$SKILL_HOME")"
  cp -r "$root/tools" "$1/"
  mkdir -p "$1/extensions" "$1/tests"
  cp -r "$root/extensions/schemas" "$1/extensions/"
  cp -r "$root/extensions/templates" "$1/extensions/"
  cp "$root/tests/validate.sh" "$root/tests/validate.ps1" "$1/tests/"
  echo "copied (re-run after updates)"
}

echo "saipen injector (source: $SKILL_HOME)"
echo "------------------------------------------------------------"
[ -d "$HOME/.claude" ]          && { printf '%-28s %s\n' "Claude Code skill"     "$(copy_skill "$HOME/.claude/skills/saipen")";
                                     printf '%-28s %s\n' "Claude Code CLAUDE.md" "$(add_block "$HOME/.claude/CLAUDE.md")"; } \
                                || printf '%-28s %s\n' "Claude Code" "not installed - skip"
[ -d "$HOME/.config/opencode" ] && { printf '%-28s %s\n' "OpenCode skill"        "$(copy_skill "$HOME/.config/opencode/skills/saipen")";
                                     printf '%-28s %s\n' "OpenCode AGENTS.md"    "$(add_block "$HOME/.config/opencode/AGENTS.md")"; } \
                                || printf '%-28s %s\n' "OpenCode" "not installed - skip"
[ -d "$HOME/.codex" ]           && { printf '%-28s %s\n' "Codex skill"           "$(copy_skill "$HOME/.codex/skills/saipen")";
                                     printf '%-28s %s\n' "Codex AGENTS.md"       "$(add_block "$HOME/.codex/AGENTS.md")"; } \
                                || printf '%-28s %s\n' "Codex" "not installed - skip"
[ -d "$HOME/.gemini" ]          && printf '%-28s %s\n' "Gemini GEMINI.md"        "$(add_block "$HOME/.gemini/GEMINI.md")" \
                                || printf '%-28s %s\n' "Gemini" "not installed - skip"

if [ -d "$HOME/.agents/skills" ]; then # copy, lowercase: these readers skip links/uppercase
  printf '%-28s %s\n' "~/.agents skills" "$(copy_skill "$HOME/.agents/skills/saipen")"
else printf '%-28s %s\n' "~/.agents" "not installed - skip"; fi

# --- Antigravity plugins (copy: IDE locks dirs, junction impossible while open) ---
PLUG_ROOT="$HOME/.gemini/config/plugins"
if [ -d "$PLUG_ROOT" ]; then
  for plugin_dir in "$PLUG_ROOT"/*/; do
    [ -d "$plugin_dir" ] || continue
    plugin_name="$(basename "$plugin_dir")"
    skills_dir="${plugin_dir}skills"
    if [ -d "$skills_dir" ]; then
      printf '%-28s %s\n' "Antigravity [$plugin_name]" "$(copy_skill "$skills_dir/saipen")"
    fi
  done
fi

# Aider boot set is RFC.md + STYLE.md, same promise as every platform.
if command -v aider >/dev/null 2>&1; then
  A="$HOME/.aider.conf.yml"
  P="$SKILL_HOME/RFC.md"
  S="$SKILL_HOME/STYLE.md"
  if [ ! -f "$A" ]; then printf '# saipen protocol auto-loaded\nread:\n  - %s\n  - %s\n' "$P" "$S" > "$A"; printf '%-28s %s\n' "Aider conf" "created"
  elif grep -qF "$P" "$A" && grep -qF "$S" "$A"; then printf '%-28s %s\n' "Aider conf" "already"
  elif ! grep -q "^read:" "$A"; then
    backup_file "$A"
    printf '\n# saipen protocol auto-loaded\nread:\n  - %s\n  - %s\n' "$P" "$S" >> "$A"; printf '%-28s %s\n' "Aider conf" "read: appended"
  else printf '%-28s %s\n' "Aider conf" "has own read: - add manually: $P + $S"; fi
else printf '%-28s %s\n' "Aider" "not installed - skip"; fi

echo "------------------------------------------------------------"
echo "Done. Test: open any project in any agent, say: saipen set"
