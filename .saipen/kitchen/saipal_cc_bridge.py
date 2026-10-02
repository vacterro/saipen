"""Persist one kernel carrier and print only its bounded reasoning surface."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAL = ROOT.parent / "_SAIPAL"
number = sys.argv[1]
run = subprocess.run([sys.executable, "-B", str(PAL / "tools/saipal.py"),
                      "--home", str(PAL / ".saipal"), "--json", "next"],
                     capture_output=True, text=True, encoding="utf-8", timeout=30,
                     env={**os.environ, "PYTHONIOENCODING": "utf-8"})
payload = json.loads(run.stdout)
out = ROOT / ".saipen/evidence/T-1579-storage-safety" / f"saipal-carrier-{number}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
carrier = payload.get("analysis_carrier")
if carrier:
    fields = ("session", "episode", "slice", "unit_digest", "protocol", "signals",
              "applicable_law", "defence_surface", "open_candidates")
    bounded = {key: carrier.get(key) for key in fields}
    bounded["events"] = [{"seq": event["seq"], "type": event["type"], "facts": event["facts"]}
                         for event in carrier["events"]]
    print(json.dumps(bounded, ensure_ascii=False))
else:
    print(json.dumps(payload, ensure_ascii=False))
sys.exit(run.returncode)
