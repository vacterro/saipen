"""Sacrificial lifecycle probes; no writes to AUDAPACK or production code."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CASE = Path(__file__).resolve().parent
HOME = CASE.parents[2]
sys.path.insert(0, str(HOME / "tools"))
from test_hermetic_env import isolate_host_session
from test_t1671_lifecycle_authority import _project
from saipen_engine import codec, state
from saipen_engine.lock import project_writer_lock

isolate_host_session()
RUN = Path(tempfile.mkdtemp(prefix="audapack-integrity-probes-")).resolve()
assert not RUN.is_relative_to(HOME.resolve())
assert not RUN.is_relative_to(Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK").resolve())
RESULTS = []


def command(root, label, args, *, native=False, agent="buffy"):
    if native:
        argv = [sys.executable, str(HOME / "tools/validate.py"), "--project-root", str(root), "--gate", "core", "--no-receipt"]
    else:
        argv = [sys.executable, str(HOME / "tools/saipen.py"), "--project-root", str(root), "--agent", agent, "--json", *args]
    proc = subprocess.run(argv, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="backslashreplace", timeout=300)
    output = proc.stdout + proc.stderr
    (CASE / (label + ".txt")).write_text(output, encoding="utf-8")
    try:
        payload = json.loads(proc.stdout)
    except ValueError:
        payload = None
    result = {"label": label, "argv": argv, "root": str(root), "exit_code": proc.returncode,
              "output_sha256": hashlib.sha256(output.encode()).hexdigest(), "payload": payload,
              "failures": [line for line in output.splitlines() if line.startswith("FAIL")],
              "terminal": output.splitlines()[-1:]}
    RESULTS.append(result)
    return proc.returncode, output, payload


def write(root, name, text):
    assert root.resolve().is_relative_to(RUN)
    (root / ".saipen" / name).write_text(text, encoding="utf-8", newline="\n")


def read(root, name):
    return codec.read_doc(root / ".saipen" / name)


def core(root):
    return {name: hashlib.sha256((root / ".saipen" / name).read_bytes()).hexdigest() for name in ("STATE.md", "BOARD.md", "LOG.md")}


def clone(base, label):
    root = RUN / label
    shutil.copytree(base, root)
    return root


def rejection(root, label, expected):
    code, output, _ = command(root, label, [], native=True)
    assert code != 0 and re.search(expected, output), (label, code, output)
    return {"probe": label, "rejected": True, "native": True, "diagnostic_pattern": expected}


def main():
    base = _project().resolve()
    assert not base.is_relative_to(HOME.resolve())
    for args in (
        ("add", "--", ".saipen/IDENTITY.md", ".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md"),
        ("-c", "user.name=Forensic Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-q", "-m", "test: seed sacrificial lifecycle fixture"),
    ):
        subprocess.run(["git", *args], cwd=base, check=True, capture_output=True)
    # The existing fixture factory owns this temporary directory. Copy it
    # under the bounded run folder; preserve both, never recursively delete.
    base = clone(base, "baseline")
    code, output, _ = command(base, "fixture-baseline", [], native=True)
    assert code == 0, (code, output)
    verdicts = []

    root = clone(base, "duplicate")
    write(root, "BOARD.md", read(root, "BOARD.md").replace("## TODO\n", "## TODO\n- [ ] T-001 [P1] conflicting second identity | verify: a different contract\n"))
    verdicts.append(rejection(root, "probe-duplicate", r"duplicate ticket ID T-001"))

    root = clone(base, "unadmitted-closed")
    write(root, "BOARD.md", read(root, "BOARD.md").replace("## DONE\n", "## DONE\n- [x] T-999 [P1] unadmitted implementation | verify: implemented | closure_mode: own_patch\n"))
    verdicts.append(rejection(root, "probe-unadmitted-closed", r"(?i)(lifecycle authority.*T-999|T-999.*(unallocated|adopt|allocation|admission))"))

    root = clone(base, "unnumbered")
    write(root, "LOG.md", read(root, "LOG.md").replace("# Log\n", "# Log\n- 09.10.26 [T-299] [P1] Widget completed; T-299 DONE\n", 1))
    verdicts.append(rejection(root, "probe-unnumbered", r"Event Graph skeleton|not a legal LOG event"))

    root = clone(base, "state-head")
    parsed = state.parse_state(read(root, "STATE.md"))
    write(root, "STATE.md", state.patch_state(read(root, "STATE.md"), {"last_event": parsed["last_event"] + 7}))
    verdicts.append(rejection(root, "probe-state-head", r"(?i)(last_event|STATE marker|lifecycle authority)"))

    root = clone(base, "malformed-headings")
    write(root, "BOARD.md", read(root, "BOARD.md").replace("## TODO\n", "## TODO## DOING\n").replace("## DOING\n", ""))
    verdicts.append(rejection(root, "probe-malformed-headings", r"required (heading|section heading).*## (TODO|DOING)"))

    root = clone(base, "conflicting-restore")
    before = read(root, "BOARD.md")
    code, output, added = command(root, "allocation-before-restore", ["ticket", "add", "P2", "allocated identity", "--verify", "separate contract"])
    assert code == 0 and added.get("ok"), output
    assigned = added["ticket"]
    write(root, "BOARD.md", re.sub(r"^- \[.\] " + re.escape(assigned) + r"\b[^\n]*\n", "", read(root, "BOARD.md"), flags=re.M))
    code, output, newer = command(root, "allocation-after-row-loss", ["ticket", "add", "P2", "new identity after restore", "--verify", "independent contract"])
    assert code == 0 and newer.get("ok") and int(newer["ticket"][2:]) > int(assigned[2:]), output
    # Restore an old row using an id still owned by live work: the conflict
    # must be rejected instead of letting the restored row shadow the owner.
    old = next(line for line in before.splitlines() if re.match(r"^- \[.\] T-001\b", line))
    restored = re.sub(r"^- \[.\]", "- [ ]", old).split(" | owner:")[0] + " | notes: conflicting restoration snapshot"
    write(root, "BOARD.md", read(root, "BOARD.md").replace("## TODO\n", "## TODO\n" + restored + "\n"))
    result = rejection(root, "probe-conflicting-restore", r"duplicate ticket ID T-001")
    result.update({"previously_assigned": assigned, "allocated_after_row_loss": newer["ticket"], "history_reservation_preserved": True})
    verdicts.append(result)

    root = clone(base, "concurrent")
    original = core(root)
    with project_writer_lock(root):
        code, output, refused = command(root, "probe-concurrent-writer", ["ticket", "add", "P2", "competing writer", "--verify", "must be refused"], agent="forensic-other")
        assert code != 0 and "WRITER_BUSY" in output, (code, output)
        assert core(root) == original
        # Read-only validation may observe a healthy tree while a writer lock
        # is held; exclusivity belongs to canonical mutation admission.
        native_code, native_output, _ = command(root, "validator-under-writer-lock", [], native=True)
        assert native_code == 0, native_output
    code, output, refused_claim = command(root, "probe-conflicting-claim", ["claim", "T-001"], agent="forensic-other")
    assert code != 0 and not refused_claim.get("ok"), output
    assert core(root) == original
    verdicts.append({"probe": "probe-concurrent-writer", "rejected": True, "native": False, "code": refused.get("code"), "foreign_claim_code": refused_claim.get("code"), "core_unchanged": True, "read_only_validator_under_lock": "PASS; mutation admission owns concurrency"})

    (CASE / "enforcement-results.json").write_text(json.dumps({"run": str(RUN), "baseline": str(base), "baseline_native": "PASS", "production_code_modified": False, "verdicts": verdicts, "commands": RESULTS}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run": str(RUN), "baseline_native": "PASS", "verdicts": verdicts}, indent=2))


if __name__ == "__main__":
    try:
        main()
    finally:
        (CASE / "enforcement-command-attempts.json").write_text(json.dumps({"run": str(RUN), "commands": RESULTS}, indent=2) + "\n", encoding="utf-8")
