"""Read original incident operands; never seize or mutate a consumer Work."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.board import parse_board
from saipen_engine.log import read_history_snapshot, regression_evidence
from saipen_engine.process_tree import run
from saipen_engine.state import parse_state


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    output = HERE / "consumer-preflight.json"
    if output.exists():
        raise RuntimeError("preparation evidence already exists")
    roots = {"SAI_WEBSITE": Path("V:/___VAC/__K/__CODE/_HTML/_SAI_WEBSITE"),
             "Wintage": Path("V:/___VAC/__K/__CODE/_TAMPERMONKEY/_WIN95THEME/Wintage")}
    environment = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
    environment.update(SAIPEN_CAPABILITY="read-only", PYTHONDONTWRITEBYTECODE="1",
                       PYTHONIOENCODING="utf-8", SAIPEN_FORBID_HOST_SPAWN="1")
    consumers = {}
    for name, project in roots.items():
        before = {basename: sha((project / ".saipen" / basename).read_bytes())
                  for basename in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")}
        state = parse_state((project / ".saipen/STATE.md").read_text(encoding="utf-8"))
        board = parse_board((project / ".saipen/BOARD.md").read_text(encoding="utf-8"))
        history = read_history_snapshot(project, lean=True)
        data = {"root": str(project), "state_frontmatter": state,
                "canonical_sha256": before, "history_hash": history.hash,
                "history_tail": history.tail, "illegal_lines": history.illegal_lines,
                "board_errors": board["errors"]}
        if name == "SAI_WEBSITE":
            data["T31_board"] = board["tickets"].get("T-31")
            data["reported_window_events"] = [event for event in history.events
                                               if 336 <= event["event"] <= 356]
            data["current_regression_gate"] = regression_evidence("T-31", history.events)
        if name == "Wintage":
            data["T359_board"] = board["tickets"].get("T-359")
            data["T916_board"] = board["tickets"].get("T-916")
            relative = ".saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.json"
            target = project / relative
            try:
                info = target.lstat()
            except FileNotFoundError:
                sidecar = {"path": relative, "status": "ABSENT_CONFIRMED_BY_LSTAT"}
            except OSError as exc:
                sidecar = {"path": relative, "status": "UNAVAILABLE", "error": repr(exc)}
            else:
                sidecar = {"path": relative, "status": "REGULAR" if stat.S_ISREG(info.st_mode) else "OTHER_NODE"}
                if stat.S_ISREG(info.st_mode):
                    sidecar["sha256"] = sha(target.read_bytes())
            data["cited_sidecar"] = sidecar
            data["E3286_parsed_events"] = [event for event in history.events if event["event"] == 3286]
        command = [sys.executable, "-B", str(ROOT / "tools/saipen.py"),
                   "--project-root", str(project), "status", "--json"]
        completed = run(command, cwd=project, env=environment, capture_output=True, timeout=120)
        data["native_readonly_status"] = {"command": command, "exit_code": completed.returncode,
                                         "stdout": completed.stdout.decode("utf-8", errors="replace"),
                                         "stderr": completed.stderr.decode("utf-8", errors="replace")}
        if before != {basename: sha((project / ".saipen" / basename).read_bytes()) for basename in before}:
            raise RuntimeError("consumer checkpoint moved during read-only preparation: " + name)
        if read_history_snapshot(project, lean=True).hash != history.hash:
            raise RuntimeError("consumer sealed history moved during preparation: " + name)
        data["canonical_and_history_unchanged"] = True
        consumers[name] = data
    result = {"checked_utc": datetime.now(timezone.utc).isoformat(), "consumers": consumers,
              "scope": "Read-only preparation while T-1714 owns VERIFY; no audit intake, consumer claim, "
                       "repair, closure, browser access, credentials, installation or publication."}
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"record": str(output), "consumers": {
        name: {"phase": data["state_frontmatter"].get("phase"),
               "task": data["state_frontmatter"].get("task"), "tail": data["history_tail"],
               "readonly_status_exit": data["native_readonly_status"]["exit_code"]}
        for name, data in consumers.items()}}))


if __name__ == "__main__":
    main()
