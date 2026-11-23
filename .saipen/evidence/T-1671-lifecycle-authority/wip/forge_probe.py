"""Scratch probe: does today's engine accept a hand-written DONE as canonical?"""
import json, os, re, subprocess, sys
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(REPO / "tools"))
import continuity_probes as P  # noqa: E402

env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
env["PYTHONUTF8"] = "1"
env["FORBID_SAIPEN_PROJECT_WRITE"] = str(REPO)
os.environ.clear(); os.environ.update(env)

root = P.fresh_project("t1671-forge")
os.environ["PWD"] = str(root)
subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
A = "buffy"
def show(label, d):
    d = dict(d); d.pop("cold_route", None); d.pop("parked_work", None); d.pop("telegrams", None)
    print(f"== {label}: " + json.dumps(d, ensure_ascii=False)[:900])

show("continue", P.cli(root, A, "continue"))
print((root / ".saipen/STATE.md").read_text(encoding="utf-8"))
print((root / ".saipen/LOG.md").read_text(encoding="utf-8")[-900:])
# --- the executor loses the CLI here and writes the lifecycle by hand ---
P.append_log(root, "T-001", A, "RUN: build -> widget implemented per ADR-7")
P.append_log(root, "T-001", A, "RUN: verify -> PASS [target: T-001] conf: high -- python tools/validate.py -> PASS")
P.append_log(root, "T-001", A, "DEC: T-001 DONE; lifecycle records written by hand against the RFC field shapes")
log = (root / ".saipen/LOG.md").read_text(encoding="utf-8")
tail = max(int(m.group(1)) for m in re.finditer(r"\[E-(\d+)\]", log))
board = root / ".saipen/BOARD.md"
bt = board.read_text(encoding="utf-8")
line = next(l for l in bt.splitlines() if "T-001" in l)
bt = bt.replace(line + "\n", "")
done = re.sub(r"^- \[.\]", "- [x]", line).split(" | owner:")[0] + " | closure_mode: own_patch"
bt = bt.replace("## DONE\n", "## DONE\n" + done + "\n")
board.write_text(bt, encoding="utf-8", newline="\n")
state = root / ".saipen/STATE.md"
st = state.read_text(encoding="utf-8")
st = re.sub(r"^phase: .*$", "phase: DONE", st, flags=re.M)
st = re.sub(r"^task: .*$", "task: none", st, flags=re.M)
st = re.sub(r'^next_action: .*$', 'next_action: "saipen continue"', st, flags=re.M)
st = re.sub(r"^transition_from: .*$", "transition_from: SHIP", st, flags=re.M)
st = re.sub(r"^last_event: .*$", f"last_event: {tail}", st, flags=re.M)
state.write_text(st, encoding="utf-8", newline="\n")
print("--- hand-written ---")
print(st); print(bt); print(log[-700:])
show("status", P.cli(root, A, "status"))
show("continue --dry-run", P.cli(root, A, "continue", "--dry-run"))
code, out = P.validate(root)
print("== validate exit", code)
print("\n".join(l[:400] for l in out.splitlines() if l.startswith(("FAIL", "WARN", "Validation"))))
print("ROOT", root)
