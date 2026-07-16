#!/usr/bin/env bash
# asp injector (macOS/Linux) вЂ” installs asp as default on every agentic system found.
# Run from clone dir:  bash inject.sh
# Idempotent: re-run safe. Also migrates pre-3.0 installs named "VAC".

set -u
SKILL_HOME="$(cd "$(dirname "$0")/vacskill" 2>/dev/null && pwd)"
[ -f "$SKILL_HOME/PROTOCOL.md" ] || { echo "FATAL: asp/PROTOCOL.md not found"; exit 1; }

BLOCK="
<!-- VACSKILL:BEGIN -->
## asp protocol (global)
On \"asp SET\" / \"asp ...\" (short alias \"vac ...\") commands, or when
project root contains .asp/: read $SKILL_HOME/PROTOCOL.md + $SKILL_HOME/STYLE.md
and follow them.
Memory: .asp/ at project root - read .asp/STATE.md before work;
checkpoint BOARD + STATE after every ticket, LOG line after every run.
Path missing (new machine)? clone github.com/vacterro/vacskill.
UI work: also obey $SKILL_HOME/UI.md (Win95 dark golden, Verdana, no AA).
<!-- VACSKILL:END -->"

# Pre-3.0 block points at the old VAC/ folder вЂ” strip it before adding the new one.
strip_legacy_block() { # $1=file
  [ -f "$1" ] || return 1
  grep -q '<!-- VAC:BEGIN -->' "$1" || return 1
  sed -i.bak '/<!-- VAC:BEGIN -->/,/<!-- VAC:END -->/d' "$1" && rm -f "$1.bak"
  return 0
}

add_block() { # $1=file
  local migrated=1
  strip_legacy_block "$1" && migrated=0
  if [ -f "$1" ] && grep -q "VACSKILL:BEGIN" "$1"; then
    if grep -q "PROTOCOL\.md" "$1"; then echo "already"; return; fi
    # 3.x block points at SKILL.md вЂ” replace with PROTOCOL.md block
    sed -i.bak '/<!-- VACSKILL:BEGIN -->/,/<!-- VACSKILL:END -->/d' "$1" && rm -f "$1.bak"
    printf '%s\n' "$BLOCK" >> "$1"; echo "block upgraded to PROTOCOL.md"; return
  fi
  mkdir -p "$(dirname "$1")"; printf '%s\n' "$BLOCK" >> "$1"
  [ $migrated -eq 0 ] && echo "migrated from VAC" || echo "block added"
}

# Remove a pre-3.0 skill dir: symlinks always, real dirs only if ours.
rm_legacy() { # $1=path
  [ -e "$1" ] || return 1
  if [ -L "$1" ]; then rm "$1"; return 0; fi
  if [ -f "$1/SKILL.md" ] && grep -qE '^name: *(VAC|vacskill) *$' "$1/SKILL.md"; then
    rm -rf "$1"; return 0
  fi
  return 1
}

add_link() { # $1=target $2=legacy
  [ -n "${2:-}" ] && rm_legacy "$2"
  if [ -L "$1" ] && [ -f "$1/SKILL.md" ]; then echo "already"; return; fi
  rm_legacy "$1"
  if [ -e "$1" ]; then echo "exists, not asp - check manually"; return; fi
  mkdir -p "$(dirname "$1")"
  ln -s "$SKILL_HOME" "$1" && echo "symlink created" || echo "FAILED"
}

copy_skill() { # $1=dst $2=legacy
  [ -n "${2:-}" ] && rm_legacy "$2"
  mkdir -p "$1"
  cp "$SKILL_HOME/SKILL.md" "$SKILL_HOME/PROTOCOL.md" "$SKILL_HOME/UI.md" "$SKILL_HOME/STYLE.md" "$1/"
}

echo "asp injector (source: $SKILL_HOME)"
echo "------------------------------------------------------------"
[ -d "$HOME/.claude" ]          && { printf '%-28s %s\n' "Claude Code skill"     "$(add_link "$HOME/.claude/skills/vacskill" "$HOME/.claude/skills/VAC")";
                                     printf '%-28s %s\n' "Claude Code CLAUDE.md" "$(add_block "$HOME/.claude/CLAUDE.md")"; } \
                                || printf '%-28s %s\n' "Claude Code" "not installed - skip"
[ -d "$HOME/.config/opencode" ] && { printf '%-28s %s\n' "OpenCode skill"        "$(add_link "$HOME/.config/opencode/skills/vacskill" "$HOME/.config/opencode/skills/vac")";
                                     printf '%-28s %s\n' "OpenCode AGENTS.md"    "$(add_block "$HOME/.config/opencode/AGENTS.md")"; } \
                                || printf '%-28s %s\n' "OpenCode" "not installed - skip"
[ -d "$HOME/.codex" ]           && { printf '%-28s %s\n' "Codex skill"           "$(add_link "$HOME/.codex/skills/vacskill" "$HOME/.codex/skills/vac")";
                                     printf '%-28s %s\n' "Codex AGENTS.md"       "$(add_block "$HOME/.codex/AGENTS.md")"; } \
                                || printf '%-28s %s\n' "Codex" "not installed - skip"
[ -d "$HOME/.gemini" ]          && printf '%-28s %s\n' "Gemini GEMINI.md"        "$(add_block "$HOME/.gemini/GEMINI.md")" \
                                || printf '%-28s %s\n' "Gemini" "not installed - skip"

if [ -d "$HOME/.agents/skills" ]; then # copy, lowercase: these readers skip links/uppercase
  rm_legacy "$HOME/.agents/skills/VAC"
  copy_skill "$HOME/.agents/skills/vacskill" "$HOME/.agents/skills/vac"
  printf '%-28s %s\n' "~/.agents skills" "copied (re-run after updates)"
else printf '%-28s %s\n' "~/.agents" "not installed - skip"; fi

if command -v aider >/dev/null 2>&1; then
  A="$HOME/.aider.conf.yml"
  P="$SKILL_HOME/PROTOCOL.md"
  if [ ! -f "$A" ]; then printf '# asp protocol auto-loaded\nread:\n  - %s\n' "$P" > "$A"; printf '%-28s %s\n' "Aider conf" "created"
  elif grep -qE '/(VAC|vacskill)/SKILL\.md' "$A"; then
    sed -i.bak "s#.*/\(VAC\|asp\)/SKILL\.md#  - $P#" "$A" && rm -f "$A.bak"
    printf '%-28s %s\n' "Aider conf" "migrated to PROTOCOL.md"
  elif grep -qF "$P" "$A"; then printf '%-28s %s\n' "Aider conf" "already"
  elif ! grep -q "^read:" "$A"; then printf '\n# asp protocol auto-loaded\nread:\n  - %s\n' "$P" >> "$A"; printf '%-28s %s\n' "Aider conf" "read: appended"
  else printf '%-28s %s\n' "Aider conf" "has own read: - add manually: $P"; fi
else printf '%-28s %s\n' "Aider" "not installed - skip"; fi

echo "------------------------------------------------------------"
echo "Done. Test: open any project in any agent, say: asp SET"
