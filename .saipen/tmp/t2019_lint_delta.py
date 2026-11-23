import json
import subprocess
import sys
from collections import Counter

paths = [
    "tools/saipen.py", "tools/saipen_engine/suite_record.py",
    "tools/saipen_engine/test_runner.py", "tools/saipen_engine/suite_preflight.py",
    "tools/test_t2019_suite_preflight.py",
]


def diagnostics(path, source):
    run = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--output-format", "json",
         "--stdin-filename", path, "-"],
        input=source, capture_output=True, check=False,
    )
    items = json.loads(run.stdout)
    lines = source.decode("utf-8").splitlines()
    return Counter(
        (item["code"], item["message"], lines[item["location"]["row"] - 1].strip())
        for item in items
    )


new = 0
inherited = 0
for path in paths:
    old = subprocess.run(["git", "show", ":" + path], capture_output=True, check=False)
    from pathlib import Path
    before = diagnostics(path, old.stdout) if old.returncode == 0 else Counter()
    after = diagnostics(path, Path(path).read_bytes())
    added = after - before
    new += added.total()
    inherited += (after & before).total()
    print(f"{path}: new={added.total()} inherited={(after & before).total()}")
print(f"NEW_LINT_ERRORS={new} INHERITED_TOUCHED_ERRORS={inherited}")
raise SystemExit(bool(new))
