"""T-1551 SCOUT probe: what do the canonical fixtures report?"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from test_guard_hostile_matrix import active_project, fresh_project  # noqa: E402
from saipen_engine.conformance import conformance_decision  # noqa: E402
from saipen_engine import response_surface as RS  # noqa: E402


def run(root, *args, text=""):
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "saipen.py"), "--project-root", str(root), "--json", *args],
        input=text, capture_output=True, text=True, cwd=str(ROOT), check=False,
    )
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, {"raw": proc.stdout[-500:], "err": proc.stderr[-500:]}


def wait_project():
    root = fresh_project()
    (root / ".saipen" / "STATE.md").write_text(
        (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        .replace("next_action: saipen continue", "next_action: WAIT: manual verify")
        .replace("blocker: \"\"", "blocker: \"HUMAN_DECISION -- choose disposition\""),
        encoding="utf-8",
    )
    return root


for label, maker in (("fresh", fresh_project), ("active", active_project), ("wait", wait_project)):
    root = maker()
    rc, status = run(root, "status")
    auto = status.get("automation", {})
    print(f"== {label} rc={rc} phase={status.get('phase')} task={status.get('task')} blocker={status.get('blocker')!r}")
    print("   automation:", {k: auto.get(k) for k in ("disposition", "next_command", "reason_code", "remediation_command")})
    validation = conformance_decision(root, gate="core")["status"]
    print("   conformance:", validation)
    card = RS.render_boundary(
        RS.OperationalBoundary("DONE", "x", "NONE", "NONE", "NONE", validation)
    )
    for text, tag in ((card, "card"), ("An ordinary explanation.", "prose"),
                      ("T-9001 is DONE, no blockers.", "prose_ticket"),
                      ("STATUS: done\nBLOCKER: NONE -- none", "prose_markers"),
                      ("STATUS\nx\nRESULT\ny\nBLOCKER\nNONE\nOPERATOR ACTION\nNONE\nNEXT EXACT ACTION\nNONE\nVALIDATION\nzzz", "broken_card")):
        rc2, out = run(root, "response", "check", "--stdin", "--auto-eligibility", "--classify", text=text)
        print(f"   classify[{tag}] rc={rc2} class={out.get('class')} turn={out.get('turn_decision')} errors={out.get('errors')}")
