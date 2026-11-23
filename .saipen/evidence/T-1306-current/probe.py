"""Calibrate public acceptance projection using canonical isolated fixture writers."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.evidence import EvidenceRun
from saipen_engine.init_project import bootstrap_project
from test_hermetic_env import hermetic_env


def file_map(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob("*") if p.is_file()}


def run(label):
    durable = EVIDENCE / label
    assert not durable.exists(), "immutable evidence label already exists"
    allocation = EvidenceRun("t1306-" + label, "T-1306", durable_dir=durable)
    project = allocation.temp_root / "project"
    allocation.register_ephemeral(project)
    project.mkdir()
    bootstrap_project(project, agent="t1306-fixture")
    prefix = [sys.executable, "-B", str(ROOT / "tools/saipen.py"),
              "--project-root", str(project), "--agent", "t1306-fixture"]
    commands = []

    def cli(*args):
        result = subprocess.run([*prefix, *args, "--json"], cwd=project,
                                env=hermetic_env(), capture_output=True, text=True,
                                encoding="utf-8", timeout=90)
        commands.append({"args": args, "exit_code": result.returncode,
                         "stdout": result.stdout, "stderr": result.stderr})
        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"], payload
        return payload

    added = cli("ticket", "add", "P2", "T-1306 isolated criterion calibration fixture",
                "--verify", "AC-01 [UNIT] fixture marker binding; AC-02 [EFFECT_PATH] fixture broader witness")
    ticket = added["ticket"]
    cli("claim", ticket)
    cli("transition", "BUILD", ticket, "controlled fixture build epoch")
    projections = {}

    def observe(name, states):
        before = file_map(project / ".saipen")
        data = cli("acceptance", ticket)
        assert before == file_map(project / ".saipen"), "public projection wrote fixture bytes"
        actual = {row["ac"]: row["state"] for row in data["criteria"]}
        assert actual == states, (name, actual, states)
        projections[name] = data
        return data

    unverified = {"AC-01": "UNVERIFIED", "AC-02": "UNVERIFIED"}
    observe("empty", unverified)
    cli("checkpoint", "RUN", ticket, "PASS conf: high -- fixture claims both criteria complete")
    observe("prose", unverified)
    cli("checkpoint", "RUN", ticket, "quoted fixture AC-EVIDENCE AC-01 PASS behavioral")
    observe("quoted", unverified)
    cli("checkpoint", "RUN", ticket, "AC-EVIDENCE AC-01 PASS claim -- intentionally invalid fixture class")
    observe("invalid_class", unverified)
    bound = cli("checkpoint", "RUN", ticket,
                "AC-EVIDENCE AC-01 PASS behavioral witness=UNIT surface=fixture-calibration -- controlled marker")
    data = observe("bound", {"AC-01": "SATISFIED", "AC-02": "UNVERIFIED"})
    assert data["criteria"][0]["evidence"][0]["event"] == int(bound["event_id"].removeprefix("E-"))
    cli("checkpoint", "RUN", ticket,
        "AC-EVIDENCE AC-02 PASS behavioral witness=UNIT surface=fixture-calibration -- narrower fixture witness")
    observe("too_weak", {"AC-01": "SATISFIED", "AC-02": "EVIDENCE_SCOPE_TOO_WEAK"})
    broader = cli("checkpoint", "RUN", ticket,
                  "AC-EVIDENCE AC-02 PASS behavioral witness=EFFECT_PATH surface=fixture-calibration -- fixture marker only")
    observe("broader_marker", {"AC-01": "SATISFIED", "AC-02": "SATISFIED"})
    cli("checkpoint", "RUN", ticket, "AC-EVIDENCE AC-01 FAIL behavioral -- controlled contradictory fixture marker")
    observe("conflict", {"AC-01": "CONTESTED", "AC-02": "SATISFIED"})
    cli("checkpoint", "RUN", ticket, "AC-EVIDENCE AC-07 PASS static -- undeclared fixture criterion")
    data = observe("undeclared", {"AC-01": "CONTESTED", "AC-02": "SATISFIED"})
    assert data["undeclared_evidence"] == ["AC-07"]
    cli("checkpoint", "RUN", ticket,
        "AC-ESCAPED AC-02 " + broader["event_id"] + " NOT_COVERED -- controlled fixture contradiction")
    observe("escaped", {"AC-01": "CONTESTED", "AC-02": "CONTESTED"})
    report = {"fixture_only": True, "grants_authority": False,
              "ticket": ticket, "projections": projections,
              "readonly_checks": len(projections), "commands": commands,
              "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "temp_root": str(allocation.temp_root)}
    (durable / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    allocation.finalize(verdict="PASS", extra={"readonly_checks": len(projections), "fixture_only": True})
    assert not allocation.temp_root.exists()
    print(json.dumps({"fixture_projection_checks": len(projections),
                      "readonly": True, "owned_temp_reclaimed": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1]))
