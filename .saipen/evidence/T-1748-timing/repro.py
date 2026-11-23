"""Probe the fixture's kill/write window without editing the tested tree."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import test_t1446_supervise as fixture  # noqa: E402

WRITE = 'state.write_text(text, encoding="utf-8")'


def measure(atomic):
    case = fixture.QualityOverTimeTests(
        "test_the_host_bound_ends_a_progressing_slice_without_failure"
    )
    case.setUp()
    try:
        if atomic:
            replacement = (
                'pending = state.with_name("STATE.pending")\n'
                '    pending.write_text(text, encoding="utf-8")\n'
                '    if index == 0 and event == 9:\n'
                '        (control / "write-window").write_text("ready")\n'
                '        time.sleep(10)\n'
                '    pending.replace(state)'
            )
        else:
            replacement = (
                'if index == 0 and event == 9:\n'
                '        state.open("w", encoding="utf-8").close()\n'
                '        (control / "write-window").write_text("ready")\n'
                '        time.sleep(10)\n'
                '    ' + WRITE
            )
        assert fixture.AGENT.count(WRITE) == 1
        script = fixture.AGENT.replace(WRITE, replacement)
        case.agent.write_text(script, encoding="utf-8")
        result = case.run_plan(
            ["slow_forever", "finish"], slice_timeout=20.0, max_slice_seconds=0.5
        )
        state = (case.project / ".saipen/STATE.md").read_bytes()
        return {
            "subject": "atomic fixture candidate" if atomic else "original in-place fixture",
            "instrumented_agent_sha256": hashlib.sha256(script.encode()).hexdigest(),
            "write_window_reached": (case.control / "write-window").exists(),
            "state_bytes": len(state), "state_text": state.decode("utf-8"),
            "result": result, "trace": case.trace(),
            "limit": "The write interruption is deliberately widened; this proves a reachable fixture defect, not attribution of the historical failure.",
        }
    finally:
        case.doCleanups()


results = [measure(False), measure(True)]
(HERE / "write-window.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
print(json.dumps([{
    "subject": item["subject"], "window": item["write_window_reached"],
    "state_bytes": item["state_bytes"], "stop": item["result"]["stop"],
    "generations": item["result"]["counters"]["worker_generation_count"],
    "failures": item["result"]["counters"]["failures"],
} for item in results], indent=2))
