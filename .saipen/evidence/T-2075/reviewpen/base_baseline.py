"""Bounded race probe: two checkpoint hooks discover one new DONE closure."""

from __future__ import annotations

import json
import sys
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path.cwd() / "tools"))
import saipen_engine  # noqa: E402

saipen_engine.__path__.insert(0, str(Path(__file__).parent / "base" / "saipen_engine"))
from saipen_engine import gc  # noqa: E402


def main() -> None:
    # Ceiling: one temporary Git project, at most eight small files, two
    # threads, a five-second synchronization bound, and a 30-second timeout.
    with tempfile.TemporaryDirectory(
        prefix="saitest-t2062-", dir=Path(__file__).parent
    ) as tmp:
        root = Path(tmp)
        (root / ".saipen").mkdir()
        (root / ".saipen" / "LOG.md").write_text(
            "# Log\n- 16.11.26 00:00 [E-001] [T-001] "
            "[op: finish-one] RUN: T-001 -> DONE\n",
            encoding="utf-8",
        )
        evidence = root / ".saipen" / "evidence" / "canonical.json"
        evidence.parent.mkdir(parents=True)
        evidence.write_bytes(b'{"protected": true}\n')
        state = gc._default_state()
        state["config"]["interval_done"] = 1
        state["config"]["evidence_budget_gib"] = 1.0 / (1024**3)
        gc.save_state(root, state)

        for argv in (
            ("init",),
            ("config", "user.name", "saitest"),
            ("config", "user.email", "saitest@example.invalid"),
            ("add", "-A"),
            ("commit", "-m", "bounded fixture"),
        ):
            subprocess.run(
                ["git", "-C", str(root), *argv],
                check=True,
                capture_output=True,
                timeout=5,
            )

        barrier = threading.Barrier(2)
        local = threading.local()
        canonical_total = gc.canonical_total

        def synchronized_total(project, state=None):
            result = canonical_total(project, state)
            if not getattr(local, "passed", False):
                local.passed = True
                barrier.wait(timeout=5)
            return result

        with mock.patch.object(gc, "canonical_total", synchronized_total):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(
                    pool.map(
                        lambda index: gc.maintenance_checkpoint(
                            root, f"saitest-{index}"
                        ),
                        range(2),
                    )
                )

        state = gc.load_state(root)
        total = gc.canonical_total(root, state)
        print(
            json.dumps(
                {
                    "result_codes": [item.get("code") for item in results],
                    "details": [item.get("detail") for item in results],
                    "counted_done": state.get("counted_done"),
                    "canonical_done": total.get("union"),
                    "maintenance_debt": (state.get("maintenance") or {}).get(
                        "state"
                    ),
                    "maintenance_runs": len(state.get("runs") or []),
                    "durable_failures": len(gc.maintenance_failures(root)),
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()

