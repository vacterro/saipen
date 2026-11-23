"""T-1670: derive the SRC-191 contract from clauses.draft.txt, one `saipen source req` each.

Usage: derive_clauses.py <repo>
"""
import json
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
draft = Path(__file__).resolve().parent / "clauses.draft.txt"
launcher = repo / "bin" / "saipen"
failed = 0
for line in draft.read_text(encoding="utf-8").splitlines()[1:]:
    rid, cls, text = line.split("|", 2)
    if rid in sys.argv[2:]:
        continue  # already derived by hand
    proc = subprocess.run(
        [r"C:\Program Files\Git\usr\bin\bash.exe", str(launcher), "source", "req", "SRC-191", rid, cls, text, "--json"],
        cwd=str(repo), capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False,
    )
    try:
        answer = json.loads(proc.stdout)
    except ValueError:
        answer = {"ok": False, "code": "UNPARSED", "detail": (proc.stdout + proc.stderr)[-300:]}
    print(rid, cls, answer.get("ok"), answer.get("code"), answer.get("detail") or "")
    failed += not answer.get("ok")
raise SystemExit(1 if failed else 0)
