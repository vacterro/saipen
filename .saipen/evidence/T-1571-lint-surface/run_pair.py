"""Same-oracle red/green pair for T-1571 (VERIFY-ORACLE-01).

Oracle: tools/test_t1571_lint_surface.py, held fixed. Subject: ruff.toml --
the pre-fix file (the two-script `include` allowlist, no exclusions) against
the live one. The pre-fix subject is rebuilt from the live file by exact
reverse replacement, each asserted once, so it cannot drift into the fix.

Run from the project root: python .saipen/evidence/T-1571-lint-surface/run_pair.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.oracle import oracle_digest, verifier_identity  # noqa: E402

SUBJECTS = ["ruff.toml"]
COMMAND = "python -B -m unittest -v test_t1571_lint_surface"
ORACLE = ["tools/test_t1571_lint_surface.py"]

LIVE_DISCOVERY = (
    "# The canonical surface is `python -m ruff check tools/ tests/` (KNOWLEDGE\n"
    "# harness, CI): every Python file under both, by default discovery. An\n"
    "# allowlist of two scripts once stood here and made that command lint those\n"
    '# two alone while every report still said "tools/ tests/ clean" (T-1571).\n'
    "# What discovery must NOT reach is named instead: the journal's generated\n"
    "# evidence and the byte-frozen fixtures under tests/fixtures (T-1563).\n"
    'extend-exclude = [".saipen", "tests/fixtures"]\n'
)
PRE_FIX_DISCOVERY = (
    "# Keep recursive `ruff check` on the two owned scripts; default discovery also\n"
    "# captures generated evidence and fixture snippets.\n"
    'include = ["tools/validate.py", "tools/run_scenarios.py"]\n'
)
LIVE_SIM905 = (
    "    # A word set written as one `\"...\".split()` string (chat_style's language\n"
    "    # vocabularies) reads as prose; a 60-item list literal does not, and the\n"
    "    # two build the identical set.\n"
    '    "SIM905",\n'
    "\n"
)

live = (ROOT / "ruff.toml").read_bytes().decode("utf-8")
newline = "\r\n" if "\r\n" in live else "\n"
text = live.replace("\r\n", "\n")
for old, new in ((LIVE_DISCOVERY, PRE_FIX_DISCOVERY), (LIVE_SIM905, "")):
    assert text.count(old) == 1, old[:60]
    text = text.replace(old, new)
(EVIDENCE / "pre-fix").mkdir(exist_ok=True)
(EVIDENCE / "pre-fix" / "ruff.toml").write_bytes(text.replace("\n", newline).encode("utf-8"))

with tempfile.TemporaryDirectory(prefix="saipen-t1571-oracle-") as directory:
    snapshot = Path(directory).resolve()
    for name in ("tools", "tests"):
        shutil.copytree(ROOT / name, snapshot / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for file in ROOT.iterdir():
        if file.is_file():
            shutil.copy2(file, snapshot / file.name)
    environment = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
    environment["PYTHONPATH"] = str(snapshot / "tools")
    environment["PYTHONUTF8"] = "1"
    verifier = verifier_identity(COMMAND, ORACLE, snapshot)
    manifest = {"verifier": verifier, "command": COMMAND, "oracle": ORACLE, "runs": []}
    for label in ("red", "green"):
        source = EVIDENCE / "pre-fix" / "ruff.toml" if label == "red" else ROOT / "ruff.toml"
        shutil.copy2(source, snapshot / "ruff.toml")
        assert verifier_identity(COMMAND, ORACLE, snapshot) == verifier, "oracle drifted"
        subject = oracle_digest(snapshot, SUBJECTS)
        out = EVIDENCE / f"verify-{label}.txt"
        with out.open("w", encoding="utf-8") as output:
            result = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", "-v", "test_t1571_lint_surface"],
                cwd=snapshot / "tools", env=environment, stdout=output,
                stderr=subprocess.STDOUT, timeout=900)
        report = out.read_text(encoding="utf-8")
        tail = report.strip().splitlines()[-1]
        errors = sum(1 for line in report.splitlines() if line.startswith("ERROR:"))
        failures = sum(1 for line in report.splitlines() if line.startswith("FAIL:"))
        manifest["runs"].append({"label": label, "subject": subject,
                                 "returncode": result.returncode, "verdict": tail,
                                 "errors": errors, "failures": failures})
        print(label, result.returncode, subject, tail,
              "errors:", errors, "failures:", failures, flush=True)
    (EVIDENCE / "verify-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    assert manifest["runs"][0]["returncode"] != 0
    assert manifest["runs"][0]["errors"] == 0
    assert manifest["runs"][1]["returncode"] == 0
    print("verifier", verifier)
