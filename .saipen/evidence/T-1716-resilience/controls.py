"""Bounded audit controls; disposable fixtures, no production repair."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.admission import evaluate_admission
from saipen_engine.board import parse_board
from saipen_engine.capability import may_mutate
from saipen_engine.operations import ticket_add, ticket_move
from saipen_engine.process_tree import run
from saipen_engine.state import parse_state
from test_regression_gate import RegressionGateFixture


def digest(root: Path) -> dict:
    return {name: hashlib.sha256((root / ".saipen" / name).read_bytes()).hexdigest()
            for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")
            if (root / ".saipen" / name).exists()}


def fixture() -> RegressionGateFixture:
    value = RegressionGateFixture()
    value.setUp()
    base = value.project.parent.resolve()
    assert base.parent == Path(tempfile.gettempdir()).resolve()
    assert base.name.startswith("saipen-regression-gate-")
    return value


def add(root: Path, description: str) -> str:
    result = ticket_add(root, "tester", "P2", description, [], "audit fixture only")
    assert result.ok, result.to_dict()
    return result.data["ticket"]


def reservation_control(active: bool) -> dict:
    case = fixture()
    try:
        root = case.project
        parent = "T-7" if active else add(root, "unclaimed parent with no own lifecycle")
        child = add(root, "workable dependency child")
        state_before = parse_state((root / ".saipen/STATE.md").read_text(encoding="utf-8"))
        before = digest(root)
        rejected = ticket_move(root, "block-for", parent, "tester", "self is invalid",
                               blocked_on=parent)
        assert not rejected.ok and digest(root) == before
        result = ticket_move(root, "block-for", parent, "tester", "audit dependency",
                             blocked_on=child)
        assert result.ok, result.to_dict()
        board = parse_board((root / ".saipen/BOARD.md").read_text(encoding="utf-8"))
        fields = board["tickets"][parent]["fields"]
        state_after = parse_state((root / ".saipen/STATE.md").read_text(encoding="utf-8"))
        assert fields["resume_phase"] == "VERIFY"
        assert state_after["task"] == ("none" if active else "T-7")
        return {"active_parent": active, "parent": parent, "child": child,
                "before_phase": state_before["phase"], "before_task": state_before["task"],
                "after_phase": state_after["phase"], "after_task": state_after["task"],
                "result": result.to_dict(), "parent_fields": fields,
                "self_child_refusal": rejected.code, "self_child_zero_write": True,
                "finding": "valid active handoff" if active else
                "unclaimed TODO parent borrowed another ticket's VERIFY resume phase"}
    finally:
        case.doCleanups()


def mode_control() -> dict:
    case = fixture()
    try:
        root = case.project
        target = root / "ordinary.py"
        target.write_text("# disposable audit target\n", encoding="utf-8")
        normal = evaluate_admission(root, target, agent="tester")
        assert normal["admitted"], normal
        state_path = root / ".saipen/STATE.md"
        initial = state_path.read_bytes()
        # Controlled state-input variation only. This is not an authentic
        # historical producer and must not be counted as a live incident.
        state_path.write_bytes(initial.replace(b"mode: full", b"mode: read-only"))
        historical_mode = evaluate_admission(root, target, agent="tester")
        readable = evaluate_admission(root, target, action="read", agent="tester")
        protected = evaluate_admission(root, state_path, agent="tester")
        assert not historical_mode["admitted"], historical_mode
        assert historical_mode["code"] == "PROTOCOL_MODE_READONLY", historical_mode
        assert readable["admitted"] and not protected["admitted"]
        state_path.write_bytes(initial)
        restored = evaluate_admission(root, target, agent="tester")
        assert restored["admitted"], restored
        return {"live_no_publish_may_mutate": may_mutate("no-publish"), "normal": normal,
                "historical_read_only_mode": historical_mode, "read": readable,
                "protected_write": protected, "restored": restored,
                "limitation": "synthetic input conflict, not proof of a production incident"}
    finally:
        case.doCleanups()


before = digest(ROOT)
output = HERE / (sys.argv[1] if len(sys.argv) > 1 else "controls.json")
assert output.parent == HERE and not output.exists()
environment = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
environment["SAIPEN_CAPABILITY"] = "no-publish"
with mock.patch.dict(os.environ, environment, clear=True):
    value = {"schema_version": 1, "scope": "T-1716 AUDIT_ONLY", "production_before": before,
             "active_handoff": reservation_control(True),
             "todo_parent_handoff": reservation_control(False),
             "mode_contract": mode_control()}
    command = run([str(ROOT / "bin/saipen.cmd"), "cc", "all", "--json"],
                  cwd=ROOT, env=environment, capture_output=True, timeout=30)
    refusal = json.loads(command.stdout.decode("utf-8"))
    assert not refusal["ok"] and refusal["code"] == "VALIDATION_FAILED", refusal
    value["cc_all"] = {"exit_code": command.returncode, "result": refusal}
value["production_after"] = digest(ROOT)
assert value["production_after"] == before
value["production_unchanged"] = True
value["passed"] = True
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"passed": True, "artifact": str(output), "production_unchanged": True}))
