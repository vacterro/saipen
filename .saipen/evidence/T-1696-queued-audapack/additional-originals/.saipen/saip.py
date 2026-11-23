import subprocess
import sys

SA = r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\tools\saipen.py"
PY_EXE = r"C:\Users\vac34\AppData\Local\Programs\Python\Python311\python.exe"


def run(*args):
    result = subprocess.run(
        [PY_EXE, SA, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    print(" ".join(args[:4]), "rc=", result.returncode)
    print((result.stdout or "").strip()[:900])
    if result.returncode:
        print("ERR:", (result.stderr or "").strip()[:900])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(run(*sys.argv[1:]))
