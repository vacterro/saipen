"""Disposable public-CLI scenarios; read-only projections preserve all bytes."""
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


def snapshot(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


with tempfile.TemporaryDirectory(prefix="saipen-t1695-") as temporary:
    for kind in ["audit", "queue"]:
        for active in [False, True]:
            label = kind + ("-active" if active else "-idle")
            root = Path(temporary) / label
            root.mkdir()
            shutil.copytree(ROOT / "tests/scenarios/userperson-valid/.saipen", root / ".saipen")
            restamp_live_style(root / ".saipen")
            (root / ".saipen/USERPERSON.md").unlink(missing_ok=True)
            env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
            env["SAIPEN_USER_CONFIG_HOME"] = str(Path(temporary) / (label + "-config"))
            base = [str(ROOT / "bin/saipen.cmd"), "--project-root", str(root)]

            def call(step, args, input_text=None):
                command = base + args + ["--json"]
                result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                        text=True, encoding="utf-8", errors="replace", timeout=180,
                                        input=input_text)
                (OUT / (prefix + "-" + label + "-" + step + ".out.txt")).write_text(
                    result.stdout + result.stderr, encoding="utf-8")
                assert result.returncode == 0, result.stdout + result.stderr
                value = json.loads(result.stdout)
                records.append({"scenario": label, "step": step, "command": command, "result": value})
                return value

            if active:
                started = call("start", ["start", "Independent active fixture; preserve exact local evidence"])
                assert started["ok"] is True, started
            if kind == "audit":
                target = root / "audit/1.md"
                target.parent.mkdir(exist_ok=True)
            else:
                request = root / "request.md"
                request.write_text(
                    "# User request\n\npriority: P1\nverify: bounded fixture evidence\n\n"
                    "## Request\n\nIndependent queued fixture request\n", encoding="utf-8")
                captured = call("capture", ["source", "capture", "--file", str(request),
                                             "--kind", "user_instruction"])
                receipt = captured["receipt"]
                target = root / ".saipen/intake/active" / (receipt + ".md")
            # Deliberate invalid bytes only in the disposable subject fixture.
            target.write_bytes(b"\xffinvalid UTF-8")
            before = snapshot(root)
            status = call("status", ["status"])
            auto = status["automation"]
            digest = call("digest", ["response", "digest", "--reason", "final"])
            if active:
                assert status["computed_reason"] == "finish", status
                assert auto["disposition"] == "CONTINUE" and auto["next_command"] == "cc", auto
                assert digest["emit"] is False and digest["text"] == "", digest
            else:
                reason = "audit-inbox-invalid" if kind == "audit" else "queued-source-invalid"
                code = "AUDIT_INBOX_INVALID" if kind == "audit" else "QUEUED_SOURCE_INVALID"
                assert status["computed_reason"] == reason, status
                assert auto["disposition"] == "INVALID" and auto["next_command"] is None, auto
                assert auto["operator_action_due"] is False and auto["closure_complete"] is False, auto
                assert digest["emit"] is True and code in digest["text"], digest
                assert "RESULT: Töö säilitatud" in digest["text"], digest
                assert "NEXT EXACT ACTION: NONE" in digest["text"], digest
                assert "OPERATOR ACTION:" not in digest["text"], digest
                checked = call("check", ["response", "check", "--stdin", "--classify",
                                         "--auto-eligibility"], input_text=digest["text"])
                assert checked["ok"] is True, checked
            assert snapshot(root) == before, "read-only projection changed scenario bytes"

(OUT / (prefix + "-public-smoke.json")).write_text(
    json.dumps({"records": records, "readonly_bytes_unchanged": True,
                "subjects": {name: hashlib.sha256((ROOT / "tools/saipen_engine" / name).read_bytes()).hexdigest()
                             for name in ["automation.py", "response_surface.py"]},
                "limits": "Disposable public source CLI; no native host enforcement or admission claim."},
               indent=2) + "\n", encoding="utf-8")
print("Four public CLI scenarios PASS: invalid audit/queue diagnostics; active Work continues; all read-only bytes preserved.")
