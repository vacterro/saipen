"""Scratch probe: the hand-written DONE against an engine tree: forge_probe2.py <tree> [shape]."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
SHAPE = sys.argv[2] if len(sys.argv) > 2 else "idle"
sys.path.insert(0, str(REPO / "tools"))
import continuity_probes as P  # noqa: E402

env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
env["PYTHONUTF8"] = "1"
env["FORBID_SAIPEN_PROJECT_WRITE"] = "V:\\___VAC\\__K\\__CODE\\_AI_STUFF_AGENTIC\\_SAIPEN"
os.environ.clear()
os.environ.update(env)

root = P.fresh_project("t1671-forge")
os.environ["PWD"] = str(root)
subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
A = "buffy"


def show(label, d):
    d = dict(d)
    for key in ("cold_route", "parked_work", "telegrams", "distribution", "milestone"):
        d.pop(key, None)
    print(f"== {label}: " + json.dumps(d, ensure_ascii=False)[:1100])
    return d


show("continue", P.cli(root, A, "continue"))
show("claim", P.cli(root, A, "claim", "T-001"))
show("transition BUILD", P.cli(root, A, "transition", "BUILD", "T-001", "scout done"))
# --- the executor loses the control route here and writes the lifecycle by hand ---
P.append_log(root, "T-001", A, "RUN: build -> widget implemented per ADR-7")
P.append_log(root, "T-001", A, "RUN: verify -> PASS [target: T-001] conf: high -- python tools/validate.py -> PASS")
P.append_log(root, "T-001", A, "DEC: T-001 DONE; lifecycle records written by hand against the RFC field shapes")
log = (root / ".saipen/LOG.md").read_text(encoding="utf-8")
tail = max(int(m.group(1)) for m in re.finditer(r"\[E-(\d+)\]", log))
board = root / ".saipen/BOARD.md"
bt = board.read_text(encoding="utf-8")
line = next(l for l in bt.splitlines() if "T-001" in l)
bt = bt.replace(line + "\n", "")
done = re.sub(r"^- \[.\]", "- [x]", line) + " | closure_mode: own_patch"
bt = bt.replace("## DONE\n", "## DONE\n" + done + "\n")
board.write_text(bt, encoding="utf-8", newline="\n")
state = root / ".saipen/STATE.md"
st = state.read_text(encoding="utf-8")
st = re.sub(r"^phase: .*$", "phase: DONE", st, flags=re.M)
if SHAPE == "idle":
    st = re.sub(r"^task: .*$", "task: none", st, flags=re.M)
st = re.sub(r"^next_action: .*$", 'next_action: "saipen continue"', st, flags=re.M)
st = re.sub(r"^transition_from: .*$", "transition_from: SHIP", st, flags=re.M)
st = re.sub(r"^last_event: .*$", f"last_event: {tail}", st, flags=re.M)
state.write_text(st, encoding="utf-8", newline="\n")
print("--- hand-written ---")
print(st)
print(bt)
print(log[-520:])
show("status", P.cli(root, A, "status"))
show("transition SCOUT", P.cli(root, A, "transition", "SCOUT", "next"))
show("checkpoint", P.cli(root, A, "checkpoint", "RUN", "T-001", "note after the forge"))
show("ticket add", P.cli(root, A, "ticket", "add", "P2", "another", "--verify", "x"))
dry = show("continue --dry-run", P.cli(root, A, "continue", "--dry-run"))
real = show("continue", P.cli(root, A, "continue"))
rid = real.get("repair_id") or dry.get("repair_id")
print("repair_id", rid, "| next:", real.get("canonical_next_command"))
if rid:
    show("recover approved", P.cli(root, A, "recover", "--apply-approved-repair", rid))
    print((root / ".saipen/STATE.md").read_text(encoding="utf-8"))
    print((root / ".saipen/BOARD.md").read_text(encoding="utf-8"))
    print((root / ".saipen/LOG.md").read_text(encoding="utf-8")[-900:])
    show("status after", P.cli(root, A, "status"))
    show("continue after", P.cli(root, A, "continue", "--dry-run"))
print("ROOT", root)
