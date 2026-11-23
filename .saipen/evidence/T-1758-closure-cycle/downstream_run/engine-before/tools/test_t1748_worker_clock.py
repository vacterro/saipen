"""Independent controls for the real-process host-bound fixture (T-1748)."""

import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CASE = "test_the_host_bound_ends_a_progressing_slice_without_failure"


def probe(scenario):
    import test_t1446_supervise as subject

    # Bound a broken old fixture without changing the configuration between
    # subjects. Three cycles still admit two generations plus the IDLE decision.
    original = subject.worker.supervise

    def supervise(*args, **kwargs):
        kwargs["max_cycles"] = 3
        if scenario == "early":
            kwargs["max_slice_seconds"] = 0.25
        elif scenario == "disabled":
            kwargs["max_slice_seconds"] = 99.0
        return original(*args, **kwargs)

    if scenario == "starved":
        # Withhold the actual worker thread's CPU for longer than the old
        # one-second idle budget, before it can write its first progress marker.
        start = "root = Path.cwd()"
        assert subject.AGENT.count(start) == 1
        subject.AGENT = subject.AGENT.replace(start, "time.sleep(1.25)\n" + start)
    if scenario == "disabled":
        # Both subjects keep a finite controlled workload for this mutant.
        loop = "while True:\n        bump()"
        assert subject.AGENT.count(loop) == 1
        subject.AGENT = subject.AGENT.replace(loop, "for _ in range(10):\n        bump()")
    if scenario == "window":
        prefix = (
            "import sys\nfrom pathlib import Path\n"
            f"sys.path.insert(0, {str(ROOT / 'tools')!r})\n"
            "import time\nfrom saipen_engine import paths as _paths\n"
            "_old_write = Path.write_text\n_old_all = _paths._write_all\n"
            "def _held(data):\n"
            "    raw = data.encode('utf-8') if isinstance(data, str) else bytes(data)\n"
            "    return (globals().get('index') == 0 and b'last_event: 9\\n' in raw)\n"
            "def _pause():\n"
            "    _old_write(control / 'write-window', 'ready', encoding='utf-8')\n"
            "    time.sleep(10)\n"
            "def _write(path, data, *args, **kwargs):\n"
            "    if _held(data):\n"
            "        with path.open('w', encoding='utf-8') as stream:\n"
            "            _pause()\n            return stream.write(data)\n"
            "    return _old_write(path, data, *args, **kwargs)\n"
            "def _all(fd, data):\n"
            "    if _held(data):\n        _pause()\n"
            "    return _old_all(fd, data)\n"
            "Path.write_text = _write\n_paths._write_all = _all\n"
        )
        subject.AGENT = prefix + subject.AGENT

    case = subject.QualityOverTimeTests(CASE)
    case.setUp()
    try:
        with patch.object(subject.worker, "supervise", side_effect=supervise):
            if scenario == "window":
                result = case.run_plan(
                    ["slow_forever", "finish"], slice_timeout=20.0, max_slice_seconds=0.5
                )
                assert (case.control / "write-window").is_file(), "write window not exercised"
                assert case.state_text(), "killed fixture left STATE empty"
                assert result["stop"] == subject.supervisor.IDLE, result
                assert result["counters"]["worker_generation_count"] == 2, result
                assert result["counters"]["failures"] == {}, result
            else:
                getattr(case, CASE)()
    finally:
        case.doCleanups()


class WorkerClockControls(unittest.TestCase):
    def run_probe(self, scenario):
        return subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--probe", scenario],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )

    def test_normal_real_process_control(self):
        result = self.run_probe("normal")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_worker_without_cpu_beyond_old_idle_budget_stays_green(self):
        result = self.run_probe("starved")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_interruption_inside_state_write_preserves_the_successor(self):
        result = self.run_probe("window")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_too_early_host_bound_turns_the_subject_check_red(self):
        result = self.run_probe("early")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("AssertionError", result.stderr)

    def test_a_disabled_host_bound_turns_the_subject_check_red(self):
        result = self.run_probe("disabled")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("AssertionError", result.stderr)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--probe":
        try:
            probe(sys.argv[2])
        except AssertionError as error:
            print("AssertionError: " + str(error), file=sys.stderr)
            raise SystemExit(1)
        print(json.dumps({"scenario": sys.argv[2], "result": "PASS"}))
    else:
        unittest.main()
