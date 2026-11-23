"""Observe one existing failed callback without changing its oracle or result."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK_RECOVERY_20261010")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pytest


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Observe:
    def __init__(self):
        self.rows = []

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        env = item.funcargs.get("launch_env")
        if env is None:
            yield
            return
        service = env.window._service
        original = service.get_project
        from audapack.config import config_path

        def snapshot(label):
            self.rows.append({
                "stage": label,
                "project_ids": [p.id for p in service.config.projects],
                "config_on_disk": config_path(service.base_dir).is_file(),
                "task_runner_state": env.window.task_runner.state,
                "task_inflight": env.window.task_runner.is_running(env.key),
            })

        def observed(project_id):
            result = original(project_id)
            snapshot("get_project: " + project_id)
            self.rows[-1]["found"] = result is not None
            return result

        service.get_project = observed
        snapshot("before unchanged test")
        try:
            yield
        finally:
            snapshot("after unchanged test")
            service.get_project = original


if __name__ == "__main__":
    output = HERE / "preview-plane-owner.json"
    if output.exists():
        raise RuntimeError("immutable preview evidence already exists")
    baseline = json.loads((ROOT / ".saipen/evidence/T-2-20261012/full-pytest.json").read_text())
    before = {rel: sha(ROOT / rel) for rel in baseline["source_inputs"]}
    canonical_before = {name: sha(ROOT / ".saipen" / name)
                        for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")}
    observation = Observe()
    command = ["tests/test_plane_launch_async.py::test_b_the_verdict_is_applied_on_the_gui_thread",
               "-q", "-p", "no:cacheprovider"]
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        result = pytest.main(command, plugins=[observation])
    changed = [rel for rel, digest in before.items() if sha(ROOT / rel) != digest]
    canonical_after = {name: sha(ROOT / ".saipen" / name) for name in canonical_before}
    evidence = {"scope": "read-only preparation; no engineering claim or completion",
                "command": command, "exit_code": int(result), "observations": observation.rows,
                "product_files_checked": len(before), "product_changed": changed,
                "canonical_unchanged": canonical_before == canonical_after,
                "stdout": stdout.getvalue()}
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in evidence.items() if k != "stdout"}))
