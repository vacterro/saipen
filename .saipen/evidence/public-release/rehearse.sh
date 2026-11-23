#!/usr/bin/env bash
# Public-release rehearsal: fresh clone -> install -> set -> continue ->
# validate -> uninstall -> reinstall, in a throwaway HOME and project.
# Nothing here touches the maintainer's real HOME.
set -u

SRC_REPO="${1:?usage: rehearse.sh <repo-to-clone> <scratch-root>}"
SCRATCH="${2:?usage: rehearse.sh <repo-to-clone> <scratch-root>}"
CLONE="$SCRATCH/clone"
SANDBOX_HOME="$SCRATCH/home"
PROJECT="$SCRATCH/project"
LOG="$SCRATCH/rehearsal.log"

step=0
fail=0

say()  { printf '%s\n' "$*" | tee -a "$LOG"; }
ok()   { step=$((step+1)); say ""; say "=== [$step] PASS: $* ==="; }
bad()  { fail=$((fail+1)); say ""; say "!!! [$step] FAIL: $* !!!"; }
gate() { if [ "$1" = "0" ]; then ok "$2"; else bad "$2"; fi }

: > "$LOG"
rm -rf "$SCRATCH"
mkdir -p "$SANDBOX_HOME" "$PROJECT"

export HOME="$SANDBOX_HOME"
export USERPROFILE="$SANDBOX_HOME"
export LOCALAPPDATA="$SANDBOX_HOME/AppData/Local"
export XDG_CONFIG_HOME="$SANDBOX_HOME/.config"
export SAIPEN_USER_CONFIG_HOME="$SANDBOX_HOME/.saipen-user"
export SAIPEN_UNINSTALL_SKIP_TASK=1
export PYTHONUTF8=1
export PYTHONDONTWRITEBYTECODE=1
export SAIPEN_PYTHON="${SAIPEN_PYTHON:-python}"
unset ZAICODE_HOME

say "scratch: $SCRATCH"
say "HOME:    $HOME"

# ---------------------------------------------------------------- 1. clone
say ""; say "=== [1] fresh clone ==="
git clone --quiet "$SRC_REPO" "$CLONE" 2>&1 | tee -a "$LOG"
gate $? "git clone"
size=$(du -sm "$CLONE" 2>/dev/null | cut -f1)
files=$(git -C "$CLONE" ls-files | wc -l | tr -d ' ')
say "clone size: ${size} MB, ${files} tracked files"
[ -f "$CLONE/bootstrap/inject.sh" ]; gate $? "inject.sh present in clone"
[ -f "$CLONE/bin/saipen" ] && bad "repo still ships a tracked bin/ launcher" || ok "repo ships no tracked bin/ launcher"

# ------------------------------------------------------------- 2. install
say ""; say "=== [2] install ==="
( cd "$CLONE" && bash bootstrap/inject.sh ) >>"$LOG" 2>&1
gate $? "bash bootstrap/inject.sh"

LAUNCH="$SANDBOX_HOME/.agents/skills/saipen/bin/saipen"
if [ -x "$LAUNCH" ] || [ -f "$LAUNCH" ]; then ok "installed launcher at .agents/skills/saipen/bin/saipen"; else bad "installed launcher missing: $LAUNCH"; fi

# A user marker the install must not touch, and a SAIPEN block it must add.
mkdir -p "$SANDBOX_HOME/.claude"
printf 'my own claude notes\n' > "$SANDBOX_HOME/.claude/CLAUDE.md"
grep -q "SAIPEN:BEGIN" "$SANDBOX_HOME/.claude/CLAUDE.md" && bad "installer clobbered a pre-existing CLAUDE.md" || ok "installer did not clobber a pre-existing CLAUDE.md"

# The installed runtime must point at the INSTALLED engine, not the clone.
if grep -q "$CLONE" "$LAUNCH" 2>/dev/null; then bad "installed launcher still names the source clone"; else ok "installed launcher points at the installed engine"; fi

# ---------------------------------------------------------------- 3. set
say ""; say "=== [3] saipen set ==="
( cd "$PROJECT" && "$LAUNCH" set ) >>"$LOG" 2>&1
gate $? "saipen set"
[ -f "$PROJECT/.saipen/STATE.md" ]; gate $? "set created .saipen/STATE.md"

# ----------------------------------------------------------- 4. continue
say ""; say "=== [4] saipen continue (cold start) ==="
( cd "$PROJECT" && "$LAUNCH" continue ) >>"$LOG" 2>&1
gate $? "saipen continue"

# ------------------------------------------------------------ 5. validate
say ""; say "=== [5] saipen validate ==="
( cd "$PROJECT" && "$LAUNCH" validate ) >>"$LOG" 2>&1
gate $? "saipen validate"
grep -qi "PASS\|conformant" "$LOG" && ok "validate reported PASS" || bad "validate did not report PASS"

# ---------------------------------------------------------- 6. uninstall
say ""; say "=== [6] uninstall ==="
( cd "$CLONE" && bash bootstrap/uninstall.sh ) >>"$LOG" 2>&1
gate $? "bash bootstrap/uninstall.sh"

[ -f "$PROJECT/.saipen/STATE.md" ]; gate $? "project .saipen/ memory survived uninstall"
grep -q "SAIPEN:BEGIN" "$SANDBOX_HOME/.claude/CLAUDE.md" && bad "marked block left behind in CLAUDE.md" || ok "marked block removed from CLAUDE.md"
grep -q "my own claude notes" "$SANDBOX_HOME/.claude/CLAUDE.md"; gate $? "user's own CLAUDE.md content survived"
[ -e "$LAUNCH" ]; [ $? -ne 0 ] && ok "installed launcher removed" || bad "installed launcher still present after uninstall"

# A file the user dropped INTO the skill dir must survive removal.
mkdir -p "$SANDBOX_HOME/.agents/skills/saipen"
printf 'my notes\n' > "$SANDBOX_HOME/.agents/skills/saipen/MY-NOTES.md"

# ----------------------------------------------------------- 7. reinstall
say ""; say "=== [7] reinstall ==="
( cd "$CLONE" && bash bootstrap/inject.sh ) >>"$LOG" 2>&1
gate $? "reinstall"
[ -f "$LAUNCH" ]; gate $? "launcher present after reinstall"
[ -f "$SANDBOX_HOME/.agents/skills/saipen/MY-NOTES.md" ]; gate $? "user file inside the skill dir survived reinstall"

# --------------------------------------------------- 8. post-reinstall pass
say ""; say "=== [8] validate after reinstall ==="
( cd "$PROJECT" && "$LAUNCH" validate ) >>"$LOG" 2>&1
gate $? "validate after reinstall"

say ""
say "==================================================="
say "steps passed: $step   steps failed: $fail"
say "log: $LOG"
[ "$fail" -eq 0 ] || exit 1
exit 0
