"""Read-only live snapshot; canonical probes run only in its disposable copy."""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

repo = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(repo / "tools"))
from saipen_engine.paths import unbound_environment

foreign = pathlib.Path("V:/___VAC/__K/__CODE/__SAITULS")
names = ("STATE.md", "BOARD.md", "LOG.md")
before = {name: (foreign / ".saipen" / name).read_bytes() for name in names}
result = {"scope": "full authority/recovery copy excluding kitchen,tmp,cache,locks scratch",
          "live_hashes": {name: hashlib.sha256(data).hexdigest() for name, data in before.items()},
          "live_state": before["STATE.md"].decode("utf-8-sig"), "probes": []}
with tempfile.TemporaryDirectory(prefix="saipen-t1609-live-copy-") as temp:
    root = pathlib.Path(temp) / "subject"
    memory = foreign / ".saipen"
    def ignore(directory, children):
        return set(children) & {"kitchen", "tmp", "cache", "locks"} if pathlib.Path(directory) == memory else set()
    shutil.copytree(memory, root / ".saipen", ignore=ignore)
    subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
    for args in (("recover", "--dry-run"), ("continue",)):
        run = subprocess.run([sys.executable, "-B", str(repo / "tools/saipen.py"),
                              *args, "--json"], cwd=root, env=unbound_environment(),
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=180)
        result["probes"].append({"args": args, "rc": run.returncode,
                                 "answer": json.loads(run.stdout or "{}"), "stderr": run.stderr})
after = {name: (foreign / ".saipen" / name).read_bytes() for name in names}
result["live_core_bytes_unchanged"] = before == after
path = pathlib.Path(__file__).with_name("T-1609-live-copy.json")
path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"live_core_bytes_unchanged": before == after,
                  "codes": [x["answer"].get("code") for x in result["probes"]]}))
assert before == after, "live project changed during the read-only snapshot"
