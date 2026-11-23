"""T-1668 REVIEW: the detail_ref check against copies of every managed project.

Usage: downstream_validate.py <repo> <copies-dir> <work>

<copies-dir> holds `<name>/.saipen` copies of the managed projects (taken for
T-1679's diff). Two engines, both at foreign paths so neither is any copy's
home: an unmodified copy of <repo>, and the same copy with the T-1668 hunk of
tools/validate.py taken out. Each runs `validate.py --gate core` on every
copy; FAIL lines are compared with numbers masked.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

repo, copies, work = (Path(arg).resolve() for arg in sys.argv[1:4])
assert not work.exists(), work


def ignore(_d, names):
    return [n for n in names if n in {"__pycache__", ".ruff_cache"} or n.endswith(".pyc")]


engines = {}
for name in ("after", "before"):
    target = work / name
    for part in ("tools", "saipen", "extensions", "bin"):
        shutil.copytree(repo / part, target / part, ignore=ignore)
    shutil.copy2(repo / "VERSION", target / "VERSION")
    engines[name] = target
validate = engines["before"] / "tools" / "validate.py"
text = validate.read_text(encoding="utf-8")
start = text.index("    # T-1668: a compacted row is a projection;")
end = text.index("    # An owner with no claim_time, or the reverse, is half a claim.")
validate.write_text(text[:start] + text[end:], encoding="utf-8", newline="")

env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")


def fails(engine: Path, root: Path) -> list[str]:
    proc = subprocess.run(
        [sys.executable, "-B", str(engine / "tools" / "validate.py"), "--gate", "core",
         "--project-root", str(root)],
        cwd=str(root), env=env, capture_output=True, timeout=900, check=False,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    return sorted(re.sub(r"\d+", "#", line) for line in out.splitlines() if line.startswith("FAIL"))


projects = sorted(p for p in copies.iterdir() if (p / ".saipen" / "STATE.md").is_file())
differing = 0
for project in projects:
    before, after = fails(engines["before"], project), fails(engines["after"], project)
    added = [line for line in after if line not in before]
    removed = [line for line in before if line not in after]
    if added or removed:
        differing += 1
        print(f"DIFF {project.name}: +{len(added)} -{len(removed)}")
        for line in added[:4]:
            print("   +", line[:220])
        for line in removed[:4]:
            print("   -", line[:220])
    else:
        print(f"same {project.name}: {len(after)} FAIL")
print(f"projects: {len(projects)}, differing: {differing}")
shutil.rmtree(work, ignore_errors=True)
