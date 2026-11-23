"""Invoke and record the existing launcher INIT, without replacing its owner."""

import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone

from preflight import HERE, HOME, ORIGINAL, RECOVERY, inventory, sha, write_new


def main():
    p0 = json.loads((HERE / "phase0.json").read_text(encoding="utf-8"))
    p2 = json.loads((HERE / "phase2.json").read_text(encoding="utf-8"))
    assert p2["copy_pass"]
    for relative, digest in p0["installation_hashes"].items():
        assert sha(HOME / relative) == digest, f"Installation changed: {relative}"
    assert not (RECOVERY / ".saipen").exists()
    before = inventory(RECOVERY)
    command = [str(HOME / "bin/saipen.cmd"), "--project-root", str(RECOVERY),
               "--agent", "saipen-cli", "init", "--json"]
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", GIT_OPTIONAL_LOCKS="0")
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=RECOVERY, env=env, stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=300, check=False)
    payload = None
    failure = None
    after = inventory(RECOVERY)
    try:
        payload = json.loads(result.stdout)
        assert result.returncode == 0 and payload["code"] == "INIT_COMPLETED" and payload["ok"]
        assert payload["mailbox"]["code"] == "MAILBOX_ATTACH_SKIPPED", payload
        sys.path.insert(0, str(HOME / "tools"))
        from saipen_engine.paths import project_lineage_identity
        original_lineage = project_lineage_identity(ORIGINAL)
        lineage = project_lineage_identity(RECOVERY)
        assert original_lineage == p2["original_lineage"]
        assert lineage and lineage != original_lineage
        new_files = sorted(set(after["files"]) - set(before["files"]))
        changed = [name for name in before["files"] if name not in after["files"]
                   or after["files"][name]["sha256"] != before["files"][name]["sha256"]]
        assert new_files == [".saipen/BOARD.md", ".saipen/IDENTITY.md", ".saipen/LOG.md", ".saipen/STATE.md"]
        assert not changed, changed
        marker = __import__("saipen_engine.mailbox", fromlist=["mailbox"])
        mailbox_marker = marker.default_workspace() / marker.MARKER_NAME
        assert sha(mailbox_marker) == p0["mailbox_marker_sha256"]
    except Exception:
        failure = traceback.format_exc()
        original_lineage = p2["original_lineage"]
        lineage = None
        new_files = sorted(set(after["files"]) - set(before["files"]))
        changed = []
    record = {"started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
              "argv": command, "cwd": str(RECOVERY), "exit_code": result.returncode,
              "stdout": result.stdout.decode("utf-8", errors="replace"),
              "stderr": result.stderr.decode("utf-8", errors="replace"), "payload": payload,
              "original_lineage": original_lineage, "new_lineage": lineage,
              "python": sys.executable, "python_version": sys.version,
              "python_executable_sha256": sha(__import__("pathlib").Path(sys.executable)),
              "installation_home": str(HOME), "installation_hashes": p0["installation_hashes"],
              "before_content_sha256": before["content_sha256"], "after": after,
              "initialized_files": {name: after["files"][name] for name in new_files},
              "preexisting_changed_files": changed, "mailbox_provisioned": False,
              "init_pass": failure is None, "failure": failure,
              "authority_verdict": "NOT_YET_ACCEPTED; INIT success alone grants no recovery acceptance"}
    write_new(HERE / "phase3.json", record)
    print(json.dumps({"init_pass": record["init_pass"], "exit_code": result.returncode,
                      "original_lineage": original_lineage, "new_lineage": lineage,
                      "initialized_files": new_files, "failure": failure}, indent=2))
    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
