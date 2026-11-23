"""Bounded control for the P2 guard-directory cleanup follow-up owned by T-1832."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from saipen_engine.process_tree import ProcessTree

with tempfile.TemporaryDirectory(prefix="t1832-guard-cleanup-") as raw:
    barrier = Path(raw) / "guard.json"
    code = f'''
import json,sys,time,os
from pathlib import Path
sys.path.insert(0,{str(Path(__file__).resolve().parents[3] / 'tools')!r})
from saipen_engine.process_tree import ProcessTree
tree=ProcessTree()
process=tree.start([sys.executable,'-c','import time; time.sleep(60)'],
    env={{**os.environ,'SAIPEN_CANONICAL_TEST_CHILD':'1'}})
Path({str(barrier)!r}).write_text(json.dumps({{'group':process.pid,'directory':tree._guard_dir.name}}))
time.sleep(60)
'''
    owner = subprocess.Popen([sys.executable, "-B", "-c", code], stdin=subprocess.DEVNULL)
    guard = None
    group = None
    try:
        deadline = time.monotonic() + 10
        while not barrier.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        info = json.loads(barrier.read_text())
        guard = Path(info["directory"]).resolve()
        group = info["group"]
        owner.kill()
        owner.wait(timeout=10)
        deadline = time.monotonic() + 10
        while ProcessTree.group_pids(group) and time.monotonic() < deadline:
            time.sleep(.01)
        assert not ProcessTree.group_pids(group), "owned verifier survived"
        assert not guard.exists(), "owned process group died but its guard directory survived"
        print("PASS: owner-death cleanup removes its guard directory")
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=10)
        if group is not None:
            with suppress(ProcessLookupError):
                os.killpg(group, signal.SIGKILL)
        if guard is not None:
            assert guard.parent == Path(tempfile.gettempdir()).resolve()
            assert guard.name.startswith("saipen-process-guard-")
            for name in ("reader-ready", "guardian.json"):
                with suppress(FileNotFoundError):
                    (guard / name).unlink()
            with suppress(FileNotFoundError):
                guard.rmdir()
