import sys, subprocess, os
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "tools"))
import test_t1671_lifecycle_authority as T
T.setUpModule()
root = T._project(); T._type_the_lifecycle(root)
for args in (["ticket", "done", "T-001", "--closure-mode", "own_patch"], ["ship"], ["push"], ["start", "new task"], ["next"], ["validate"], ["transition", "SHIP", "T-001", "x"], ["scope", "T-001", "src/a.py"], ["handoff", "T-001", "--to", "other"], ["goal", "do things"], ["user-request", "another thing"], ["ticket", "block", "T-001", "why"], ["source", "recover"], ["brief"], ["context", "orient"], ["recover", "normalize-log"], ["recover", "--dry-run"]):
    r = subprocess.run([sys.executable, "-B", str(Path(sys.argv[1]) / "tools/saipen.py"), "--project-root", str(root), "--agent", "buffy", "--json", *args], cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    tb = "Traceback" in out
    import re, json
    code = re.search(r'"code": "([A-Z_]+)"', out)
    print(args, "| rc", r.returncode, "| code", code.group(1) if code else None, "| TRACEBACK" if tb else "")
    if tb:
        frames = re.findall(r'File ".*?tools[\/](.*?)", line (\d+), in (\w+)', out)
        print("     ", frames[-6:])
