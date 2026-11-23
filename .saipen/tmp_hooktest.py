import json, subprocess, sys

PY = r"C:\Users\vac34\AppData\Local\Programs\Python\Python311\python.exe"
HOOK = r"C:\Users\vac34\.zcode\hooks\saipen-guard.py"
BOOT = "import os,runpy,sys;a=sys.argv[1];sys.argv=sys.argv[1:];os.path.isfile(a) and runpy.run_path(a,run_name=__name__)"

event = {
    "hook_event_name": "UserPromptSubmit",
    "session_id": "sess_53495f99-4c5d-412f-af0c-86d45222c6af",
    "cwd": r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN",
    "prompt": "cc",
    "turnId": "turn-probe-1",
}

cmd = [PY, "-c", BOOT, HOOK, "--host", "zaicode", "--saipen-root", r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN"]
p = subprocess.run(cmd, input=json.dumps(event), capture_output=True, text=True, timeout=120)
print("EXIT", p.returncode)
print("STDOUT:")
print(p.stdout)
print("STDERR:")
print(p.stderr[:2000])
