"""Public source-CLI smoke in a disposable scenario; no native-host claim."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from test_fixture_support import restamp_live_style

prefix = sys.argv[1] if len(sys.argv) > 1 else "verify"
records = []
with tempfile.TemporaryDirectory(prefix="saipen-t1694-") as temporary:
    root = Path(temporary) / "project"
    root.mkdir()
    shutil.copytree(ROOT / "tests/scenarios/userperson-valid/.saipen", root / ".saipen")
    restamp_live_style(root / ".saipen")
    (root / ".saipen/USERPERSON.md").unlink(missing_ok=True)
    env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
    env["SAIPEN_USER_CONFIG_HOME"] = str(Path(temporary) / "user-config")
    base = [str(ROOT / "bin/saipen.cmd"), "--project-root", str(root)]

    def call(label, args):
        command = base + args + ["--json"]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=120)
        (OUT / (prefix + "-" + label + ".out.txt")).write_text(
            result.stdout + result.stderr, encoding="utf-8")
        assert result.returncode == 0, result.stdout + result.stderr
        value = json.loads(result.stdout)
        records.append({"label": label, "command": command, "result": value})
        return value

    (root / "audit").mkdir()
    (root / "audit/1.md").write_text(
        "# Disposable audit\npriority: P1\nverify: external fixture signal arrives\n\n"
        "Await the external fixture result.\n", encoding="utf-8")
    ingested = call("ingest", ["audit", "ingest"])
    work = ingested["work"]
    if isinstance(work, dict):
        work = work.get("id") or work.get("ticket")
    assert isinstance(work, str) and work.startswith("T-"), ingested
    call("block", ["ticket", "block", work, "BLOCKED_EXTERNAL -- fixture signal is absent"])
    checkpoint = {name: (root / ".saipen" / name).read_bytes()
                  for name in ["STATE.md", "BOARD.md", "LOG.md"]}
    status = call("status", ["status"])
    auto = status["automation"]
    assert status["computed_reason"] == "audit-inbox-unworkable", status
    assert auto["disposition"] == "BLOCKED" and auto["next_command"] is None, auto
    assert auto["operator_action_due"] is False and auto["closure_complete"] is False, auto
    digest = call("digest", ["response", "digest", "--reason", "final"])
    assert digest["emit"] is True and "AUDIT_INBOX_UNWORKABLE" in digest["text"], digest
    assert "RESULT: Töö säilitatud" in digest["text"], digest
    assert "NEXT EXACT ACTION: NONE" in digest["text"], digest
    assert "OPERATOR ACTION:" not in digest["text"], digest
    assert all((root / ".saipen" / name).read_bytes() == raw
               for name, raw in checkpoint.items())
    call("add-runnable", ["ticket", "add", "P1", "Independent runnable fixture",
                          "--verify", "bounded fixture evidence"])
    status = call("runnable-status", ["status"])
    assert status["automation"]["disposition"] == "CONTINUE", status
    assert status["automation"]["next_command"] == "cc", status
    digest = call("runnable-digest", ["response", "digest", "--reason", "final"])
    assert digest["emit"] is False and digest["text"] == "", digest

(OUT / (prefix + "-public-smoke.json")).write_text(
    json.dumps({"records": records, "readonly_checkpoint_unchanged": True,
                "subjects": {name: hashlib.sha256((ROOT / "tools/saipen_engine" / name).read_bytes()).hexdigest()
                             for name in ["automation.py", "response_surface.py"]},
                "limits": "Disposable canonical scenario and public source CLI; native host not exercised."},
               indent=2) + "\n", encoding="utf-8")
print("Public source CLI: blocked audit emits a truthful handback; independent runnable Work continues; reads write zero checkpoint bytes.")
