"""Read named target states; write evidence only into the SAIPEN project."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
OUT = HERE / "observations-final" if "--final" in sys.argv else HERE
OUT.mkdir(exist_ok=True)
TARGETS = {
    "smartvac": Path("V:/___VAC/__K/__CODE/_PY/_SMART_VAC_CLEANER"),
    "saituls": Path("V:/___VAC/__K/__CODE/__SAITULS"),
    "audapack_recovery": Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK_RECOVERY_20261010"),
    "audapack_original": Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK"),
}
INPUTS = (".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md",
          ".saipen/IDENTITY.md", ".git/index")


def hashes(root):
    result = {}
    for name in INPUTS:
        path = root / name
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return result


def observe(item):
    name, root = item
    started = datetime.now(timezone.utc).isoformat()
    if not root.is_dir():
        return {"name": name, "root": str(root), "error": "TARGET_ABSENT", "at": started}
    before = hashes(root)
    for rel in INPUTS[:4]:
        source = root / rel
        if source.is_file():
            (OUT / (name + "-" + source.name)).write_bytes(source.read_bytes())
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    command = [str(HOME / "bin/saipen.cmd"), "--project-root", str(root), "status", "--json"]
    try:
        run = subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=180)
        (OUT / (name + "-status.json")).write_bytes(run.stdout)
        (OUT / (name + "-status.stderr.txt")).write_bytes(run.stderr)
        try:
            status = json.loads(run.stdout.decode("utf-8-sig"))
        except (ValueError, UnicodeError):
            status = {"error": "UNPARSEABLE_STATUS"}
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            env=env, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        after = hashes(root)
        result = {
            "name": name, "root": str(root), "started_utc": started,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "command": command, "exit_code": run.returncode,
            "head": head.stdout.strip() if head.returncode == 0 else None,
            "phase": status.get("phase"), "task": status.get("task"),
            "next_action": status.get("computed_next_action", status.get("next_action")),
            "code": status.get("code"), "detail": status.get("detail"),
            "automation": status.get("automation"),
            "conformance": status.get("conformance"),
            "before_hashes": before, "after_hashes": after,
            "observed_inputs_unchanged": before == after,
            "limit": "This collector writes only its own SAIPEN evidence; concurrent target edits are not excluded.",
        }
    except subprocess.TimeoutExpired as exc:
        result = {"name": name, "root": str(root), "error": "OBSERVATION_TIMEOUT",
                  "command": command, "timeout_s": exc.timeout, "before_hashes": before,
                  "after_hashes": hashes(root), "started_utc": started}
    (OUT / (name + "-observation.json")).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8",
    )
    return result


with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(observe, TARGETS.items()))
(OUT / "target-observations.json").write_text(
    json.dumps(results, indent=2) + "\n", encoding="utf-8",
)
print(json.dumps([{
    key: row.get(key) for key in ("name", "exit_code", "phase", "task", "code", "error",
                                 "observed_inputs_unchanged")
} for row in results], indent=2))
