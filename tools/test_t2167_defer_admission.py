"""T-2167 regression oracle: the crew-defer closure parity contract.

RED half (pre-fix operations.py): ``_plan_defer_for_crew`` commits DONE
while the producing candidate attempt closed after the last VERIFY
boundary and without the source closure gate -- the state the canonical
validator then answers CURRENT_FAIL for.

GREEN half (post-fix operations.py): the same plan REFUSES with the same
admission text ``_plan_finish_ticket`` produces, before any write.

The oracle imports the module under test by file path so the regression
harness can stage either subject copy beside it. It builds the attempt
history and the scope record mechanically, then asks the engine's own
plan function to speak.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from saipen_engine import codec  # noqa: E402
from saipen_engine.log import read_history_snapshot_and_logs_digest  # noqa: E402


def _import_operations(root: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "t2167_operations_under_test",
        root / "tools" / "saipen_engine" / "operations.py",
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "saipen_engine"
    spec.loader.exec_module(module)
    return module


LOG_TAIL = (
    "- 23.11.26 00:00 [E-1] [T-1] [agent: oracle] [op: userreq-aa] DEC: user request SRC-1 projected as T-1\n"
    "- 23.11.26 00:01 [E-2] [T-1] [agent: oracle] [op: attempt-open-aa] DEC: attempt A-001 open\n"
    "- 23.11.26 00:02 [E-3] [T-1] [agent: oracle] [op: transition-aa] RUN: transition to VERIFY\n"
    "- 23.11.26 00:03 [E-4] [T-1] [agent: oracle] [op: checkpoint-aa] RUN: verify -> PASS [target: T-1] conf: high -- oracle fixture\n"
    "- 23.11.26 00:04 [E-5] [T-1] [agent: oracle] [op: checkpoint-ab] DEC: REVIEW pass 1 DEC: SHIP\n"
    "- 23.11.26 00:05 [E-6] [T-1] [agent: oracle] [op: transition-ab] RUN: transition to SHIP\n"
    "- 23.11.26 00:06 [E-7] [T-1] [agent: oracle] [op: attempt-close-aa] DEC: attempt A-001 close result candidate stop completed_execution\n"
)


class DeferAdmissionParityTests(unittest.TestCase):
    def test_defer_refuses_a_post_close_candidate_without_new_verification(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="t2167-oracle-"))
        self.addCleanup(_rmtree_silent, root)
        (root / "tools" / "saipen_engine").mkdir(parents=True)
        # The regression harness stages the subject under test as
        # tools/saipen_engine/operations.py beside this oracle BEFORE the
        # run (pre-fix bytes for the 'before' measure, current bytes for
        # 'after'), so the module under test is that exact file.
        (root / "tools" / "saipen_engine" / "operations.py").write_bytes(
            (Path(__file__).parents[1] / "tools" / "saipen_engine" / "operations.py").read_bytes()
        )

        ops = _import_operations(root)

        # The live LOG tail doubles as the sealed history: the snapshot
        # reader needs the files on disk, so stage them first.
        (root / ".saipen").mkdir(exist_ok=True)
        (root / ".saipen" / "LOG.md").write_text(LOG_TAIL, encoding="utf-8")
        (root / ".saipen" / "STATE.md").write_text(_STATE_TEXT, encoding="utf-8")
        (root / ".saipen" / "BOARD.md").write_text(_BOARD_TEXT, encoding="utf-8")
        snapshot, _logs_digest = read_history_snapshot_and_logs_digest(root)
        docs = {
            "state": codec.read_document(root / ".saipen" / "STATE.md"),
            "board": codec.read_document(root / ".saipen" / "BOARD.md"),
            "log": codec.read_document(root / ".saipen" / "LOG.md"),
            "_history": snapshot,
        }
        scope_dir = root / ".saipen" / "kitchen" / "release_scope"
        scope_dir.mkdir(parents=True)
        import json as _json

        sys.path.insert(0, str(TOOLS))
        from freshness import compute_source_identity

        _ident = compute_source_identity(root)
        (scope_dir / "T-1.json").write_text(
            _json.dumps(
                {
                    "schema_version": 2,
                    "ticket": "T-1",
                    "paths": {".saipen/STATE.md": "0" * 64},
                    "project_identity": str(root).lower(),
                    "source_head": _ident.source_head,
                    "source_tree_fingerprint": _ident.source_tree_fingerprint,
                }
            ),
            encoding="utf-8",
        )

        # The scope identity check must pass so the admission gate is what
        # speaks. Reuse the module's own identity helpers against this root.
        real_identity = ops._identity
        ops._identity = lambda r, *a, **k: str(root).lower()
        try:
            plan = ops._plan_defer_for_crew(
                root, "T-1", "oracle", "converge_intent-" + "0" * 32,
                "23.11.26 00:07", "2026-11-23T00:07:00Z",
            )
        finally:
            ops._identity = real_identity

        refused = hasattr(plan, "code") and plan.code == "INCOMPLETE_TICKET"
        admission_text = "no VERIFY boundary after that close"
        detail = getattr(plan, "message", "") or getattr(plan, "detail", "")
        self.assertTrue(
            refused and admission_text in str(detail),
            "defer must refuse a DONE whose candidate attempt closed after "
            "the last VERIFY boundary, exactly like ticket done; got: "
            f"{getattr(plan, 'code', type(plan))} {str(detail)[:160]}",
        )


def _rmtree_silent(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)


_STATE_TEXT = (
    "---\n"
    "phase: SHIP\n"
    "task: T-1\n"
    "next_action: \"PHASE SHIP T-1\"\n"
    "blocker: none\n"
    "agent: oracle\n"
    "mode: full\n"
    "transition_from: REVIEW\n"
    "saipen_version: 8\n"
    "schema_version: 3\n"
    "last_event: 7\n"
    "updated: \"2026-11-23T00:06:00Z\"\n"
    "---\n"
)

_BOARD_TEXT = (
    "# Board\n\n"
    "## DOING\n"
    "- [/] T-1 [P2] oracle defer ticket | verify: the requested change is present "
    "and demonstrated against the user own description of it | request_witness: "
    "model_supplied | source_receipts: SRC-1 | owner: oracle | claim_time: "
    "2026-11-23T00:00:00Z\n\n"
    "## TODO\n\n## DONE\n\n## BLOCKED\n"
)


if __name__ == "__main__":
    unittest.main()
