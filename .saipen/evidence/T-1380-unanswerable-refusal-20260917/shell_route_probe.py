"""Measure what PowerShell 5, pwsh 7 and cmd hand a program for the printed --file route.

Git Bash is measured by shell_route_probe_bash.py, which types the line into a
script file so no Windows command-line quoting sits between the probe and bash.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

work = Path(tempfile.mkdtemp(prefix="t1380-shell-probe-"))
echo = work / "argv_echo.py"
echo.write_text("import sys, json\nprint(json.dumps(sys.argv[1:]))\n", encoding="utf-8")

plain = r"V:\_TEMP_\t1363-abc\.saipen-launched-task.txt"
spaced = r"V:\_TEMP_\operator notes\launched task.txt"
forms = {
    "unquoted plain": f"--file {plain}",
    "double-quoted plain": f'--file "{plain}"',
    "unquoted spaced": f"--file {spaced}",
    "double-quoted spaced": f'--file "{spaced}"',
}


def powershell(executable):
    def build(args):
        return [executable, "-NoProfile", "-Command", f"& '{sys.executable}' '{echo}' {args}"]

    return build


shells = []
for name in ("powershell", "pwsh"):
    if shutil.which(name):
        shells.append((name, powershell(name)))
if shutil.which("cmd"):
    shells.append(("cmd", lambda args: f'cmd /d /c ""{sys.executable}" "{echo}" {args}"'))

for label, form in forms.items():
    expected = plain if "plain" in label else spaced
    for shell, build in shells:
        proc = subprocess.run(build(form), capture_output=True, text=True, timeout=60)
        try:
            argv = json.loads(proc.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            argv = [f"<no output: rc={proc.returncode} {proc.stderr.strip()[:80]}>"]
        intact = argv[:2] == ["--file", expected]
        print(f"{label:<22} {shell:<10} intact={intact!s:<5} argv={argv}")

shutil.rmtree(work, ignore_errors=True)
