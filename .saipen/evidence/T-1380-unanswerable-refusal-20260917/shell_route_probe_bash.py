"""Git Bash half of the route probe: the typed line goes into a script file, so no
Windows command-line quoting sits between the probe and bash."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

BASH = r"C:\Program Files\Git\usr\bin\bash.exe"
work = Path(tempfile.mkdtemp(prefix="t1380-bash-probe-"))
echo = work / "argv_echo.py"
echo.write_text("import sys, json\nprint(json.dumps(sys.argv[1:]))\n", encoding="utf-8")
py = sys.executable.replace("\\", "/")
echo_posix = str(echo).replace("\\", "/")

plain = r"V:\_TEMP_\t1363-abc\.saipen-launched-task.txt"
spaced = r"V:\_TEMP_\operator notes\launched task.txt"
forms = {
    "unquoted plain": f"--file {plain}",
    "double-quoted plain": f'--file "{plain}"',
    "unquoted spaced": f"--file {spaced}",
    "double-quoted spaced": f'--file "{spaced}"',
}
for label, form in forms.items():
    expected = plain if "plain" in label else spaced
    script = work / "typed.sh"
    script.write_text(f'"{py}" "{echo_posix}" {form}\n', encoding="utf-8", newline="\n")
    proc = subprocess.run([BASH, str(script)], capture_output=True, text=True, timeout=60)
    try:
        argv = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        argv = [f"<no output: rc={proc.returncode} {proc.stderr.strip()[:160]}>"]
    print(f"{label:<22} git-bash   intact={argv[:2] == ['--file', expected]!s:<5} argv={argv}")
