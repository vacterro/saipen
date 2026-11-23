"""Run the same oracle on current and preserved pre-fix subjects in one copy."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.test_runner import _ignore_copy

VERIFIER = "tools/test_t1635_claude_profiles.py"
COMMAND = [sys.executable, "-B", "-m", "unittest", "test_t1635_claude_profiles"]
FILES = sorted(path.relative_to(EVIDENCE / "pre").as_posix()
               for path in (EVIDENCE / "pre").rglob("*") if path.is_file())
FILES.append("tools/saipen_engine/claude_profiles.py")


def fingerprint(root):
    digest = hashlib.sha256()
    for name in FILES:
        path = root / name
        digest.update(name.encode() + b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"MISSING")
    return digest.hexdigest()[:16]


def run(root, label):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("SAIPEN_")}
    env["CLAUDE_CONFIG_DIR"] = ""
    result = subprocess.run(COMMAND, cwd=root / "tools", env=env,
                            capture_output=True, stdin=subprocess.DEVNULL, timeout=600)
    (EVIDENCE / (label + ".out.txt")).write_bytes(result.stdout + result.stderr)
    return result.returncode


verifier = hashlib.sha256((ROOT / VERIFIER).read_bytes()).hexdigest()[:16]
post = fingerprint(ROOT)
with tempfile.TemporaryDirectory(prefix="saipen-t1635-pair-") as temporary:
    subject = Path(temporary) / "project"
    shutil.copytree(ROOT, subject, symlinks=True, ignore=_ignore_copy)
    control = run(subject, "control")
    if control:
        raise SystemExit("unmutated copy is not a passing instrument; see control.out.txt")
    for name in FILES:
        saved = EVIDENCE / "pre" / name
        target = subject / name
        if saved.is_file():
            shutil.copyfile(saved, target)
        elif target.exists():
            target.unlink()
    pre = fingerprint(subject)
    red = run(subject, "red")
    held = hashlib.sha256((subject / VERIFIER).read_bytes()).hexdigest()[:16] == verifier
green = run(ROOT, "green")
record = {"verifier": verifier, "pre_subject": pre, "post_subject": post,
          "pre_rc": red, "post_rc": green, "control_rc": control,
          "held": held, "command": "python -B -m unittest test_t1635_claude_profiles"}
(EVIDENCE / "pair.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
raise SystemExit(0 if red and not green and held else 1)
