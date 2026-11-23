"""Read-only handoff boundaries; source memory changes are recorded separately."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
FOREIGN = Path(r"V:\___VAC\__K\__CODE\_PY\_LIMISAW")
CYCLE = FOREIGN / ".saipen/improve/imp-vacterro-limisaw-20260918-4"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    paths = ["tools/saipen.py", "tools/improve.py", "tools/validate.py",
             "tools/saipen_engine/subs.py", "tools/saipen_engine/conformance.py"]
    index_path = subprocess.check_output(
        ["git", "rev-parse", "--git-path", "index"], cwd=ROOT,
        text=True, encoding="utf-8").strip()
    index = Path(index_path)
    if not index.is_absolute():
        index = ROOT / index
    return {
        "source_hashes": {path: digest(ROOT / path) for path in paths},
        "inherited_index_sha256": digest(index),
        "foreign_head": subprocess.check_output(
            ["git", "-C", str(FOREIGN), "rev-parse", "HEAD"],
            text=True, encoding="utf-8").strip(),
        "foreign_core": {name: digest(FOREIGN / ".saipen" / name)
                         for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")},
        "foreign_cycle": {path.relative_to(CYCLE).as_posix(): digest(path)
                          for path in sorted(CYCLE.rglob("*")) if path.is_file()},
    }


mode = sys.argv[1]
current = snapshot()
if mode == "before":
    target = OUT / "review-boundaries-before.json"
    assert not target.exists(), "preserve the original boundary snapshot"
elif mode == "after":
    prior = json.loads((OUT / "review-boundaries-before.json").read_text(encoding="utf-8"))
    differences = {name: {"before": prior.get(name), "after": current.get(name)}
                   for name in current if prior.get(name) != current.get(name)}
    (OUT / "review-boundary-differences.json").write_text(
        json.dumps(differences, indent=2) + "\n", encoding="utf-8")
    target = OUT / "review-boundaries-after.json"
else:
    raise SystemExit("use before or after")
target.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
if mode == "after":
    assert prior == current, "boundary moved: " + ", ".join(differences)
print(json.dumps({"boundary": mode, "foreign_cycle_files": len(current["foreign_cycle"]),
                  "all_observed_hashes_unchanged": mode == "after"}))
