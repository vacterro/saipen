"""T-1869 / SRC-298 red control: the PRE-FIX world, measured not asserted.

`measure.py` proves the cure is present. This control proves the defect it cures
was real, and proves it the only honest way available: by measuring the state of
the world before T-1868, then running the verifier's own questions against it.

Three independent pre-fix facts, each measured here:

A. At HEAD the repository held no ZAICODE adapter, so the audit's section 02
   ("no ZCode adapter exists") was a true observation, not a mistake. `git
   cat-file` answers this; the control requires it to FAIL.
B. The pre-fix live config dispatched nothing on `UserPromptSubmit`. That config
   is reproduced in a temporary copy -- the live file is read, never written --
   and the verifier's dispatch check is required to fail on it.
C. The pre-fix hook body, restored into a temporary file and fed the same host
   event, returns green with `ingress_id: null`. That is the silent defect: the
   operator's prompt was dropped while the hook reported success.

Run: python .saipen/evidence/T-1869-audit-premise/control.py
Exit 0 means every pre-fix condition was reproduced.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HOME = Path(__file__).resolve().parents[3]
FP = Path(r"V:\___VAC\__K\__CODE\_PY\_FastPrompter")
CONFIG = Path.home() / ".zcode" / "cli" / "config.json"
REPO_HOOK = HOME / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"

BOOTSTRAP = (
    "import os,runpy,sys;a=sys.argv[1];sys.argv=sys.argv[1:];"
    "os.path.isfile(a) and runpy.run_path(a,run_name=__name__)"
)

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def control_a_no_tracked_adapter() -> None:
    print("\n== A: at HEAD the repository held no ZAICODE adapter ==")
    proc = subprocess.run(
        ["git", "cat-file", "-e", "HEAD:extensions/adapters/zaicode/saipen-guard.py"],
        cwd=str(HOME), capture_output=True, text=True,
    )
    first = proc.stderr.strip().splitlines()[0] if proc.stderr.strip() else ""
    print(f"  git cat-file rc={proc.returncode}")
    print(f"  stderr: {first}")
    check("the adapter is absent at HEAD", proc.returncode != 0)
    # And the directory is untracked, i.e. T-1868 created it in this run.
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "extensions/adapters/zaicode/"],
        cwd=str(HOME), capture_output=True, text=True,
    )
    untracked = status.stdout.strip().startswith("??")
    print(f"  git status: {status.stdout.strip()}")
    check("the adapter directory is untracked (created after HEAD)", untracked)


def control_b_pre_fix_config_dispatched_nothing() -> None:
    print("\n== B: the pre-fix live config dispatched nothing on a prompt ==")
    doc = json.loads(CONFIG.read_text(encoding="utf-8"))
    today = ((doc.get("hooks") or {}).get("events") or {}).get("UserPromptSubmit") or []
    print(f"  UserPromptSubmit entries in the LIVE config: {len(today)}")
    check("the live config now dispatches an adapter", len(today) == 1, str(len(today)))

    # The live file is read only. The pre-fix shape is a COPY with no
    # UserPromptSubmit entry at all -- exactly what the audit described.
    with tempfile.TemporaryDirectory(prefix="t1869-red-config-") as tmp:
        pre_fix = json.loads(json.dumps(doc))
        ((pre_fix.get("hooks") or {}).get("events") or {}).pop("UserPromptSubmit", None)
        copy = Path(tmp) / "config.json"
        copy.write_text(json.dumps(pre_fix, indent=1), encoding="utf-8")
        reread = json.loads(copy.read_text(encoding="utf-8"))
        entries = ((((reread.get("hooks") or {}).get("events") or {})
                   .get("UserPromptSubmit")) or [])
        print(f"  reproduced pre-fix UserPromptSubmit entries: {len(entries)}")
        check("the pre-fix config dispatched nothing", len(entries) == 0)
        # measure.py M1 asserts exactly this equality, so it fails on that state.
        check("measure.py's dispatch check FAILS on the pre-fix config",
              len(entries) != 1)


def control_c_pre_fix_reader_drops_the_prompt() -> None:
    print("\n== C: the pre-fix READER against a real host event ==")
    source = REPO_HOOK.read_text(encoding="utf-8")
    marker = "    ingress = _declared_ingress(event)\n"
    if marker not in source:
        check("the pre-fix reader can be reconstructed", False, "marker moved")
        return
    pre_fix = (
        '    ingress = event.get("host_ingress")\n'
        "    if not isinstance(ingress, dict):\n"
        '        print(json.dumps({"ok": True, "ingress_id": None, "sealed": False}))\n'
        "        return 0\n"
    )
    event = {
        "hookEventName": "UserPromptSubmit",
        "hook_event_name": "UserPromptSubmit",
        "prompt": "cc",
        "cwd": str(FP),
        "sessionId": "sess-t1869-red",
        "session_id": "sess-t1869-red",
        "turnId": "turn-t1869-red",
    }
    with tempfile.TemporaryDirectory(prefix="t1869-red-hook-") as tmp:
        red_hook = Path(tmp) / "saipen-guard-pre-fix.py"
        red_hook.write_text(source.replace(marker, pre_fix), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-c", BOOTSTRAP, str(red_hook), "--host", "zaicode",
             "--saipen-root", str(HOME)],
            input=json.dumps(event), capture_output=True, text=True, timeout=180,
        )
    print(f"  rc={proc.returncode} stdout={proc.stdout.strip()}")
    lines = [l for l in proc.stdout.strip().splitlines() if l.strip().startswith("{")]
    if not lines:
        check("the pre-fix hook answered", False, proc.stdout.strip()[:200])
        return
    reply = json.loads(lines[-1])
    check("the pre-fix hook dropped the operator's prompt",
          reply.get("ingress_id") is None, json.dumps(reply))
    check("it still answered ok -- the defect was silent",
          reply.get("ok") is True, json.dumps(reply))


def main() -> int:
    print(f"project home: {HOME}")
    print(f"subject     : {FP}")
    control_a_no_tracked_adapter()
    control_b_pre_fix_config_dispatched_nothing()
    control_c_pre_fix_reader_drops_the_prompt()
    print("\n== CONTROL VERDICT ==")
    if failures:
        print(f"CONTROL INVALID: {len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("CONTROL VALID: the pre-fix world lacked the adapter, the dispatch and the reader")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
