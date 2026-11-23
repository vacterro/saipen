"""RED control for T-1743 F6: same oracle, the generation-follow rule
removed from state.persisted_home_access, in a disposable source copy."""
import pathlib
import shutil
import subprocess
import sys

SRC = pathlib.Path(r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN")
RED = pathlib.Path(r"V:\_TEMP_\saipen-t1743-red-f6")

if RED.exists():
    shutil.rmtree(RED, ignore_errors=True)
RED.mkdir(parents=True)
for name in ("tools", "saipen", "extensions", "bootstrap", "tests"):
    shutil.copytree(SRC / name, RED / name, ignore=shutil.ignore_patterns("__pycache__"))
shutil.copy2(SRC / "VERSION", RED / "VERSION")

target = RED / "tools" / "saipen_engine" / "state.py"
raw = target.read_bytes().decode("utf-8")
fixed = (
    "    path = machine_runtime.current_generation_for(text) or path\r\n"
)
assert raw.count(fixed) == 1, "fixed line not found"
target.write_bytes(raw.replace(fixed, "").encode("utf-8"))

proc = subprocess.run(
    [sys.executable, "-m", "pytest", "tools/test_t1743_cross_user_dead_ends.py", "-q",
     "-p", "no:cacheprovider", "-k", "Pruned"],
    cwd=RED, capture_output=True, text=True,
)
print(proc.stdout[-1800:])
shutil.rmtree(RED, ignore_errors=True)
