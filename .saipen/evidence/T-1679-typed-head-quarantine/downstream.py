"""T-1679 REVIEW: downstream verdicts before/after on COPIES of every managed project.

Usage: t1679_downstream.py <repo> <work>

The "before" engine is a copy of <repo> with the three T-1679 semantics taken
out (the journal bound in the cut, the floor handed to it by the loader, and
an adoption counting as a closure again). Every project's `.saipen/` (without
cache/) is copied under <work>; both engines answer `status --json` on the
copy; the live projects are never opened for writing. Differences in ok/code
are listed, everything else is masked.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
work = Path(sys.argv[2]).resolve()
assert not work.exists(), work
CODE = Path("V:/___VAC/__K/__CODE")
SKIP = ("__SAITULS", "_TEMP", "_AI_STUFF_AGENTIC/_SAIPEN/")

projects = sorted(
    p.parent.parent
    for pattern in ("*/.saipen/STATE.md", "*/*/.saipen/STATE.md")
    for p in CODE.glob(pattern)
    if not any(s in p.as_posix() + "/" for s in SKIP)
)


def ignore(_d, names):
    return [n for n in names if n in {"cache", "__pycache__"} or n.endswith(".pyc")]


before = work / "engine-before"
for part in ("tools", "saipen", "extensions", "bin"):
    shutil.copytree(repo / part, before / part, ignore=ignore)
shutil.copy2(repo / "VERSION", before / "VERSION")
EDITS = [
    ("tools/saipen_engine/log.py",
     "    journal = journal_floor is not None and "
     "(last_event is None or journal_floor < last_event)\n",
     "    journal = False\n"),
    ("tools/saipen_engine/operations.py",
     "                journal_floor=_journal_floor(root, snapshot.events)[0],\n",
     "                journal_floor=None,\n"),
    ("tools/saipen_engine/lifecycle_authority.py",
     "            op_id.startswith(\"reconcile-\") and _ATTESTATION in text\n",
     "            op_id.startswith(\"reconcile-\")\n"),
]
for rel, old, new in EDITS:
    target = before / rel
    raw = target.read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8")
    old, new = old.replace("\n", nl), new.replace("\n", nl)
    assert text.count(old) == 1, (rel, old[:60])
    target.write_bytes(text.replace(old, new).encode("utf-8"))

env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")


def status(engine: Path, root: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, "-B", str(engine / "tools" / "saipen.py"), "status", "--json",
         "--project-root", str(root)],
        cwd=str(root), env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=300,
    )
    try:
        answer = json.loads(proc.stdout)
    except ValueError:
        return {"ok": None, "code": "NOT_JSON", "reason": (proc.stdout + proc.stderr)[-200:]}
    return answer


differ = 0
for project in projects:
    name = project.relative_to(CODE).as_posix().replace("/", "__")
    copy = work / name
    shutil.copytree(project / ".saipen", copy / ".saipen", ignore=ignore)
    old = status(before, copy)
    new = status(repo, copy)
    a = (old.get("ok"), old.get("code"))
    b = (new.get("ok"), new.get("code"))
    mark = "same" if a == b else "DIFF"
    differ += a != b
    print(f"{mark:4} {name}: before {a} after {b}")
    if a != b:
        print("     before:", str(old.get("reason") or old.get("detail"))[:200])
        print("     after :", str(new.get("reason") or new.get("detail"))[:200])
print(f"projects: {len(projects)}, differing verdicts: {differ}")
