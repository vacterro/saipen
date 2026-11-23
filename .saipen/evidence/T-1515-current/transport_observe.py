"""Observe the genuine native transport before strengthening its regression."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import test_t1515_posix_shell_entry as suite

case = suite.PosixShellHostTransport()
case.setUp()
bash = Path(r"C:\Program Files\Git\bin\bash.exe")
env = suite.t1501._cold_env(MSYSTEM="MINGW64")
resolved = suite.er.resolve_entry(case.root, env=env, honor_environment=False)
with tempfile.TemporaryDirectory(prefix="saipen-t1515-native-observe-") as scratch:
    script = f'{resolved["command_form"]} search \'x"y > injected.txt\' --json'
    run = subprocess.run([str(bash), "--noprofile", "--norc", "-c", script],
                         cwd=scratch, env={**env, "PATH": os.environ["PATH"],
                                          "SAIPEN_PROJECT_ROOT": str(case.root)},
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=120)
    record = {"shell": str(bash), "command_form": resolved["command_form"],
              "returncode": run.returncode, "stdout": run.stdout,
              "stderr": run.stderr, "files": sorted(os.listdir(scratch))}
(Path(__file__).parent / "transport-observed.json").write_text(
    json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
