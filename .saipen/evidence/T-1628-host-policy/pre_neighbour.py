"""Run one test module against a clone carrying the exact pre-T-1628 bytes."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
module = sys.argv[1]
sys.path.insert(0, str(root / "tools"))
from saipen_engine.test_runner import _ignore_copy  # noqa: E402

paths = json.loads((evidence / "paths.json").read_text())
with tempfile.TemporaryDirectory(prefix="saipen-t1628-preneighbour-") as temporary:
    subject = Path(temporary) / "project"

    def ignore(directory, names):
        extra = {".git"} | ({".saipen"} if Path(directory) == root else set())
        return _ignore_copy(directory, names) | {n for n in names if n in extra}

    shutil.copytree(root, subject, symlinks=True, ignore=ignore)
    for relative in (paths if sys.argv[2:] != ["post"] else []):
        saved = evidence / "pre" / relative
        target = subject / relative
        if saved.is_file():
            shutil.copyfile(saved, target)
        elif target.exists():
            target.unlink()
    env = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
    env.pop("CLAUDE_CONFIG_DIR", None)
    proc = subprocess.run([sys.executable, "-B", "-m", "unittest", module], cwd=subject / "tools",
                          env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          timeout=1200)
    print(proc.stderr[-3000:])
    sys.exit(proc.returncode)
