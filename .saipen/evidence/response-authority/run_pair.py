"""Freeze one oracle, run it against actual HEAD and live subject in scratch.

No live production or protected protocol files are overwritten. Subjects use
the same current verifier/fixtures; only production bytes differ. This script
is durable evidence tooling, not part of the deployed runtime.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.oracle import verifier_identity, oracle_digest
from saipen_engine.test_runner import _ignore_copy

ORACLES = ("tools/test_ingress_authority.py", "tools/test_response_digest.py", "tools/test_response_delivery.py")
FIXTURES = ("tests/fixtures/response-authority/incidents.json", "tools/test_ticket_retirement.py", "tools/test_t1461_source_append.py", "tools/test_opencode_adapter.py", "tools/test_guard_hostile_matrix.py", "tools/test_operator_task_witness.py", "tools/test_t1363_zero_manual_entry.py", "tools/test_dependency_resume_liveness.py", "tools/test_fixture_support.py", "tools/test_hermetic_env.py", "tools/test_orchestration_repair.py")
PRODUCTION = ("tools/saipen.py", "tools/saipen_engine/operator_task.py", "tools/saipen_engine/board.py", "tools/saipen_engine/board_compaction.py", "tools/saipen_engine/entry.py", "tools/saipen_engine/operations.py", "tools/saipen_engine/retirement.py", "tools/saipen_engine/response_surface.py", "tools/saipen_engine/chat_style.py", "tools/saipen_engine/hush.py", "tools/saipen_engine/source_append.py", "extensions/adapters/opencode/saipen-guard.js", "extensions/adapters/codex/saipen-guard.py", "extensions/adapters/claude/saipen-guard.py")


def run(subject: str, destination: Path) -> dict:
    verifier_paths = (*ORACLES, *FIXTURES)
    command = "python -X utf8 -m unittest test_ingress_authority test_response_digest test_response_delivery"
    with tempfile.TemporaryDirectory(prefix="saipen-authority-oracle-") as raw:
        scratch = Path(raw) / "subject"
        shutil.copytree(ROOT, scratch, ignore=_ignore_copy)
        if subject == "HEAD":
            archive = Path(raw) / "subject.zip"
            subprocess.run(["git", "archive", "--format=zip", f"--output={archive}", "f462ddc018977f06598f332356f9229f23b2e830", *PRODUCTION], cwd=ROOT, check=True)
            with zipfile.ZipFile(archive) as zipped:
                zipped.extractall(scratch)
        env = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
        env["SAIPEN_FORBID_HOST_SPAWN"] = "1"
        env["PYTHONUTF8"] = "1"
        done = subprocess.run([sys.executable, "-X", "utf8", "-m", "unittest", "test_ingress_authority", "test_response_digest", "test_response_delivery"], cwd=scratch / "tools", env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=600)
        result = {"subject": subject, "pre_fix_commit": "f462ddc018977f06598f332356f9229f23b2e830" if subject == "HEAD" else None, "command": command, "returncode": done.returncode, "verifier": verifier_identity(command, verifier_paths, ROOT), "subject_digest": oracle_digest(scratch, PRODUCTION), "oracle_paths": list(verifier_paths), "production_paths": list(PRODUCTION)}
        destination.mkdir(parents=True, exist_ok=True)
        (destination / f"{subject.lower()}.txt").write_text(done.stdout + done.stderr, encoding="utf-8")
        (destination / f"{subject.lower()}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("subject", choices=("HEAD", "live"))
    args = parser.parse_args()
    run(args.subject, Path(__file__).parent / "paired")
