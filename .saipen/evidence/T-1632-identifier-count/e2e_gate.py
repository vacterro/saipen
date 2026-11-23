"""T-1632 end to end: does VERIFY -> REVIEW accept a verify line that cites a pair by id?

Usage: python e2e_gate.py <saipen home holding tools/>

Drives a fixture ticket through the public CLI of the given home up to VERIFY,
records the exact shape LOG E-12510 used, and asks for the transition.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

home = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(home / "tools"))

import test_t1614_future_gate as H  # noqa: E402
from test_hermetic_env import hermetic_env  # noqa: E402

base, project = H._project(intent="normal")
engine = str(home / "tools" / "saipen.py")
env = hermetic_env()


def saipen(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-B", engine, *args, "--project-root", str(project), "--json", "--agent", "tester"],
        capture_output=True,
        env=env,
        timeout=180,
    )
    try:
        return json.loads(proc.stdout.decode("utf-8", "replace"))
    except ValueError:
        return {"code": f"UNPARSED rc={proc.returncode}", "detail": proc.stderr.decode("utf-8", "replace")[-400:]}


VERIFY_LINE = (
    "verify -> PASS [target: {tid}] conf: high -- regression pair E-12503 FAIL / E-12504 PASS "
    "same verifier 7e7eb72e7be1564f ADMISSIBLE; incident controls 9 OK"
)
steps = []
try:
    tid = H._add(project, "a bug fix whose verify line cites its regression pair")
    for args in (
        ("claim", tid),
        ("checkpoint", "RUN", tid, "SCOUT -- fixture"),
        ("transition", "BUILD", tid, "SCOUT recorded"),
        ("checkpoint", "RUN", tid, "build -> fixture change"),
        ("transition", "VERIFY", tid, "BUILD recorded"),
        ("checkpoint", "RUN", tid, VERIFY_LINE.format(tid=tid)),
    ):
        result = saipen(*args)
        steps.append((args[0], args[1] if len(args) > 1 else "", result.get("code")))
        if not result.get("ok"):
            raise SystemExit(json.dumps({"home": home.name, "setup_failed": steps, "detail": result.get("detail")}))
    gate = saipen("transition", "REVIEW", tid, "VERIFY PASS")
    print(
        json.dumps(
            {
                "home": home.name,
                "transition_to_REVIEW": gate.get("code"),
                "ok": gate.get("ok"),
                "detail": str(gate.get("detail") or gate.get("message") or "")[:260],
            }
        )
    )
finally:
    shutil.rmtree(base, True)
