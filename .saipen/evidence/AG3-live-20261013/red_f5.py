"""RED control for T-1743 F5: same oracle, projects() restored to the
path-equality-only rule, in a disposable copy of the source tree."""
import pathlib
import shutil
import subprocess
import sys

SRC = pathlib.Path(r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN")
RED = pathlib.Path(r"V:\_TEMP_\saipen-t1743-red-f5")

if RED.exists():
    shutil.rmtree(RED, ignore_errors=True)
RED.mkdir(parents=True)
for name in ("tools", "saipen", "extensions", "bootstrap", "tests"):
    shutil.copytree(SRC / name, RED / name, ignore=shutil.ignore_patterns("__pycache__"))
for name in ("VERSION",):
    shutil.copy2(SRC / name, RED / name)

target = RED / "tools" / "saipen_engine" / "machine_runtime.py"
text = target.read_text(encoding="utf-8")
fixed = """    if _same_dir(recorded, wanted):
        return True
    homes = (registration or {}).get("projected_homes") or ()
    return isinstance(homes, list) and any(
        isinstance(item, str) and item.strip() and _same_dir(item, wanted) for item in homes
    )
"""
assert text.count(fixed) == 1, "fixed hunk not found"
text = text.replace(fixed, "    return _same_dir(recorded, wanted)\n")
target.write_text(text, encoding="utf-8")

proc = subprocess.run(
    [sys.executable, "-m", "pytest", "tools/test_t1743_cross_user_dead_ends.py", "-q",
     "-p", "no:cacheprovider", "-k", "Projected"],
    cwd=RED, capture_output=True, text=True,
)
print(proc.stdout[-2500:])
shutil.rmtree(RED, ignore_errors=True)
