#!/usr/bin/env python
"""Install the saipen pre-commit validation hook into the current repo.

Stdlib only. Run from a project root that has both .git/ and .saipen/:

    python <saipen-home>/tools/install_hook.py

The hook runs tools/validate.py before every commit and blocks the commit
on structural corruption -- the checkpoint files can't rot silently
between ships. Bypass a false positive with `git commit --no-verify`.

The validator is found in this order: the SAIPEN home baked in at install
time, then STATE.md's saipen_home field (survives the home moving), then
the frozen shell floor for hosts without Python.

To remove: python <saipen-home>/tools/uninstall_hook.py
"""

import sys
from pathlib import Path

MARKER = "# saipen pre-commit hook"

home = Path(__file__).resolve().parent.parent
hooks_dir = Path(".git/hooks")

git_path = Path(".git")
if git_path.is_file():
    # Linked worktree: .git is a pointer file and hooks live in the MAIN repo, shared by every
    # worktree -- installing from here is neither possible nor needed.
    print("FAIL: this is a linked git worktree (.git is a file) -- run "
          "from the main checkout instead; worktrees share its hooks "
          "automatically")
    sys.exit(1)
if not git_path.is_dir():
    print("FAIL: no .git here -- run from the project root of a git repo")
    sys.exit(1)
if not Path(".saipen").is_dir():
    print("FAIL: no .saipen here -- nothing for the hook to validate")
    sys.exit(1)

# sh handles Windows drive paths fine under git's shell; forward slashes
# keep it out of escaping trouble on every platform.
home_sh = str(home).replace("\\", "/")

hook = f"""#!/bin/sh
{MARKER}
# Validates .saipen/ before every commit; installed by tools/install_hook.py.
# Bypass a false positive with: git commit --no-verify
[ -d .saipen ] || exit 0

SAIPEN_HOME="{home_sh}"
if [ ! -f "$SAIPEN_HOME/tools/validate.py" ]; then
  # Home moved since install -- fall back to STATE.md's saipen_home field.
  SAIPEN_HOME=$(sed -n 's/^saipen_home:[ \\t]*"\\{{0,1\\}}\\([^"]*\\)"\\{{0,1\\}}[ \\t]*$/\\1/p' .saipen/STATE.md | head -1 | tr '\\\\' '/')
fi

if [ -f "$SAIPEN_HOME/tools/validate.py" ]; then
  if command -v python >/dev/null 2>&1; then
    python "$SAIPEN_HOME/tools/validate.py" && exit 0
    echo "saipen: validation failed -- fix .saipen/ or commit with --no-verify" >&2
    exit 1
  elif command -v py >/dev/null 2>&1; then
    py "$SAIPEN_HOME/tools/validate.py" && exit 0
    echo "saipen: validation failed -- fix .saipen/ or commit with --no-verify" >&2
    exit 1
  fi
fi
if [ -f "$SAIPEN_HOME/tests/validate.sh" ]; then
  sh "$SAIPEN_HOME/tests/validate.sh" && exit 0
  echo "saipen: validation failed -- fix .saipen/ or commit with --no-verify" >&2
  exit 1
fi
# No validator reachable -- never block commits on a broken install.
exit 0
"""

hooks_dir.mkdir(parents=True, exist_ok=True)
target = hooks_dir / "pre-commit"
if target.exists():
    existing = target.read_text(encoding="utf-8", errors="replace")
    if MARKER not in existing:
        backup = hooks_dir / "pre-commit.pre-saipen.bak"
        backup.write_text(existing, encoding="utf-8")
        print(f"note: existing non-saipen pre-commit hook backed up to {backup}")

target.write_text(hook, encoding="utf-8", newline="\n")
try:
    target.chmod(0o755)
except OSError:
    pass  # Windows: git runs hooks through sh regardless of mode bits
print(f"Installed: {target} (validator home: {home_sh})")
