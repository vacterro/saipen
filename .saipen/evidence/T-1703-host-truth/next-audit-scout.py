"""Bounded read-only metadata for the next inbox task, not its adjudication."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

OUT = Path(__file__).resolve().parent
registry = Path(r"C:\Users\vac34\.config\freebuff-desktop\projects\_FastPrompter-233f8ace-de83-4057-a703-41ef1ae21f72\project.json")
binding = json.loads(registry.read_bytes())
target = Path(binding["projectPath"])
files = (".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md", "src/fastprompter/main.py")


def snapshot():
    output = {}
    for name in files:
        path = target / name
        info = path.lstat()
        assert stat.S_ISREG(info.st_mode) and not path.is_symlink()
        assert not getattr(info, "st_file_attributes", 0) & 0x400
        output[name] = path.read_bytes()
    return output


before = snapshot()
git = []
for args in (("rev-parse", "--show-toplevel"), ("rev-parse", "HEAD")):
    result = subprocess.run(["git", *args], cwd=target,
                            env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"), capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    git.append(result.stdout.decode("utf-8").strip())
assert Path(git[0]).resolve() == target.resolve()
after = snapshot()
assert before == after, "scouted metadata changed during observation"
state_lines = [line for line in before[".saipen/STATE.md"].decode("utf-8").splitlines()
               if line.startswith(("phase:", "task:", "last_event:", "blocker:"))]
record = {"observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "registry_path": str(registry), "registry_sha256": hashlib.sha256(registry.read_bytes()).hexdigest(),
          "target": str(target.resolve()), "head": git[1], "reported_state_lines": state_lines,
          "files": {name: {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
                    for name, raw in before.items()}, "target_writes": 0,
          "scope": "Read-only next-audit scout; no source adjudication, canonical target command or lifecycle verdict."}
(OUT / "next-audit-scout.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"target": record["target"], "head": git[1], "reported_state_lines": state_lines,
                  "main_sha256": record["files"]["src/fastprompter/main.py"]["sha256"],
                  "target_writes": 0, "lifecycle_verdict": "NOT_ADJUDICATED"}))
