import os
import subprocess
import sys
import tempfile
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAIPEN_PY = ROOT / "tools" / "saipen.py"

now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
td = tempfile.mkdtemp()
proj = Path(td) / "proj"
(proj / ".saipen").mkdir(parents=True)
(proj / ".saipen" / "STATE.md").write_text(
    f"""---
phase: BUILD
task: T-010
next_action: "PHASE BUILD T-010"
blocker: none
transition_from: SCOUT
saipen_version: 7
agent: crashed-agent
mode: full
updated: {now}
---
""",
    encoding="utf-8",
)
(proj / ".saipen" / "BOARD.md").write_text(
    "# Board\n## DOING\n- [/] T-010 feature under construction | owner: crashed-agent | claim_time: 2020-01-01T00:00:00Z\n## TODO\n## DONE\n## BLOCKED\n",
    encoding="utf-8",
)
(proj / ".saipen" / "LOG.md").write_text(
    "# Log\n\n- 01.01.20 00:00 [E-001] [T-010] [agent: crashed-agent] RUN: build -> edits in flight\n",
    encoding="utf-8",
)

ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def run(*args):
    r = subprocess.run(
        [sys.executable, str(SAIPEN_PY), "--project-root", str(proj), "--json", "--dry-run", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=ENV,
    )
    return r.returncode, r.stdout, r.stderr


CYR = "\u0441\u0441\u0441\u0430\u0430\u0435\u0435\u0435\u0435\u0440\u0440"
tokens = [
    "gg", "hh", "cc", "ccc", "ss", "sss", "dd", "aa", "qq", "qqq", "ee", "eee", "pp", "tt", "sc",
    CYR[0:2], CYR[2:5], CYR[5:7], CYR[7:10], CYR[10:12],
]
for tok in tokens:
    rc, out, err = run(tok)
    head = " ".join(out.split())[:110]
    print(f"{tok!r} rc={rc} out={head}")
    if err.strip():
        print(f"   STDERR: {' '.join(err.split())[:160]}")
