"""Prove a proposed fixture-only correction on copies while the main tree is frozen."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SUBJECT = "test_t1736_tool_safety_and_evidence.py"
text = (ROOT / "tools" / SUBJECT).read_text(encoding="utf-8-sig")
old = '        bash_bin = shutil.which("bash")\n        if bash_bin:\n            cmd_piped'
new = '''        bash_bin = shutil.which("bash")
        if bash_bin:
            try:
                startup = subprocess.run(
                    [bash_bin, "-c", "exit 0"], capture_output=True, timeout=5
                )
            except (OSError, subprocess.TimeoutExpired):
                bash_bin = None
            else:
                if startup.returncode != 0:
                    bash_bin = None
        if bash_bin:
            cmd_piped'''
assert text.count(old) == 1
copies = {"before": text, "after": text.replace(old, new)}
results = []
git_bin = Path("C:/Program Files/Git/bin")
git_usr = Path("C:/Program Files/Git/usr/bin")
assert (git_bin / "bash.exe").is_file(), "native positive control is unavailable"
for version, source in copies.items():
    directory = HERE / version
    directory.mkdir(exist_ok=True)
    (directory / SUBJECT).write_text(source, encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="shell-control-", dir=HERE) as temporary:
        temporary_path = Path(temporary).resolve()
        assert temporary_path.is_relative_to(HERE.resolve())
        bad = temporary_path / "bad"
        empty = temporary_path / "empty"
        bad.mkdir()
        empty.mkdir()
        (bad / "bash.cmd").write_text("@echo off\nexit /b 75\n", encoding="ascii")
        profiles = {"missing": str(empty), "unusable": str(bad),
                    "native": os.pathsep.join((str(git_bin), str(git_usr)))}
        for case, search_path in profiles.items():
            env = os.environ.copy()
            env["PATH"] = search_path
            env["PYTHONPATH"] = str(ROOT / "tools")
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            command = [sys.executable, "-B", "-m", "unittest",
                       "test_t1736_tool_safety_and_evidence.ToolSafetyAndEvidenceTests."
                       "test_pipelined_validator_exit_status_preservation"]
            completed = subprocess.run(command, cwd=directory, env=env,
                                       capture_output=True, timeout=30, check=False)
            results.append({"subject": version, "profile": case, "exit_code": completed.returncode,
                            "stdout": completed.stdout.decode("utf-8", errors="replace"),
                            "stderr": completed.stderr.decode("utf-8", errors="replace")})
expected = {("before", "missing"): 0, ("before", "unusable"): 1,
            ("before", "native"): 0, ("after", "missing"): 0,
            ("after", "unusable"): 0, ("after", "native"): 0}
assert all(r["exit_code"] == expected[(r["subject"], r["profile"])] for r in results), results
(HERE / "draft-results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"scope": "disposable draft only; T-1742 is not claimed",
                  "results": [{k: r[k] for k in ("subject", "profile", "exit_code")} for r in results]}))
