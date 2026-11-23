import sys, subprocess, re
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "tools"))
import test_t1671_lifecycle_authority as T
T.setUpModule()
root = T._project(); T._type_the_lifecycle(root)
for args in (["ticket", "done", "T-001", "--closure-mode", "own_patch"], ["handoff", "T-001", "--to", "other"], ["next"], ["start", "new task"]):
    r = subprocess.run([sys.executable, "-B", str(Path(sys.argv[1]) / "tools/saipen.py"), "--project-root", str(root), "--agent", "buffy", "--json", *args], cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    print("=====", args)
    lines = [l for l in out.splitlines() if l.strip().startswith("File ") or "Error" in l]
    print("\n".join(l[-170:] for l in lines[-9:]) if "Traceback" in out else out[:700])
